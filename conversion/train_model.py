"""
Model Training for Conversion Predictor
Trains XGBoost + MLP ensemble on the processed dataset features.

Based on: SalesRLAgent (arXiv:2503.23303) — Section IV

Usage:
    python -m conversion.train_model

Outputs:
    conversion/models/xgb_model.json       — XGBoost classifier
    conversion/models/mlp_model.pkl        — MLP classifier  
    conversion/models/scaler.pkl           — StandardScaler
    conversion/models/knn_index.pkl        — KNN for confidence estimation
    conversion/models/training_report.txt  — Evaluation metrics
"""

import os
import pickle
import numpy as np
from pathlib import Path

from sklearn.model_selection import train_test_split, cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
)
from sklearn.neural_network import MLPClassifier
from sklearn.neighbors import NearestNeighbors
import xgboost as xgb

from conversion.data_prep import load_processed_data
from conversion.feature_extractor import FEATURE_NAMES

# Paths
BASE_DIR = Path(__file__).parent
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)


def train_and_evaluate():
    """Full training pipeline: load data, train, evaluate, save."""
    
    print("=" * 60)
    print("  Conversion Predictor — Model Training")
    print("  Paper: SalesRLAgent (arXiv:2503.23303)")
    print("=" * 60)
    
    # ── Load data ──
    print("\n📂 Loading processed features...")
    X, y, feature_names = load_processed_data()
    print(f"   X shape: {X.shape}, y shape: {y.shape}")
    print(f"   Class distribution: 0={sum(y==0)}, 1={sum(y==1)}")
    
    # ── Train/test split ──
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y,
    )
    print(f"\n📊 Split: train={len(X_train)}, test={len(X_test)}")
    
    # ── Scale features ──
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # ── PCA for embedding features (prevent overfitting) ──
    pca = None
    n_keyword_features = 28
    if X.shape[1] > n_keyword_features:
        from sklearn.decomposition import PCA
        n_embedding_components = 50  # reduce 388 embedding dims → 50
        print(f"\n🔬 Applying PCA to embedding features ({X.shape[1] - n_keyword_features} → {n_embedding_components} dims)")
        
        # Split keyword and embedding features
        X_train_kw = X_train_scaled[:, :n_keyword_features]
        X_train_emb = X_train_scaled[:, n_keyword_features:]
        X_test_kw = X_test_scaled[:, :n_keyword_features]
        X_test_emb = X_test_scaled[:, n_keyword_features:]
        
        # Fit PCA on train embeddings only
        pca = PCA(n_components=n_embedding_components, random_state=42)
        X_train_emb_pca = pca.fit_transform(X_train_emb)
        X_test_emb_pca = pca.transform(X_test_emb)
        
        explained = sum(pca.explained_variance_ratio_) * 100
        print(f"   Explained variance: {explained:.1f}%")
        
        # Recombine: 28 keyword + 30 PCA = 58 features
        X_train_scaled = np.hstack([X_train_kw, X_train_emb_pca])
        X_test_scaled = np.hstack([X_test_kw, X_test_emb_pca])
        print(f"   Final feature count: {X_train_scaled.shape[1]}")
    
    # ── Train XGBoost ──
    print("\n🌲 Training XGBoost classifier...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.7,
        colsample_bytree=0.6,
        min_child_weight=5,
        reg_alpha=1.0,
        reg_lambda=5.0,
        gamma=0.3,
        eval_metric='logloss',
        random_state=42,
        use_label_encoder=False,
    )
    xgb_model.fit(
        X_train_scaled, y_train,
        eval_set=[(X_test_scaled, y_test)],
        verbose=False,
    )
    
    xgb_preds = xgb_model.predict(X_test_scaled)
    xgb_probs = xgb_model.predict_proba(X_test_scaled)[:, 1]
    
    print("   ✅ XGBoost trained")
    _print_metrics("XGBoost", y_test, xgb_preds, xgb_probs)
    
    # ── Train MLP ──
    print("\n🧠 Training MLP classifier...")
    mlp_model = MLPClassifier(
        hidden_layer_sizes=(64, 32),
        activation='relu',
        solver='adam',
        max_iter=500,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.15,
        n_iter_no_change=20,
        learning_rate='adaptive',
        learning_rate_init=0.001,
    )
    mlp_model.fit(X_train_scaled, y_train)
    
    mlp_preds = mlp_model.predict(X_test_scaled)
    mlp_probs = mlp_model.predict_proba(X_test_scaled)[:, 1]
    
    print("   ✅ MLP trained")
    _print_metrics("MLP", y_test, mlp_preds, mlp_probs)
    
    # ── Ensemble (average probabilities) ──
    print("\n🤝 Ensemble (XGBoost + MLP average)...")
    ensemble_probs = (xgb_probs + mlp_probs) / 2
    ensemble_preds = (ensemble_probs >= 0.5).astype(int)
    
    _print_metrics("Ensemble", y_test, ensemble_preds, ensemble_probs)
    
    # ── Feature importance (XGBoost) ──
    print("\n📊 Feature Importance (XGBoost):")
    importances = xgb_model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    for rank, idx in enumerate(sorted_idx[:10], 1):
        name = FEATURE_NAMES[idx] if idx < len(FEATURE_NAMES) else f"feature_{idx}"
        print(f"   {rank}. {name}: {importances[idx]:.4f}")
    
    # ── Build KNN index for confidence estimation ──
    print("\n🔍 Building KNN index for meta-learning confidence...")
    knn = NearestNeighbors(n_neighbors=5, algorithm='ball_tree')
    knn.fit(X_train_scaled)
    print("   ✅ KNN index built (k=5)")
    
    # ── Save models ──
    print("\n💾 Saving models...")
    
    # XGBoost
    xgb_path = MODEL_DIR / "xgb_model.json"
    xgb_model.save_model(str(xgb_path))
    print(f"   XGBoost → {xgb_path}")
    
    # MLP
    mlp_path = MODEL_DIR / "mlp_model.pkl"
    with open(mlp_path, 'wb') as f:
        pickle.dump(mlp_model, f)
    print(f"   MLP → {mlp_path}")
    
    # Scaler
    scaler_path = MODEL_DIR / "scaler.pkl"
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)
    print(f"   Scaler → {scaler_path}")
    
    # KNN
    knn_path = MODEL_DIR / "knn_index.pkl"
    with open(knn_path, 'wb') as f:
        pickle.dump(knn, f)
    print(f"   KNN → {knn_path}")
    
    # ── Save training report ──
    report = _generate_report(y_test, xgb_preds, xgb_probs, mlp_preds, mlp_probs,
                               ensemble_preds, ensemble_probs, importances)
    report_path = MODEL_DIR / "training_report.txt"
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"   Report → {report_path}")
    
    # Save PCA model if used
    if pca is not None:
        pca_path = MODEL_DIR / "pca_model.pkl"
        with open(pca_path, 'wb') as f:
            pickle.dump(pca, f)
        print(f"   PCA → {pca_path}")
    
    print("\n🎉 Training complete! Models saved to conversion/models/")
    print("   Next step: The predictor will auto-load these during runtime.")
    
    # ── Evaluate on HELD-OUT test set (rows 2000-2300, never seen) ──
    held_out_results = {}
    try:
        X_held, y_held, _ = load_processed_data(suffix="_test")
        print(f"\n📋 HELD-OUT TEST SET EVALUATION (n={len(y_held)}, rows 2000-2300)")
        print("   This data was NEVER seen during training.")
        
        X_held_scaled = scaler.transform(X_held)
        
        # Apply PCA if embedding features are present
        if pca is not None and X_held.shape[1] > n_keyword_features:
            X_held_kw = X_held_scaled[:, :n_keyword_features]
            X_held_emb = X_held_scaled[:, n_keyword_features:]
            X_held_emb_pca = pca.transform(X_held_emb)
            X_held_scaled = np.hstack([X_held_kw, X_held_emb_pca])
            print(f"   Applied PCA: {X_held.shape[1]} → {X_held_scaled.shape[1]} features")
        
        ho_xgb_preds = xgb_model.predict(X_held_scaled)
        ho_xgb_probs = xgb_model.predict_proba(X_held_scaled)[:, 1]
        _print_metrics("XGBoost (held-out)", y_held, ho_xgb_preds, ho_xgb_probs)
        
        ho_mlp_preds = mlp_model.predict(X_held_scaled)
        ho_mlp_probs = mlp_model.predict_proba(X_held_scaled)[:, 1]
        _print_metrics("MLP (held-out)", y_held, ho_mlp_preds, ho_mlp_probs)
        
        ho_ens_probs = (ho_xgb_probs + ho_mlp_probs) / 2
        ho_ens_preds = (ho_ens_probs >= 0.5).astype(int)
        _print_metrics("Ensemble (held-out)", y_held, ho_ens_preds, ho_ens_probs)
        
        held_out_results = {
            'held_out_xgb_accuracy': accuracy_score(y_held, ho_xgb_preds),
            'held_out_mlp_accuracy': accuracy_score(y_held, ho_mlp_preds),
            'held_out_ensemble_accuracy': accuracy_score(y_held, ho_ens_preds),
            'held_out_ensemble_f1': f1_score(y_held, ho_ens_preds),
            'held_out_ensemble_auc': roc_auc_score(y_held, ho_ens_probs),
        }
    except FileNotFoundError:
        print("\n⚠️  No held-out test set found. Run: python -m conversion.data_prep")
    
    return {
        'xgb_accuracy': accuracy_score(y_test, xgb_preds),
        'mlp_accuracy': accuracy_score(y_test, mlp_preds),
        'ensemble_accuracy': accuracy_score(y_test, ensemble_preds),
        'ensemble_f1': f1_score(y_test, ensemble_preds),
        'ensemble_auc': roc_auc_score(y_test, ensemble_probs),
        **held_out_results,
    }


def _print_metrics(name: str, y_true, y_pred, y_prob):
    """Print evaluation metrics for a model."""
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    auc = roc_auc_score(y_true, y_prob)
    cm = confusion_matrix(y_true, y_pred)
    
    print(f"   Accuracy:  {acc:.4f}")
    print(f"   Precision: {prec:.4f}")
    print(f"   Recall:    {rec:.4f}")
    print(f"   F1 Score:  {f1:.4f}")
    print(f"   ROC-AUC:   {auc:.4f}")
    print(f"   Confusion Matrix:")
    print(f"     TN={cm[0][0]:4d}  FP={cm[0][1]:4d}")
    print(f"     FN={cm[1][0]:4d}  TP={cm[1][1]:4d}")


def _generate_report(y_test, xgb_preds, xgb_probs, mlp_preds, mlp_probs,
                      ensemble_preds, ensemble_probs, importances) -> str:
    """Generate a text training report."""
    lines = [
        "=" * 60,
        "Conversion Predictor — Training Report",
        "Paper: SalesRLAgent (arXiv:2503.23303)",
        "Dataset: DeepMostInnovations/saas-sales-conversations",
        "=" * 60,
        "",
        "--- XGBoost ---",
        classification_report(y_test, xgb_preds, target_names=['No Conversion', 'Conversion']),
        f"ROC-AUC: {roc_auc_score(y_test, xgb_probs):.4f}",
        "",
        "--- MLP ---",
        classification_report(y_test, mlp_preds, target_names=['No Conversion', 'Conversion']),
        f"ROC-AUC: {roc_auc_score(y_test, mlp_probs):.4f}",
        "",
        "--- Ensemble (XGBoost + MLP) ---",
        classification_report(y_test, ensemble_preds, target_names=['No Conversion', 'Conversion']),
        f"ROC-AUC: {roc_auc_score(y_test, ensemble_probs):.4f}",
        "",
        "--- Feature Importance (XGBoost) ---",
    ]
    
    sorted_idx = np.argsort(importances)[::-1]
    for rank, idx in enumerate(sorted_idx, 1):
        name = FEATURE_NAMES[idx] if idx < len(FEATURE_NAMES) else f"feature_{idx}"
        lines.append(f"  {rank}. {name}: {importances[idx]:.4f}")
    
    return "\n".join(lines)


# ── CLI entry point ─────────────────────────────────────────────────

if __name__ == "__main__":
    results = train_and_evaluate()
    print(f"\n📋 Summary:")
    for k, v in results.items():
        print(f"   {k}: {v:.4f}")
