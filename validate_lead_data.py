"""
Module 5a - Synthetic Data Validation

Validates whether the CTGAN-generated B2B lead data is suitable
for training an XGBoost lead scoring model.

Run in Colab after generate_lead_data.py has produced b2b_leads_synthetic.csv.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
from sklearn.metrics import roc_auc_score, classification_report

CSV_PATH = "b2b_leads_synthetic.csv"

# Columns that are identifiers, not features
ID_COLS = ["Company_Name", "Email"]

# Columns used as model features
FEATURE_COLS = [
    "Decision_Maker_Job_Title", "Industry", "Country",
    "City", "Employee_Count", "Annual_Revenue_Range"
]
TARGET = "Converted"


def load_data():
    df = pd.read_csv(CSV_PATH)
    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}\n")
    return df


# ---- 1. Basic stats ----

def check_basics(df):
    print("=" * 50)
    print("1. BASIC STATS")
    print("=" * 50)

    print(f"\nShape: {df.shape}")
    print(f"Null counts:\n{df.isnull().sum()}\n")

    print(f"Target distribution:")
    counts = df[TARGET].value_counts()
    for val, count in counts.items():
        print(f"  {val}: {count} ({count/len(df):.1%})")
    print(f"  Positive rate: {df[TARGET].mean():.2%}")

    target_ok = 0.15 <= df[TARGET].mean() <= 0.40
    print(f"  Within 15-40% range: {'YES' if target_ok else 'NO - investigate'}\n")


# ---- 2. Feature distributions ----

def check_distributions(df):
    print("=" * 50)
    print("2. FEATURE DISTRIBUTIONS")
    print("=" * 50)

    for col in FEATURE_COLS:
        vc = df[col].value_counts()
        print(f"\n{col} ({vc.shape[0]} unique values):")
        for val, count in vc.head(10).items():
            print(f"  {val}: {count} ({count/len(df):.1%})")
        if len(vc) > 10:
            print(f"  ... and {len(vc) - 10} more")


# ---- 3. Feature-target correlation ----

def check_feature_target(df):
    print("\n" + "=" * 50)
    print("3. CONVERSION RATE BY FEATURE")
    print("=" * 50)

    fig, axes = plt.subplots(3, 3, figsize=(18, 14))
    axes = axes.flatten()

    for i, col in enumerate(FEATURE_COLS):
        conv_rates = df.groupby(col)[TARGET].mean().sort_values(ascending=False)

        print(f"\n{col}:")
        for val, rate in conv_rates.items():
            n = len(df[df[col] == val])
            print(f"  {val}: {rate:.1%} (n={n})")

        # Check variance - if all rates are within 2%, the feature has no signal
        spread = conv_rates.max() - conv_rates.min()
        print(f"  Spread: {spread:.1%} {'(weak signal)' if spread < 0.05 else '(has signal)'}")

        # Plot
        if i < len(axes):
            top_n = conv_rates.head(15)
            ax = axes[i]
            top_n.plot(kind="barh", ax=ax, color="steelblue")
            ax.set_title(f"{col} (spread: {spread:.1%})")
            ax.set_xlabel("Conversion Rate")

    # Hide unused subplots
    for j in range(len(FEATURE_COLS), len(axes)):
        axes[j].set_visible(False)

    plt.tight_layout()
    plt.savefig("feature_target_correlation.png", dpi=100)
    plt.show()
    print("\nSaved: feature_target_correlation.png")


# ---- 4. Cross-feature correlations ----

def check_cross_correlations(df):
    print("\n" + "=" * 50)
    print("4. CROSS-FEATURE CORRELATIONS")
    print("=" * 50)

    # Employee count vs Job title
    ct = pd.crosstab(df["Employee_Count"], df["Decision_Maker_Job_Title"], normalize="columns")
    print("\nEmployee_Count distribution by Job Title (top 5 titles):")
    top_titles = df["Decision_Maker_Job_Title"].value_counts().head(5).index
    print(ct[top_titles].round(2).to_string())

    # Revenue vs Employee count
    ct2 = pd.crosstab(df["Annual_Revenue_Range"], df["Employee_Count"], normalize="columns")
    print(f"\nRevenue distribution by Employee Count:")
    print(ct2.round(2).to_string())


# ---- 5. Sanity-check XGBoost ----

def sanity_check_model(df):
    print("\n" + "=" * 50)
    print("5. SANITY-CHECK XGBOOST")
    print("=" * 50)

    # Encode categoricals
    df_encoded = df[FEATURE_COLS + [TARGET]].copy()
    encoders = {}
    for col in FEATURE_COLS:
        le = LabelEncoder()
        df_encoded[col] = le.fit_transform(df_encoded[col].astype(str))
        encoders[col] = le

    X = df_encoded[FEATURE_COLS]
    y = df_encoded[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train, verbose=False)

    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = model.predict(X_test)
    auc = roc_auc_score(y_test, y_prob)

    print(f"\nTest AUC: {auc:.4f}")
    if auc < 0.55:
        print("WARNING: AUC near 0.5 means features have almost no predictive signal.")
        print("The synthetic data likely lost feature-target correlations during CTGAN training.")
    elif auc < 0.65:
        print("Moderate signal. Acceptable for a demo but could be improved.")
    else:
        print("Good signal. Data is suitable for training the lead scoring model.")

    print(f"\nClassification Report:\n{classification_report(y_test, y_pred)}")

    # Feature importance
    importances = pd.Series(model.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
    print("Feature Importances:")
    for feat, imp in importances.items():
        print(f"  {feat}: {imp:.4f}")

    fig, ax = plt.subplots(figsize=(8, 4))
    importances.plot(kind="barh", ax=ax, color="steelblue")
    ax.set_title(f"XGBoost Feature Importance (AUC={auc:.3f})")
    ax.set_xlabel("Importance")
    plt.tight_layout()
    plt.savefig("feature_importance.png", dpi=100)
    plt.show()
    print("Saved: feature_importance.png")


# ---- Main ----

if __name__ == "__main__":
    df = load_data()
    check_basics(df)
    check_distributions(df)
    check_feature_target(df)
    check_cross_correlations(df)
    sanity_check_model(df)
