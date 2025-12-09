import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
CHROMA_DIR = BASE_DIR / "chroma_data"
TEMP_DIR = BASE_DIR / "temp"

# Ensure directories exist
CHROMA_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

# LLM Configuration
LLM_CONFIG = {
    "model": "llama3.1:8b-instruct-q4_K_M",
    "temperature": 0.7,
    "base_url": "http://localhost:11434"
}

# Embedding Configuration
EMBEDDING_CONFIG = {
    "model": "sentence-transformers/all-MiniLM-L6-v2"
}

# MCQ Generation Defaults
MCQ_DEFAULTS = {
    "num_questions": 5,
    "difficulty": "medium",
    "num_distractors": 3
}