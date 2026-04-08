"""
LeadScoringService - loads the trained XGBoost pipeline and scores leads.

The pipeline (lead_scorer_pipeline.pkl) contains both the preprocessing
(TargetEncoder + OneHotEncoder) and the XGBoost model, so we just pass
a DataFrame and get probabilities back.
"""

import os
import pickle
import pandas as pd
import numpy as np
from typing import Optional

# Features the model was trained on
MODEL_FEATURES = [
    "City", "Decision_Maker_Job_Title",
    "Industry", "Country", "Employee_Count", "Annual_Revenue_Range",
]

THRESHOLD_HIGH = 0.60   # >= 70%: MANUAL_REVIEW (Human handoff because it's too high value for AI)
THRESHOLD_MED = 0.10    # 10-69%: AI_OUTREACH (AI engages the mid-level leads)
                        # < 10%: NURTURE_CAMPAIGN (Low priority/low confidence)

# Path to the trained pipeline
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lead_scorer_pipeline.pkl")

# Global pipeline instance (loaded once)
_pipeline = None


def load_pipeline():
    """Load the trained pipeline from disk. Called once at app startup."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    if not os.path.exists(MODEL_PATH):
        print(f"WARNING: Lead scoring model not found at {MODEL_PATH}")
        return None

    with open(MODEL_PATH, "rb") as f:
        _pipeline = pickle.load(f)

    print(f"Lead scoring pipeline loaded from {MODEL_PATH}")
    return _pipeline


def get_allocation_decision(probability: float) -> str:
    """Map win probability to an allocation decision."""
    if probability >= THRESHOLD_HIGH:
        return "MANUAL_REVIEW"
    elif probability >= THRESHOLD_MED:
        return "AI_OUTREACH"
    else:
        return "NURTURE_CAMPAIGN"


def predict_win_probability(lead_data: dict) -> dict:
    """
    Score a single lead.

    Args:
        lead_data: dict with keys matching the model's feature columns.
                   Missing keys are filled with "Unknown".

    Returns:
        dict with 'win_probability' (float) and 'allocation_decision' (str).
    """
    pipeline = load_pipeline()

    # Count how many usable features the lead actually has
    present_features = sum(
        1 for f in MODEL_FEATURES
        if f in lead_data and lead_data[f] and str(lead_data[f]).strip() not in ("", "nan", "None", "Unknown")
    )

    # If fewer than 3 real features, don't trust the model — default to low priority
    if present_features < 3 or pipeline is None:
        return {
            "win_probability": 0.30,
            "allocation_decision": "NURTURE_CAMPAIGN",
            "features_available": present_features,
        }

    # Build a single-row DataFrame with all required columns
    row = {}
    for col in MODEL_FEATURES:
        val = lead_data.get(col)
        if val is None or str(val).strip() in ("", "nan", "None"):
            row[col] = "Unknown"
        else:
            row[col] = str(val).strip()

    df = pd.DataFrame([row])

    try:
        probability = float(pipeline.predict_proba(df)[:, 1][0])
    except Exception as e:
        print(f"Model prediction failed: {e}")
        return {
            "win_probability": 0.30,
            "allocation_decision": "NURTURE_CAMPAIGN",
            "features_available": present_features,
        }

    return {
        "win_probability": round(probability, 4),
        "allocation_decision": get_allocation_decision(probability),
        "features_available": present_features,
    }


def score_leads_batch(leads: list[dict]) -> list[dict]:
    """
    Score multiple leads at once for better performance.
    Uses a single predict_proba call instead of one per lead.
    """
    pipeline = load_pipeline()
    results = []

    if pipeline is None:
        return [
            {"win_probability": 0.30, "allocation_decision": "NURTURE_CAMPAIGN", "features_available": 0}
            for _ in leads
        ]

    # Separate leads into scorable and fallback
    scorable_indices = []
    rows = []

    for i, lead_data in enumerate(leads):
        present = sum(
            1 for f in MODEL_FEATURES
            if f in lead_data and lead_data[f] and str(lead_data[f]).strip() not in ("", "nan", "None", "Unknown")
        )

        if present < 3:
            results.append({
                "win_probability": 0.30,
                "allocation_decision": "NURTURE_CAMPAIGN",
                "features_available": present,
            })
        else:
            row = {}
            for col in MODEL_FEATURES:
                val = lead_data.get(col)
                if val is None or str(val).strip() in ("", "nan", "None"):
                    row[col] = "Unknown"
                else:
                    row[col] = str(val).strip()

            scorable_indices.append(i)
            rows.append(row)
            results.append(None)  # placeholder

    # Batch predict scorable leads
    if rows:
        df = pd.DataFrame(rows)

        try:
            probabilities = pipeline.predict_proba(df)[:, 1]
            
            for idx, prob in zip(scorable_indices, probabilities):
                p = round(float(prob), 4)
                results[idx] = {
                    "win_probability": p,
                    "allocation_decision": get_allocation_decision(p),
                    "features_available": sum(
                        1 for f in MODEL_FEATURES
                        if f in leads[idx] and leads[idx][f] and str(leads[idx][f]).strip() not in ("", "nan", "None", "Unknown")
                    ),
                }
        except Exception as e:
            import traceback
            print(f"Batch prediction failed: {e}\n{traceback.format_exc()}")
            for idx in scorable_indices:
                results[idx] = {
                    "win_probability": 0.30,
                    "allocation_decision": "NURTURE_CAMPAIGN",
                    "features_available": 0,
                }

    return results
