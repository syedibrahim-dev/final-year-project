"""
Inference module for fine-tuned classifiers.

Loads the 3 trained DistilBERT models and provides simple predict() functions
that Engine A and Engine B call as part of their ensemble.

Models are lazy-loaded on first use (~500ms load, ~30ms per prediction on CPU).
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

# Lazy-loaded singletons
_classifier1 = None  # objection detection
_classifier2 = None  # response quality
_classifier3 = None  # emotion + pressure


def _load_classifier(name: str):
    """Load a fine-tuned DistilBERT classifier."""
    model_path = os.path.join(MODEL_DIR, name)

    if not os.path.exists(model_path):
        logger.warning(f"Classifier model not found: {model_path}")
        return None, None, None

    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch

        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForSequenceClassification.from_pretrained(model_path)
        model.eval()

        # Load label mapping
        mapping_path = os.path.join(model_path, "label_mapping.json")
        if os.path.exists(mapping_path):
            with open(mapping_path, "r") as f:
                mapping = json.load(f)
            id2label = {int(k): v for k, v in mapping["id2label"].items()}
        else:
            id2label = model.config.id2label

        logger.info(f"Loaded classifier: {name} ({len(id2label)} labels)")
        return tokenizer, model, id2label

    except Exception as e:
        logger.error(f"Failed to load classifier {name}: {e}")
        return None, None, None


def _predict(tokenizer, model, id2label, text: str, top_k: int = 1, max_length: int = 128) -> list:
    """Run inference on a single text. Returns list of (label, confidence) tuples."""
    import torch

    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    probs = torch.softmax(outputs.logits, dim=-1)[0]

    top_indices = torch.topk(probs, min(top_k, len(probs))).indices.tolist()
    results = []
    for idx in top_indices:
        results.append((id2label[idx], round(float(probs[idx]), 4)))
    return results


# ── Public API ──────────────────────────────────────────────────────

def predict_objection(text: str) -> Dict[str, Any]:
    """
    Classify a prospect utterance for objection type.

    Returns:
        {
            "label": "objection_price" | "objection_timing" | ... | "not_objection",
            "confidence": float,
            "is_objection": bool,
            "all_scores": [(label, score), ...],
            "source": "fine_tuned_distilbert"
        }
    """
    global _classifier1
    if _classifier1 is None:
        _classifier1 = _load_classifier("classifier1_objection")

    tokenizer, model, id2label = _classifier1
    if tokenizer is None:
        return {"label": "unknown", "confidence": 0.0, "is_objection": False,
                "all_scores": [], "source": "unavailable"}

    results = _predict(tokenizer, model, id2label, text, top_k=3)
    top_label, top_conf = results[0]

    return {
        "label": top_label,
        "confidence": top_conf,
        "is_objection": top_label != "not_objection",
        "all_scores": results,
        "source": "fine_tuned_distilbert",
    }


def predict_handling(concern: str, response: str) -> Dict[str, Any]:
    """
    Classify response quality given a concern + response pair.

    Returns:
        {
            "label": "resolved" | "deflected" | "escalated",
            "confidence": float,
            "all_scores": [(label, score), ...],
            "source": "fine_tuned_distilbert"
        }
    """
    global _classifier2
    if _classifier2 is None:
        _classifier2 = _load_classifier("classifier2_handling")

    tokenizer, model, id2label = _classifier2
    if tokenizer is None:
        return {"label": "unknown", "confidence": 0.0,
                "all_scores": [], "source": "unavailable"}

    # Format as the model was trained: "Concern: ... Response: ..."
    combined = f"Concern: {concern} Response: {response}"
    results = _predict(tokenizer, model, id2label, combined, top_k=3)
    top_label, top_conf = results[0]

    return {
        "label": top_label,
        "confidence": top_conf,
        "all_scores": results,
        "source": "fine_tuned_distilbert",
    }


def predict_emotion(text: str) -> Dict[str, Any]:
    """
    Classify emotion/pressure level of an utterance.

    Returns:
        {
            "label": "positive" | "negative" | "neutral" | "empathetic" | "anxious"
                   | "consultative" | "urgent" | "demanding",
            "confidence": float,
            "is_pressure": bool,
            "pressure_type": str | None,
            "all_scores": [(label, score), ...],
            "source": "fine_tuned_distilbert"
        }
    """
    global _classifier3
    if _classifier3 is None:
        _classifier3 = _load_classifier("classifier3_emotion")

    tokenizer, model, id2label = _classifier3
    if tokenizer is None:
        return {"label": "neutral", "confidence": 0.0, "is_pressure": False,
                "pressure_type": None, "all_scores": [], "source": "unavailable"}

    results = _predict(tokenizer, model, id2label, text, top_k=3)
    top_label, top_conf = results[0]

    pressure_labels = {"consultative", "urgent", "demanding"}
    is_pressure = top_label in pressure_labels

    return {
        "label": top_label,
        "confidence": top_conf,
        "is_pressure": is_pressure,
        "pressure_type": top_label if is_pressure else None,
        "all_scores": results,
        "source": "fine_tuned_distilbert",
    }


# ── New Models (Step 3-5) ──────────────────────────────────────────

_outcome_predictor = None
_sales_state_model = None
_willingness_predictor = None


def predict_outcome(conversation_text: str) -> Dict[str, Any]:
    """
    Predict deal outcome from conversation text.
    Replaces SalesRLAgent PPO for conversion prediction.

    Returns:
        {
            "label": "converted" | "failed",
            "probability": float (0-1, probability of conversion),
            "confidence": float,
            "source": "fine_tuned_distilbert"
        }
    """
    global _outcome_predictor
    if _outcome_predictor is None:
        _outcome_predictor = _load_classifier("outcome_predictor")

    tokenizer, model, id2label = _outcome_predictor
    if tokenizer is None:
        return {"label": "unknown", "probability": 0.5, "confidence": 0.0,
                "source": "unavailable"}

    import torch
    inputs = tokenizer(conversation_text, return_tensors="pt", truncation=True,
                       max_length=256, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    probs = torch.softmax(outputs.logits, dim=-1)[0]

    # Get conversion probability (class 1 = converted)
    converted_idx = None
    for idx, label in id2label.items():
        if label == "converted":
            converted_idx = idx
            break

    if converted_idx is not None:
        conversion_prob = float(probs[converted_idx])
    else:
        conversion_prob = float(probs[1]) if len(probs) > 1 else 0.5

    predicted_idx = int(torch.argmax(probs))
    predicted_label = id2label.get(predicted_idx, "unknown")

    return {
        "label": predicted_label,
        "probability": round(conversion_prob, 4),
        "confidence": round(float(probs[predicted_idx]), 4),
        "source": "fine_tuned_distilbert",
    }


def predict_sales_state(conversation_window: str) -> Dict[str, Any]:
    """
    Predict buyer state from a conversation window (last 3 turns).

    Returns:
        {
            "state": "interest"|"trust"|"objection"|"evaluation"|"comparison"|"decision"|"drop_off_risk",
            "confidence": float,
            "all_states": [(state, score), ...],
            "source": "fine_tuned_distilbert"
        }
    """
    global _sales_state_model
    if _sales_state_model is None:
        _sales_state_model = _load_classifier("sales_state_model")

    tokenizer, model, id2label = _sales_state_model
    if tokenizer is None:
        return {"state": "neutral", "confidence": 0.0,
                "all_states": [], "source": "unavailable"}

    results = _predict(tokenizer, model, id2label, conversation_window, top_k=3, max_length=256)
    top_state, top_conf = results[0]

    return {
        "state": top_state,
        "confidence": top_conf,
        "all_states": results,
        "source": "fine_tuned_distilbert",
    }


def predict_willingness(conversation_window: str) -> Dict[str, Any]:
    """
    Predict buyer willingness from a conversation window.

    Returns:
        {
            "level": "engaged"|"neutral"|"disengaged",
            "confidence": float,
            "all_levels": [(level, score), ...],
            "source": "fine_tuned_distilbert"
        }
    """
    global _willingness_predictor
    if _willingness_predictor is None:
        _willingness_predictor = _load_classifier("willingness_predictor")

    tokenizer, model, id2label = _willingness_predictor
    if tokenizer is None:
        return {"level": "neutral", "confidence": 0.0,
                "all_levels": [], "source": "unavailable"}

    results = _predict(tokenizer, model, id2label, conversation_window, top_k=3, max_length=256)
    top_level, top_conf = results[0]

    return {
        "level": top_level,
        "confidence": top_conf,
        "all_levels": results,
        "source": "fine_tuned_distilbert",
    }
