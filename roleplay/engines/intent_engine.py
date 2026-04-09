"""
Engine A: Intent & Semantic Engine (DeBERTa NLI)

Uses cross-encoder NLI to classify:
  1. Objection Detection — is the prospect objecting?
  2. Objection Response  — did the rep resolve / deflect / escalate?
  3. Active Listening     — semantic similarity between prospect concern & rep reply

Model: cross-encoder/nli-deberta-v3-base (~400MB, runs on CPU)
Latency: ~15-30ms per classification on CPU
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Lazy-loaded globals
_nli_pipeline = None
_similarity_model = None
_similarity_tokenizer = None


def _get_nli_pipeline():
    """Lazy-load the NLI pipeline (first call downloads ~400MB)."""
    global _nli_pipeline
    if _nli_pipeline is None:
        logger.info("Loading DeBERTa NLI model (first time may download ~400MB)...")
        from transformers import pipeline
        _nli_pipeline = pipeline(
            "zero-shot-classification",
            model="cross-encoder/nli-deberta-v3-base",
            device=-1,  # CPU
        )
        logger.info("DeBERTa NLI model loaded!")
    return _nli_pipeline


def _get_similarity_models():
    """Lazy-load a sentence-transformers model for semantic similarity."""
    global _similarity_model, _similarity_tokenizer
    if _similarity_model is None:
        logger.info("Loading sentence similarity model...")
        from transformers import AutoTokenizer, AutoModel
        import torch

        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        _similarity_tokenizer = AutoTokenizer.from_pretrained(model_name)
        _similarity_model = AutoModel.from_pretrained(model_name)
        _similarity_model.eval()
        logger.info("Sentence similarity model loaded!")
    return _similarity_model, _similarity_tokenizer


def _mean_pooling(model_output, attention_mask):
    """Mean pooling of token embeddings."""
    import torch
    token_embeddings = model_output[0]
    input_mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask, 1) / torch.clamp(input_mask.sum(1), min=1e-9)


def compute_semantic_similarity(text_a: str, text_b: str) -> float:
    """
    Compute cosine similarity between two texts using MiniLM.
    Returns float 0.0–1.0.
    """
    import torch
    import torch.nn.functional as F

    model, tokenizer = _get_similarity_models()

    encoded = tokenizer(
        [text_a, text_b],
        padding=True, truncation=True, max_length=128, return_tensors="pt"
    )

    with torch.no_grad():
        output = model(**encoded)

    embeddings = _mean_pooling(output, encoded["attention_mask"])
    embeddings = F.normalize(embeddings, p=2, dim=1)
    similarity = F.cosine_similarity(embeddings[0].unsqueeze(0), embeddings[1].unsqueeze(0))
    return round(float(similarity.item()), 3)


def detect_objection(prospect_message: str) -> Tuple[bool, float]:
    """
    Detect if the prospect's message is an objection.

    Uses two-pass detection:
      Pass 1: Standard NLI classification (4 labels)
      Pass 2: Sales-specific objection patterns (keyword + NLI hybrid)

    Real B2B objections are often phrased as questions ("Isn't that expensive?")
    or hedging statements ("I'm not sure about the timeline"). The keyword pass
    catches these even when NLI classifies them as "question or inquiry".

    Returns:
        (is_objection: bool, confidence: float)
    """
    import re

    # Pass 1: NLI classification
    nli = _get_nli_pipeline()
    result = nli(
        prospect_message,
        candidate_labels=[
            "objection or concern about price, timeline, or capability",
            "question or request for information",
            "agreement or acceptance",
            "neutral statement",
        ],
        multi_label=False,
    )

    top_label = result["labels"][0]
    top_score = result["scores"][0]

    # Direct NLI detection
    if "objection" in top_label and top_score > 0.35:
        return True, round(top_score, 3)

    # Pass 2: Sales-specific objection keyword patterns
    # Many real objections are phrased as questions or hedging statements
    lower = prospect_message.lower()
    objection_signals = [
        r'\b(too expensive|too costly|steep|over budget|out of.*budget|can.t afford)\b',
        r'\b(not sure|not convinced|don.t think|hesitant|skeptical|concerned about)\b',
        r'\b(competitor|alternative|other option|someone else|better deal)\b',
        r'\b(not the right time|too soon|not ready|need to think|check with)\b',
        r'\b(hidden fees|total cost|what.s the catch|additional cost)\b',
        r'\b(how long|take.*weeks|take.*months|implementation.*time)\b',
        r'\b(not interested|don.t need|already have|works fine|happy with)\b',
    ]

    keyword_match = any(re.search(p, lower) for p in objection_signals)

    if keyword_match:
        # Keyword detected — re-run NLI with just objection vs non-objection
        binary_result = nli(
            prospect_message,
            candidate_labels=["raising a concern or pushback", "asking a genuine question"],
            multi_label=False,
        )
        objection_score = binary_result["scores"][0] if "concern" in binary_result["labels"][0] else binary_result["scores"][1]

        if objection_score > 0.3:
            return True, round(objection_score, 3)

    return False, round(top_score, 3)


def classify_objection_response(rep_message: str) -> Dict[str, Any]:
    """
    Classify how the rep handled an objection.
    
    Returns:
        {"handling": "resolved"|"deflected"|"escalated", "confidence": float}
    """
    nli = _get_nli_pipeline()
    result = nli(
        rep_message,
        candidate_labels=[
            "addressing the concern directly with a solution",
            "changing the subject or avoiding the concern",
            "making the situation worse or being aggressive",
        ],
        multi_label=False,
    )

    label_map = {
        "addressing the concern directly with a solution": "resolved",
        "changing the subject or avoiding the concern": "deflected",
        "making the situation worse or being aggressive": "escalated",
    }

    top_label = result["labels"][0]
    return {
        "handling": label_map.get(top_label, "deflected"),
        "confidence": round(result["scores"][0], 3),
    }


def analyze_active_listening(prospect_message: str, rep_response: str) -> float:
    """
    Score how well the rep's response addresses the prospect's concern.
    Uses semantic similarity (0.0–1.0, higher = better listening).
    """
    return compute_semantic_similarity(prospect_message, rep_response)


def run_intent_analysis(
    prospect_message: str,
    rep_message: str,
    previous_prospect_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full Engine A analysis for one turn.
    
    Args:
        prospect_message: The latest AI customer message
        rep_message: The trainee's response to it
        previous_prospect_message: The previous prospect message (for context)
    
    Returns:
        {
            "is_objection": bool,
            "objection_confidence": float,
            "objection_handling": str | None,
            "handling_confidence": float | None,
            "active_listening_score": float,
        }
    """
    result = {
        "is_objection": False,
        "objection_confidence": 0.0,
        "objection_handling": None,
        "handling_confidence": None,
        "active_listening_score": 0.0,
    }

    try:
        # 1. Check if prospect raised an objection — ENSEMBLE
        # Run both zero-shot NLI and fine-tuned classifier, combine results
        is_obj_nli, obj_conf_nli = detect_objection(prospect_message)

        # Fine-tuned classifier (if available)
        ft_objection = None
        try:
            from training.inference import predict_objection
            ft_objection = predict_objection(prospect_message)
        except Exception:
            pass  # fine-tuned model not available, use NLI only

        if ft_objection and ft_objection["source"] != "unavailable":
            ft_is_obj = ft_objection["is_objection"]
            ft_conf = ft_objection["confidence"]
            ft_label = ft_objection["label"]

            # Ensemble: if both agree, use combined confidence
            # If they disagree, trust fine-tuned (higher accuracy on this task)
            if ft_is_obj == is_obj_nli:
                result["is_objection"] = ft_is_obj
                result["objection_confidence"] = round((ft_conf + obj_conf_nli) / 2, 3)
            else:
                # Disagreement: trust fine-tuned if confidence > 0.6
                if ft_conf > 0.6:
                    result["is_objection"] = ft_is_obj
                    result["objection_confidence"] = ft_conf
                else:
                    result["is_objection"] = is_obj_nli
                    result["objection_confidence"] = obj_conf_nli

            result["objection_type"] = ft_label
            result["ensemble_agreement"] = ft_is_obj == is_obj_nli
        else:
            result["is_objection"] = is_obj_nli
            result["objection_confidence"] = obj_conf_nli

        # 2. If objection detected, classify the rep's response — ENSEMBLE
        if result["is_objection"]:
            # Zero-shot NLI handling
            nli_handling = classify_objection_response(rep_message)

            # Fine-tuned handling classifier
            ft_handling = None
            try:
                from training.inference import predict_handling
                ft_handling = predict_handling(prospect_message, rep_message)
            except Exception:
                pass

            if ft_handling and ft_handling["source"] != "unavailable":
                # Trust fine-tuned (81% vs 50% on this task)
                result["objection_handling"] = ft_handling["label"]
                result["handling_confidence"] = ft_handling["confidence"]
            else:
                result["objection_handling"] = nli_handling["handling"]
                result["handling_confidence"] = nli_handling["confidence"]

        # 3. Active listening score
        result["active_listening_score"] = analyze_active_listening(
            prospect_message, rep_message
        )

    except Exception as e:
        logger.warning(f"Intent engine error: {e}")

    return result
