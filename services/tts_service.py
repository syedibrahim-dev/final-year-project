"""
Edge TTS Service — natural-sounding text-to-speech via Microsoft Edge Neural voices.

Replaces the browser's robotic Web Speech API with high-quality neural TTS.
Audio is generated server-side and streamed to the frontend as MP3.

Voice mapping allows persona-specific voices (e.g., female customer = Aria,
male customer = Guy).  Falls back to a sensible default when no match.
"""

import asyncio
import io
import logging
from typing import Optional

import edge_tts

logger = logging.getLogger(__name__)

# ── Voice presets (en-US Neural voices) ──────────────────────────────
# These are the most natural-sounding Edge Neural voices.
VOICE_PRESETS = {
    "female_default": "en-US-AriaNeural",
    "female_warm":    "en-US-JennyNeural",
    "female_pro":     "en-US-EmmaNeural",
    "male_default":   "en-US-GuyNeural",
    "male_pro":       "en-US-AndrewNeural",
    "male_deep":      "en-US-EricNeural",
}

DEFAULT_VOICE = "en-US-GuyNeural"


def _pick_voice(voice_hint: Optional[str] = None) -> str:
    """Resolve a voice hint to an Edge TTS voice name.

    Accepts: full voice name ("en-US-AriaNeural"), preset key ("female_warm"),
    gender shorthand ("female"/"male"), or None for default.
    """
    if not voice_hint:
        return DEFAULT_VOICE

    # Exact Edge voice name
    if voice_hint.startswith("en-") and "Neural" in voice_hint:
        return voice_hint

    # Preset key
    if voice_hint in VOICE_PRESETS:
        return VOICE_PRESETS[voice_hint]

    # Gender shorthand
    lower = voice_hint.lower()
    if "female" in lower or lower == "f":
        return VOICE_PRESETS["female_default"]
    if "male" in lower or lower == "m":
        return VOICE_PRESETS["male_default"]

    return DEFAULT_VOICE


async def _generate_audio(text: str, voice: str, rate: str = "+0%") -> bytes:
    """Generate MP3 audio bytes from text using Edge TTS."""
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    return buffer.getvalue()


def synthesize_speech(
    text: str,
    voice_hint: Optional[str] = None,
    rate: str = "+0%",
) -> bytes:
    """
    Generate natural-sounding speech audio from text.

    Args:
        text:       The text to speak.
        voice_hint: Voice selector — see _pick_voice() for formats.
        rate:       Speed adjustment (e.g. "-10%", "+5%", "+0%").

    Returns:
        MP3 audio bytes ready to stream to the client.
    """
    voice = _pick_voice(voice_hint)
    logger.debug(f"TTS: voice={voice}, rate={rate}, text_len={len(text)}")

    # edge-tts is async; run in a fresh event loop if none is running
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an async context (FastAPI) — run in a thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            audio_bytes = pool.submit(
                asyncio.run, _generate_audio(text, voice, rate)
            ).result()
    else:
        audio_bytes = asyncio.run(_generate_audio(text, voice, rate))

    logger.debug(f"TTS: generated {len(audio_bytes)} bytes")
    return audio_bytes
