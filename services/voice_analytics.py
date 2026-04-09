"""
Voice Analytics Service — Whisper-based STT + sales coaching metrics.

Replaces browser Web Speech API with faster-whisper for:
1. More accurate transcription
2. Word-level timestamps → pause detection, speaking pace
3. Confidence scores → hesitation detection
4. Filler word counting

Sales coaching metrics (Gong Labs research-backed):
- Words per minute (optimal B2B range: 130-150 WPM)
- Filler word ratio (target: <3%)
- Pause frequency (natural pauses improve trust)
- Confidence score (low confidence = hesitation)
"""

import os
import re
import logging
import tempfile
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-loaded model singleton
_whisper_model = None
_model_size = "base"  # base = 74M params, fast + accurate enough

# Filler words common in B2B sales conversations
FILLER_WORDS = {
    "um", "uh", "uhh", "umm", "hmm", "hm",
    "like", "you know", "i mean", "basically",
    "actually", "literally", "sort of", "kind of",
    "right", "so", "well", "anyway",
}

# Single-word fillers for fast matching
SINGLE_FILLERS = {w for w in FILLER_WORDS if " " not in w}
# Multi-word fillers
MULTI_FILLERS = [w for w in FILLER_WORDS if " " in w]


def _load_model():
    """Load Whisper model (lazy, ~500ms first load)."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info(f"Loading Whisper {_model_size} model (CPU)...")
        _whisper_model = WhisperModel(
            _model_size,
            device="cpu",
            compute_type="int8",  # Fastest on CPU
        )
        logger.info("Whisper model loaded")
    return _whisper_model


def transcribe_audio(audio_path: str) -> Dict[str, Any]:
    """
    Transcribe audio file and extract voice analytics.

    Args:
        audio_path: Path to audio file (wav, webm, mp3, etc.)

    Returns:
        {
            "text": str,              # Full transcription
            "words": [...],           # Word-level details
            "metrics": {
                "duration_seconds": float,
                "word_count": int,
                "words_per_minute": float,
                "filler_count": int,
                "filler_ratio": float,
                "filler_words_found": [str],
                "pause_count": int,
                "avg_pause_duration": float,
                "longest_pause": float,
                "confidence_avg": float,
                "confidence_min": float,
                "hesitation_count": int,
            },
            "coaching": {
                "pace_feedback": str,
                "filler_feedback": str,
                "confidence_feedback": str,
                "pause_feedback": str,
            }
        }
    """
    model = _load_model()

    # Transcribe with word timestamps
    segments, info = model.transcribe(
        audio_path,
        language="en",
        word_timestamps=True,
        vad_filter=True,  # Filter out silence
    )

    # Collect all words with timestamps
    words = []
    full_text_parts = []

    for segment in segments:
        full_text_parts.append(segment.text.strip())
        if segment.words:
            for word in segment.words:
                words.append({
                    "word": word.word.strip(),
                    "start": round(word.start, 3),
                    "end": round(word.end, 3),
                    "confidence": round(word.probability, 4),
                })

    full_text = " ".join(full_text_parts).strip()
    duration = info.duration if info.duration else (words[-1]["end"] if words else 0)

    # Calculate metrics
    metrics = _calculate_metrics(words, full_text, duration)
    coaching = _generate_coaching(metrics)

    return {
        "text": full_text,
        "words": words,
        "duration": round(duration, 2),
        "metrics": metrics,
        "coaching": coaching,
    }


def _calculate_metrics(words: List[Dict], text: str, duration: float) -> Dict[str, Any]:
    """Calculate voice analytics metrics from word-level data."""
    word_count = len(words)

    if word_count == 0 or duration == 0:
        return {
            "duration_seconds": 0,
            "word_count": 0,
            "words_per_minute": 0,
            "filler_count": 0,
            "filler_ratio": 0,
            "filler_words_found": [],
            "pause_count": 0,
            "avg_pause_duration": 0,
            "longest_pause": 0,
            "confidence_avg": 0,
            "confidence_min": 0,
            "hesitation_count": 0,
        }

    # ── Words per minute ──
    wpm = round((word_count / duration) * 60, 1)

    # ── Filler words ──
    lower_text = text.lower()
    filler_count = 0
    fillers_found = []

    # Multi-word fillers
    for filler in MULTI_FILLERS:
        count = lower_text.count(filler)
        if count > 0:
            filler_count += count
            fillers_found.extend([filler] * count)

    # Single-word fillers
    for w in words:
        word_lower = w["word"].lower().strip(".,!?")
        if word_lower in SINGLE_FILLERS:
            filler_count += 1
            fillers_found.append(word_lower)

    filler_ratio = round(filler_count / max(1, word_count), 4)

    # ── Pauses (gaps > 0.5s between words) ──
    pauses = []
    for i in range(1, len(words)):
        gap = words[i]["start"] - words[i - 1]["end"]
        if gap > 0.5:  # 500ms threshold
            pauses.append(round(gap, 3))

    pause_count = len(pauses)
    avg_pause = round(sum(pauses) / max(1, len(pauses)), 3)
    longest_pause = round(max(pauses), 3) if pauses else 0

    # ── Confidence ──
    confidences = [w["confidence"] for w in words]
    conf_avg = round(sum(confidences) / len(confidences), 4)
    conf_min = round(min(confidences), 4)

    # ── Hesitations (confidence < 0.5 or very short words followed by pause) ──
    hesitation_count = sum(1 for w in words if w["confidence"] < 0.5)

    # ── Speech Rate Variability (WPM per segment) ──
    # Split words into segments of ~5 words and compute per-segment WPM.
    # Low std dev = monotone/flat pace; good speakers vary speed for emphasis.
    segment_wpms = []
    seg_size = 5
    for i in range(0, word_count - seg_size + 1, seg_size):
        seg = words[i : i + seg_size]
        seg_dur = seg[-1]["end"] - seg[0]["start"]
        if seg_dur > 0.1:
            seg_wpm = round((len(seg) / seg_dur) * 60, 1)
            segment_wpms.append(seg_wpm)

    if len(segment_wpms) >= 2:
        import statistics
        pace_std_dev = round(statistics.stdev(segment_wpms), 1)
        pace_variability = "good" if pace_std_dev >= 15 else ("flat" if pace_std_dev < 8 else "moderate")
    else:
        pace_std_dev = 0.0
        pace_variability = "insufficient_data"

    return {
        "duration_seconds": round(duration, 2),
        "word_count": word_count,
        "words_per_minute": wpm,
        "filler_count": filler_count,
        "filler_ratio": filler_ratio,
        "filler_words_found": fillers_found[:10],  # Cap for response size
        "pause_count": pause_count,
        "avg_pause_duration": avg_pause,
        "longest_pause": longest_pause,
        "confidence_avg": conf_avg,
        "confidence_min": conf_min,
        "hesitation_count": hesitation_count,
        "pace_std_dev": pace_std_dev,
        "pace_variability": pace_variability,
    }


def _generate_coaching(metrics: Dict) -> Dict[str, str]:
    """Generate sales-specific coaching feedback from voice metrics."""
    coaching = {}

    # ── Pace feedback (Gong Labs: 130-150 WPM optimal for B2B) ──
    wpm = metrics["words_per_minute"]
    if wpm == 0:
        coaching["pace_feedback"] = "No speech detected."
    elif wpm < 110:
        coaching["pace_feedback"] = f"Speaking too slowly ({wpm} WPM). Aim for 130-150 WPM to maintain engagement."
    elif wpm < 130:
        coaching["pace_feedback"] = f"Slightly slow ({wpm} WPM). Pick up the pace slightly for more energy."
    elif wpm <= 160:
        coaching["pace_feedback"] = f"Great pace ({wpm} WPM). This is the optimal range for B2B conversations."
    elif wpm <= 180:
        coaching["pace_feedback"] = f"Slightly fast ({wpm} WPM). Slow down a bit to let key points land."
    else:
        coaching["pace_feedback"] = f"Speaking too fast ({wpm} WPM). Slow down — fast speech reduces trust in sales."

    # ── Filler feedback (target: <3% of words) ──
    ratio_pct = metrics["filler_ratio"] * 100
    if ratio_pct == 0:
        coaching["filler_feedback"] = "No filler words detected. Clean delivery."
    elif ratio_pct < 3:
        coaching["filler_feedback"] = f"Low filler usage ({ratio_pct:.1f}%). Good conversational flow."
    elif ratio_pct < 6:
        coaching["filler_feedback"] = f"Moderate fillers ({ratio_pct:.1f}%). Try replacing 'um/like' with a brief pause instead."
    else:
        top_fillers = list(set(metrics["filler_words_found"]))[:3]
        coaching["filler_feedback"] = f"High filler usage ({ratio_pct:.1f}%). Most common: {', '.join(top_fillers)}. Practice pausing instead."

    # ── Confidence feedback ──
    conf = metrics["confidence_avg"]
    hesitations = metrics["hesitation_count"]
    if conf >= 0.85:
        coaching["confidence_feedback"] = "Clear, confident delivery. Words are well-articulated."
    elif conf >= 0.7:
        coaching["confidence_feedback"] = f"Mostly clear ({hesitations} hesitations). Enunciate key terms more clearly."
    else:
        coaching["confidence_feedback"] = f"Frequent hesitations ({hesitations} detected). Practice your pitch to sound more confident."

    # ── Pause feedback (Gong Labs: strategic pauses increase close rates) ──
    pause_count = metrics["pause_count"]
    avg_pause = metrics["avg_pause_duration"]
    duration = metrics["duration_seconds"]

    if duration < 3:
        coaching["pause_feedback"] = "Response too short to analyze pauses."
    elif pause_count == 0:
        coaching["pause_feedback"] = "No pauses detected. Try pausing after key points — it builds impact."
    elif avg_pause < 1.0 and pause_count > 0:
        coaching["pause_feedback"] = f"{pause_count} brief pauses. Good rhythm — consider slightly longer pauses after value statements."
    elif avg_pause < 2.0:
        coaching["pause_feedback"] = f"{pause_count} well-placed pauses (avg {avg_pause:.1f}s). Strong conversational rhythm."
    else:
        coaching["pause_feedback"] = f"Long pauses detected (avg {avg_pause:.1f}s). May signal uncertainty — prepare key talking points."

    # ── Pace variability feedback (monotone detection) ──
    variability = metrics.get("pace_variability", "insufficient_data")
    std_dev = metrics.get("pace_std_dev", 0)
    if variability == "insufficient_data":
        coaching["variability_feedback"] = "Speak longer to analyze pace variation."
    elif variability == "flat":
        coaching["variability_feedback"] = f"Flat pace detected (variation: {std_dev} WPM). Slow down for key points, speed up for energy."
    elif variability == "moderate":
        coaching["variability_feedback"] = f"Moderate pace variation ({std_dev} WPM). Try emphasising value statements by slowing slightly."
    else:
        coaching["variability_feedback"] = f"Dynamic pace ({std_dev} WPM variation). Natural emphasis helps key points land."

    return coaching
