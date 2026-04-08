"""
Module 5a - XGBoost Lead Scoring Model Training

Trains an XGBoost classifier on the synthetic B2B lead data and saves
the full pipeline (preprocessing + model) as a single pickle file.

Input:  b2b_leads_final.csv (20k rows, 9 cols)
Output: lead_scorer_pipeline.pkl
"""

import pandas as pd
import numpy as np
import pickle
import os
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, TargetEncoder
from sklearn.metrics import (
    roc_auc_score, average_precision_score,
    precision_score, classification_report
)
from xgboost import XGBClassifier

SEED = 42
CSV_PATH = "b2b_leads_final.csv"
OUTPUT_PKL = "lead_scorer_pipeline.pkl"

# Feature groups
HIGH_CARD_COLS = ["City", "Decision_Maker_Job_Title"]
LOW_CARD_COLS = ["Industry", "Country", "Employee_Count", "Annual_Revenue_Range"]
ALL_FEATURES = HIGH_CARD_COLS + LOW_CARD_COLS
TARGET = "Converted"


# ---- 1. Load data ----

df = pd.read_csv(CSV_PATH)
print(f"Loaded {len(df)} rows, {len(df.columns)} cols")
print(f"Target distribution:\n{df[TARGET].value_counts()}\n")

X = df[ALL_FEATURES]
y = df[TARGET]


# ---- 2. Stratified train/val split ----
# Stratify by both Converted and Industry using a composite key

stratify_key = df[TARGET].astype(str) + "_" + df["Industry"]

X_train, X_val, y_train, y_val = train_test_split(
    X, y,
    test_size=0.2,
    random_state=SEED,
    stratify=stratify_key,
)
print(f"Train: {len(X_train)}, Val: {len(X_val)}")
print(f"Train positive rate: {y_train.mean():.2%}")
print(f"Val positive rate:   {y_val.mean():.2%}\n")


# ---- 3. Preprocessing pipeline ----

# High-cardinality categoricals: impute missing → target encode
high_card_pipeline = Pipeline([
    ("impute", SimpleImputer(strategy="constant", fill_value="Unknown")),
    ("encode", TargetEncoder(smooth="auto", random_state=SEED)),
])

# Low-cardinality categoricals: impute missing → one-hot encode
low_card_pipeline = Pipeline([
    ("impute", SimpleImputer(strategy="most_frequent")),
    ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
])

preprocessor = ColumnTransformer([
    ("high_card", high_card_pipeline, HIGH_CARD_COLS),
    ("low_card", low_card_pipeline, LOW_CARD_COLS),
])


# ---- 4. Full pipeline (preprocessor + XGBoost) ----

# Compute class weight ratio for imbalanced target
neg_count = (y_train == 0).sum()
pos_count = (y_train == 1).sum()
scale_pos_weight = neg_count / pos_count
print(f"scale_pos_weight: {scale_pos_weight:.2f}")

full_pipeline = Pipeline([
    ("preprocess", preprocessor),
    ("model", XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        random_state=SEED,
        n_jobs=-1,
    )),
])


# ---- 5. Train ----

print("Training...")
full_pipeline.fit(X_train, y_train)
print("Done.\n")


# ---- 6. Evaluate on validation set ----

y_prob = full_pipeline.predict_proba(X_val)[:, 1]
y_pred = full_pipeline.predict(X_val)

auc_roc = roc_auc_score(y_val, y_prob)
pr_auc = average_precision_score(y_val, y_prob)

# Precision@Top-20%: treat the top 20% of scores as predicted positive
top_20_threshold = np.percentile(y_prob, 80)
y_pred_top20 = (y_prob >= top_20_threshold).astype(int)
precision_at_20 = precision_score(y_val, y_pred_top20)

print("Validation Metrics:")
print(f"  AUC-ROC:          {auc_roc:.4f}")
print(f"  PR-AUC:           {pr_auc:.4f}")
print(f"  Precision@Top-20%: {precision_at_20:.4f}")
print(f"\nClassification Report:\n{classification_report(y_val, y_pred)}")


# ---- 7. Save pipeline ----

with open(OUTPUT_PKL, "wb") as f:
    pickle.dump(full_pipeline, f)

print(f"Pipeline saved to {OUTPUT_PKL}")
print(f"File size: {os.path.getsize(OUTPUT_PKL) / 1024:.1f} KB")
