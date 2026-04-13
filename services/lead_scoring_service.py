"""
LeadScoringService - loads the trained XGBoost pipeline and scores leads.

The pipeline (lead_scorer_pipeline.pkl) contains both the preprocessing
(TargetEncoder + OneHotEncoder) and the XGBoost model, so we just pass
a DataFrame and get probabilities back.
"""

import os
import pickle
import warnings
import pandas as pd
import numpy as np
from typing import Optional

# Silence sklearn's "trained on older version" warning — we handle the version
# delta explicitly via the compat shims below (_RemainderColsList stub +
# SimpleImputer._fill_dtype reconstruction). The warning is purely informational.
try:
    from sklearn.exceptions import InconsistentVersionWarning
    warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
except ImportError:
    pass

# ── sklearn compat shim ────────────────────────────────────────────────
# The lead_scorer_pipeline.pkl was trained with sklearn 1.6.x. Two
# incompatibilities exist when loading on sklearn 1.7+:
#
# 1. ColumnTransformer used a private `_RemainderColsList` (list subclass)
#    that was removed in 1.7+. Pickle can't resolve the class. Fix: register
#    a plain `list` subclass with the same name in the original module path.
#
# 2. SimpleImputer in 1.7+ uses an internal `_fill_dtype` attribute (set
#    during fit). Old pickles don't have it, causing AttributeError on
#    transform. Fix: walk the loaded pipeline and reconstruct it from
#    `statistics_.dtype`, which is what sklearn would have set anyway.
try:
    import sklearn.compose._column_transformer as _ct
    if not hasattr(_ct, "_RemainderColsList"):
        class _RemainderColsList(list):
            pass
        _ct._RemainderColsList = _RemainderColsList
except Exception:
    pass


def _patch_legacy_sklearn_objects(obj, _seen=None):
    """Recursively patch missing internal attributes on legacy sklearn objects."""
    if _seen is None:
        _seen = set()
    if id(obj) in _seen:
        return
    _seen.add(id(obj))

    cls_name = type(obj).__name__
    if cls_name == "SimpleImputer" and hasattr(obj, "statistics_") and not hasattr(obj, "_fill_dtype"):
        try:
            obj._fill_dtype = obj.statistics_.dtype
        except Exception:
            obj._fill_dtype = np.dtype("O")

    if hasattr(obj, "__dict__"):
        for v in list(obj.__dict__.values()):
            _patch_legacy_sklearn_objects(v, _seen)
    if isinstance(obj, (list, tuple)):
        for item in obj:
            _patch_legacy_sklearn_objects(item, _seen)
    if isinstance(obj, dict):
        for item in obj.values():
            _patch_legacy_sklearn_objects(item, _seen)
# ──────────────────────────────────────────────────────────────────────

# Features the model was trained on
MODEL_FEATURES = [
    "City", "Decision_Maker_Job_Title",
    "Industry", "Country", "Employee_Count", "Annual_Revenue_Range",
]

# Allocation thresholds — verified against the trained pipeline's calibration.
#
# Counterintuitive design:  high-confidence leads go to HUMAN review, not AI.
# Rationale: when the model is very confident a lead will convert, the deal
# is high-stakes — letting AI mishandle a mid-conversation objection on a
# whale account is more expensive than the time cost of human handling.
# AI handles the BULK of mid-tier leads where mistakes are cheap and
# personalisation at scale is the only way to engage them.
#
#   ≥ 0.60  → MANUAL_REVIEW   (high-value, human takes over)
#   0.10–0.60 → AI_OUTREACH    (mid-tier, AI engages with personalised email)
#   < 0.10  → NURTURE_CAMPAIGN (cold, low-priority drip campaign)
#
# Tuned on the synthetic CTGAN B2B dataset; revisit when retraining the model.
THRESHOLD_HIGH = 0.60
THRESHOLD_MED  = 0.10

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

    # Patch legacy sklearn internals (see compat shim above)
    _patch_legacy_sklearn_objects(_pipeline)

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


MIN_FEATURES_FOR_MODEL = 2  # Lowered from 3 — pipeline handles "Unknown" gracefully
                            # for sparse leads, and real B2B exports often have only
                            # 2-3 fields filled (company name + email + maybe industry).


def predict_win_probability(lead_data: dict) -> dict:
    """
    Score a single lead.

    Args:
        lead_data: dict with keys matching the model's feature columns.
                   Missing keys are filled with "Unknown".

    Returns:
        dict with 'win_probability' (float) and 'allocation_decision' (str).

    Strategy for sparse leads:
      • ≥2 real features → use the model (trained encoders handle "Unknown" tokens)
      • <2 real features → return fallback 0.30 (NURTURE_CAMPAIGN)
        Rationale: testing showed the model returns ~0.51 for ALL-Unknown rows,
        which would erroneously route empty leads to AI_OUTREACH. The fallback
        prevents wasted LLM/SMTP cost on no-information leads.
    """
    pipeline = load_pipeline()

    # Count how many usable features the lead actually has
    present_features = sum(
        1 for f in MODEL_FEATURES
        if f in lead_data and lead_data[f] and str(lead_data[f]).strip() not in ("", "nan", "None", "Unknown")
    )

    # Too sparse to trust the model — default to nurture
    if present_features < MIN_FEATURES_FOR_MODEL or pipeline is None:
        return {
            "win_probability": 0.30,
            "allocation_decision": "NURTURE_CAMPAIGN",
            "features_available": present_features,
            "used_model": False,
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
            "used_model": False,
        }

    return {
        "win_probability": round(probability, 4),
        "allocation_decision": get_allocation_decision(probability),
        "features_available": present_features,
        "used_model": True,
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

        if present < MIN_FEATURES_FOR_MODEL:
            results.append({
                "win_probability": 0.30,
                "allocation_decision": "NURTURE_CAMPAIGN",
                "features_available": present,
                "used_model": False,
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
                    "used_model": True,
                }
        except Exception as e:
            import traceback
            print(f"Batch prediction failed: {e}\n{traceback.format_exc()}")
            for idx in scorable_indices:
                results[idx] = {
                    "win_probability": 0.30,
                    "allocation_decision": "NURTURE_CAMPAIGN",
                    "features_available": 0,
                    "used_model": False,
                }

    return results
