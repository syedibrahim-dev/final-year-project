"""
Engine B: Emotion & Tone Engine (Emotion-RoBERTa)

Uses transformer classifiers for:
  1. Empathy Detection — classify prospect emotion, check if rep responds empathetically
  2. Pressure Level    — classify rep's tone as consultative/urgent/demanding

Models:
  - j-hartmann/emotion-english-distilroberta-base  (7 emotions, ~250MB)
  - SamLowe/roberta-base-go_emotions               (28 emotions, ~300MB)

Latency: ~10-20ms per classification on CPU
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Lazy-loaded globals
_emotion7_pipeline = None
_go_emotions_pipeline = None


def _get_emotion7_pipeline():
    """Lazy-load the 7-class emotion classifier."""
    global _emotion7_pipeline
    if _emotion7_pipeline is None:
        logger.info("Loading Emotion-RoBERTa (7-class) model...")
        from transformers import pipeline
        _emotion7_pipeline = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            top_k=None,  # return all labels with scores
            device=-1,   # CPU
        )
        logger.info("Emotion-RoBERTa (7-class) loaded!")
    return _emotion7_pipeline


def _get_go_emotions_pipeline():
    """Lazy-load the 28-class GoEmotions classifier."""
    global _go_emotions_pipeline
    if _go_emotions_pipeline is None:
        logger.info("Loading GoEmotions-RoBERTa (28-class) model...")
        from transformers import pipeline
        _go_emotions_pipeline = pipeline(
            "text-classification",
            model="SamLowe/roberta-base-go_emotions",
            top_k=5,  # top 5 emotions
            device=-1,
        )
        logger.info("GoEmotions-RoBERTa loaded!")
    return _go_emotions_pipeline


# ── Emotion categories relevant to sales ─────────────────────────────

# Prospect emotions that signal the rep should show empathy
NEGATIVE_PROSPECT_EMOTIONS = {"anger", "disgust", "fear", "sadness", "frustration",
                                "annoyance", "disappointment", "confusion"}

# Rep emotions that indicate empathetic response
# Note: "neutral" removed — being neutral when prospect is upset is NOT empathy.
# A genuinely empathetic response shows caring, approval, or gratitude, not just absence of negativity.
EMPATHETIC_REP_EMOTIONS = {"caring", "approval", "admiration", "gratitude",
                           "optimism", "joy"}

# Rep emotions that indicate pushy/aggressive behaviour
PUSHY_REP_EMOTIONS = {"anger", "annoyance", "disapproval", "disgust"}


def classify_emotion_7class(text: str) -> Dict[str, float]:
    """
    Classify text into 7 basic emotions using distilroberta.
    Returns dict of {emotion: score} for all 7 classes.
    
    Labels: anger, disgust, fear, joy, neutral, sadness, surprise
    """
    pipe = _get_emotion7_pipeline()
    result = pipe(text[:512])  # truncate to model max
    
    if isinstance(result, list) and len(result) > 0:
        if isinstance(result[0], list):
            result = result[0]
        return {item["label"]: round(item["score"], 3) for item in result}
    return {}


def classify_go_emotions(text: str) -> List[Dict[str, Any]]:
    """
    Classify text using GoEmotions (28 fine-grained labels).
    Returns top 5 emotions with scores.
    
    Labels include: admiration, amusement, anger, annoyance, approval, caring,
    confusion, curiosity, desire, disappointment, disapproval, disgust,
    embarrassment, excitement, fear, gratitude, grief, joy, love, nervousness,
    neutral, optimism, pride, realization, relief, remorse, sadness, surprise
    """
    pipe = _get_go_emotions_pipeline()
    result = pipe(text[:512])
    
    if isinstance(result, list) and len(result) > 0:
        if isinstance(result[0], list):
            result = result[0]
        return [{"label": item["label"], "score": round(item["score"], 3)} for item in result]
    return []


def detect_empathy(
    prospect_message: str,
    rep_message: str,
) -> Dict[str, Any]:
    """
    Detect whether the rep responded empathetically to the prospect's emotion.
    
    Process:
      1. Classify prospect's emotion (7-class for simplicity)
      2. Classify rep's emotion (GoEmotions for granularity)
      3. If prospect shows negative emotion → check if rep shows empathetic response
    
    Returns:
        {
            "prospect_emotion": str,           # dominant emotion
            "prospect_emotion_scores": dict,   # all 7 scores
            "rep_emotions": list,              # top 5 GoEmotions
            "rep_dominant_emotion": str,        # top emotion
            "prospect_needs_empathy": bool,     # was prospect frustrated/sad/angry?
            "rep_showed_empathy": bool,         # did rep respond empathetically?
            "empathy_score": float,             # 0.0-1.0
        }
    """
    # 1. Prospect emotion (7-class)
    prospect_emotions = classify_emotion_7class(prospect_message)
    prospect_dominant = max(prospect_emotions, key=prospect_emotions.get) if prospect_emotions else "neutral"
    
    # 2. Rep emotions (GoEmotions — more granular)
    rep_emotions = classify_go_emotions(rep_message)
    rep_dominant = rep_emotions[0]["label"] if rep_emotions else "neutral"
    
    # 3. Does prospect need empathy?
    needs_empathy = prospect_dominant in NEGATIVE_PROSPECT_EMOTIONS
    
    # 4. Did the rep respond empathetically?
    showed_empathy = False
    empathy_score = 0.5  # neutral default
    
    if needs_empathy:
        # Check rep's emotions — require empathy to be DOMINANT, not buried
        rep_emotion_labels = {e["label"] for e in rep_emotions[:3]}
        top_is_empathetic = rep_dominant in EMPATHETIC_REP_EMOTIONS
        has_empathetic_in_top3 = bool(rep_emotion_labels & EMPATHETIC_REP_EMOTIONS)
        is_pushy = bool(rep_emotion_labels & PUSHY_REP_EMOTIONS)

        # Also check for explicit empathy keywords (GoEmotions misses sales-specific phrases)
        import re
        rep_lower = rep_message.lower()
        has_empathy_words = bool(re.search(
            r'\b(i understand|i hear you|that makes sense|valid point|fair point|appreciate|i get that)\b',
            rep_lower
        ))

        if top_is_empathetic or has_empathy_words:
            # Strong empathy: dominant emotion is empathetic OR explicit verbal empathy
            empathy_score = 0.8 + (0.2 * rep_emotions[0]["score"] if rep_emotions else 0)
            showed_empathy = True
        elif has_empathetic_in_top3 and not is_pushy:
            # Weak empathy: present but not dominant — partial credit
            empathy_score = 0.55
            showed_empathy = True
        elif is_pushy:
            empathy_score = 0.15
            showed_empathy = False
        else:
            empathy_score = 0.35  # missed opportunity to show empathy
            showed_empathy = False
    else:
        # Prospect is neutral/positive — use keyword detection alongside GoEmotions
        # GoEmotions was trained on Reddit comments and may miss sales-specific empathy
        # signals like "I understand", "I hear you", "that makes sense"
        import re
        rep_lower = rep_message.lower()
        empathy_keywords = [
            r'\b(i understand|i hear you|that makes sense|i appreciate|i get that)\b',
            r'\b(valid point|fair point|good point|absolutely|of course)\b',
            r'\b(help you|work with you|find.*solution|walk you through)\b',
        ]
        has_empathy_keywords = any(re.search(p, rep_lower) for p in empathy_keywords)

        rep_emotion_labels = {e["label"] for e in rep_emotions[:3]}
        showed_empathy_emotion = rep_dominant in EMPATHETIC_REP_EMOTIONS or rep_dominant == "neutral"

        if has_empathy_keywords and showed_empathy_emotion:
            empathy_score = 0.85  # strong: both keywords and emotion detected
            showed_empathy = True
        elif has_empathy_keywords:
            empathy_score = 0.75  # keywords present, GoEmotions didn't catch it
            showed_empathy = True
        elif showed_empathy_emotion:
            empathy_score = 0.65  # emotion detected but no explicit verbal signals
            showed_empathy = True
        else:
            empathy_score = 0.4   # neither keywords nor empathetic emotion
            showed_empathy = False
    
    return {
        "prospect_emotion": prospect_dominant,
        "prospect_emotion_scores": prospect_emotions,
        "rep_emotions": rep_emotions[:5],
        "rep_dominant_emotion": rep_dominant,
        "prospect_needs_empathy": needs_empathy,
        "rep_showed_empathy": showed_empathy,
        "empathy_score": round(min(1.0, empathy_score), 3),
    }


def classify_pressure_level(rep_message: str) -> Dict[str, Any]:
    """
    Classify the rep's communication pressure level.
    Uses GoEmotions to detect pushy vs consultative tone.
    
    Returns:
        {
            "pressure_level": "consultative" | "urgent" | "demanding",
            "pressure_score": float (0.0 = very consultative, 1.0 = very pushy),
            "contributing_emotions": list
        }
    """
    rep_emotions = classify_go_emotions(rep_message)
    
    if not rep_emotions:
        return {"pressure_level": "consultative", "pressure_score": 0.0, "contributing_emotions": []}
    
    emotion_labels = {e["label"]: e["score"] for e in rep_emotions}
    
    # Pushy indicators
    pushy_score = sum(
        emotion_labels.get(e, 0) for e in ["anger", "annoyance", "disapproval", "disgust"]
    )
    
    # Consultative indicators
    consultative_score = sum(
        emotion_labels.get(e, 0) for e in ["caring", "approval", "curiosity", "neutral", "optimism"]
    )
    
    # Urgency indicators
    urgency_score = sum(
        emotion_labels.get(e, 0) for e in ["desire", "excitement", "nervousness"]
    )
    
    # Determine level from GoEmotions
    if pushy_score > 0.3:
        go_level = "demanding"
        go_pressure = min(1.0, 0.5 + pushy_score)
    elif urgency_score > 0.3:
        go_level = "urgent"
        go_pressure = min(0.7, 0.3 + urgency_score)
    else:
        go_level = "consultative"
        go_pressure = max(0.0, 0.3 - consultative_score)

    # ENSEMBLE: Fine-tuned pressure classifier (99-100% on pressure labels)
    ft_result = None
    try:
        from training.inference import predict_emotion
        ft_result = predict_emotion(rep_message)
    except Exception:
        pass

    if ft_result and ft_result["source"] != "unavailable" and ft_result["is_pressure"]:
        # Fine-tuned model detected a pressure label with high confidence
        ft_level = ft_result["pressure_type"]
        ft_conf = ft_result["confidence"]

        if ft_conf > 0.7:
            # Trust fine-tuned (it's 99-100% on pressure detection)
            level = ft_level
            pressure = {"consultative": 0.0, "urgent": 0.5, "demanding": 0.9}.get(ft_level, go_pressure)
        else:
            # Low confidence — fall back to GoEmotions
            level = go_level
            pressure = go_pressure
    else:
        level = go_level
        pressure = go_pressure

    return {
        "pressure_level": level,
        "pressure_score": round(pressure, 3),
        "contributing_emotions": rep_emotions[:3],
    }


def run_emotion_analysis(
    prospect_message: str,
    rep_message: str,
) -> Dict[str, Any]:
    """
    Full Engine B analysis for one turn.
    
    Args:
        prospect_message: The latest AI customer message
        rep_message: The trainee's response
    
    Returns:
        {
            "empathy": { ... },      # empathy detection results
            "pressure": { ... },     # pressure level results
        }
    """
    result = {
        "empathy": {},
        "pressure": {},
    }

    try:
        result["empathy"] = detect_empathy(prospect_message, rep_message)
    except Exception as e:
        logger.warning(f"Empathy detection failed: {e}")
        result["empathy"] = {
            "prospect_emotion": "unknown",
            "empathy_score": 0.5,
            "rep_showed_empathy": False,
        }

    try:
        result["pressure"] = classify_pressure_level(rep_message)
    except Exception as e:
        logger.warning(f"Pressure classification failed: {e}")
        result["pressure"] = {
            "pressure_level": "consultative",
            "pressure_score": 0.0,
        }

    return result
