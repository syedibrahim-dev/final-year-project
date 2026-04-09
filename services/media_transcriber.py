"""
Media Transcriber Service
Transcribes video/audio files to text for RAG ingestion.
Uses OpenAI Whisper (local, no API key needed).
"""

import logging
import tempfile
import os
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    logger.warning("whisper not installed — media transcription unavailable")
    WHISPER_AVAILABLE = False

# Supported file extensions
SUPPORTED_AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"}
SUPPORTED_VIDEO = {".mp4", ".webm", ".mkv", ".avi", ".mov"}
SUPPORTED_EXTENSIONS = SUPPORTED_AUDIO | SUPPORTED_VIDEO

# Cache the model to avoid reloading
_whisper_model = None


def _get_model(model_size: str = "base"):
    """Get or load whisper model (cached)."""
    global _whisper_model
    if _whisper_model is None:
        logger.info(f"Loading Whisper model: {model_size}")
        _whisper_model = whisper.load_model(model_size)
        logger.info("Whisper model loaded successfully")
    return _whisper_model


def validate_media_file(file_path: str) -> str:
    """
    Validate that the file is a supported media type.
    Returns the file extension.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(
            f"Unsupported file type: {ext}. Supported: {supported}"
        )
    return ext


def transcribe_media(
    file_path: str,
    model_size: str = "base",
    language: Optional[str] = "en",
) -> Dict[str, Any]:
    """
    Transcribe an audio/video file to text.
    
    Args:
        file_path: Path to the media file
        model_size: Whisper model size (tiny, base, small, medium, large)
        language: Language code (e.g. 'en') or None for auto-detect
    
    Returns:
        Dictionary with:
            - text: Full transcript text
            - segments: List of {start, end, text} segments
            - language: Detected language
            - duration: Audio duration in seconds
            - word_count: Number of words in transcript
    """
    if not WHISPER_AVAILABLE:
        raise RuntimeError(
            "whisper not installed. Run: pip install openai-whisper\n"
            "Also requires ffmpeg: winget install ffmpeg"
        )
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    validate_media_file(file_path)
    
    logger.info(f"Transcribing: {file_path} (model: {model_size})")
    
    model = _get_model(model_size)
    
    # Transcribe
    options = {}
    if language:
        options["language"] = language
    
    result = model.transcribe(file_path, **options)
    
    text = result["text"].strip()
    segments = [
        {
            "start": round(seg["start"], 1),
            "end": round(seg["end"], 1),
            "text": seg["text"].strip(),
        }
        for seg in result.get("segments", [])
    ]
    
    # Calculate duration from last segment
    duration = segments[-1]["end"] if segments else 0
    word_count = len(text.split())
    
    logger.info(f"Transcription complete: {word_count} words, {duration:.0f}s duration")
    
    return {
        "text": text,
        "segments": segments,
        "language": result.get("language", language),
        "duration": duration,
        "word_count": word_count,
    }


def transcribe_to_file(
    file_path: str,
    original_filename: str = "",
    model_size: str = "base",
    language: Optional[str] = "en",
) -> Dict[str, Any]:
    """
    Transcribe a media file and save the transcript to a temp text file.
    The temp file can be fed directly into the RAG pipeline.
    
    Args:
        file_path: Path to the media file
        original_filename: Original file name for metadata
        model_size: Whisper model size
        language: Language code
    
    Returns:
        Dictionary with:
            - file_path: Path to the temp transcript file
            - text: Full transcript
            - duration: Audio duration
            - word_count: Word count
            - language: Detected language
            - segments: Timed segments
    """
    result = transcribe_media(file_path, model_size, language)
    
    # Build structured text with timestamps
    filename = original_filename or Path(file_path).name
    header = f"Transcript of: {filename}\n"
    header += f"Duration: {result['duration']:.0f} seconds\n"
    header += f"Language: {result['language']}\n\n"
    
    # Add timestamped segments for better chunking context
    body_parts = []
    for seg in result["segments"]:
        mins = int(seg["start"] // 60)
        secs = int(seg["start"] % 60)
        body_parts.append(f"[{mins:02d}:{secs:02d}] {seg['text']}")
    
    full_text = header + "\n".join(body_parts)
    
    # Save to temp file
    temp_dir = tempfile.gettempdir()
    safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
    temp_path = os.path.join(temp_dir, f"transcript_{safe_name}.txt")
    
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    
    result["file_path"] = temp_path
    logger.info(f"Saved transcript to: {temp_path}")
    
    return result
