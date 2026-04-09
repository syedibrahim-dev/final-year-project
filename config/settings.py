import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    
    # Database - will read from .env or use default
    DATABASE_URL: str = "mysql+pymysql://root:shaheer1@localhost:3306/salesforge_db"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # LLM Configuration — Q8_0 everywhere (22 GPU layers + 11 on 32GB RAM)
    LOCAL_LLM_MODEL: str = "llama3.1:8b-instruct-q8_0"
    LOCAL_LLM_BASE_URL: str = "http://localhost:11434"
    LOCAL_LLM_TEMPERATURE: float = 0.7
    LLM_NUM_GPU: int = 22  # 22/33 layers on GPU, rest spill to system RAM

    # MCQ-specific LLM
    MCQ_LLM_MODEL: str = "llama3.1:8b-instruct-q8_0"

    # Roleplay-specific LLM
    ROLEPLAY_LLM_MODEL: str = "llama3.1:8b-instruct-q8_0"

    # Post-session evaluation LLM (same model — no swap needed)
    EVAL_LLM_MODEL: str = "llama3.1:8b-instruct-q8_0"
    EVAL_NUM_GPU: int = 22

    # Multi-Agent Configuration
    ANALYST_LLM_MODEL: str = "llama3.1:8b-instruct-q8_0"
    ANALYST_SKIP_INTERVAL: int = 1                 # Run analyst every turn (1 = every message)
    ENABLE_ANALYST_AGENT: bool = True              # Toggle analyst agent on/off
    ENABLE_COACHING_HINTS: bool = True             # Toggle coaching hints in UI

    # SalesRLAgent Conversion Predictor (deepmost)
    ENABLE_SALESRL_AGENT: bool = True              # Toggle real-time conversion prediction
    SALESRL_LLM_MODEL: str = "llama3.1:8b-instruct-q8_0"  # Same model as roleplay — no GPU swap needed
    SALESRL_PYTHON: str = r"D:\fyp-2026\venv311_deepmost\Scripts\python.exe"
    SALESRL_PREDICT_INTERVAL: int = 1              # Run prediction every turn

    # Embedding Model (Ollama-served; 768-dim, superior semantic understanding)
    EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # Chunking
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # ── Module 5b: AI Image Generation (Colab FLUX API) ──────────────────────
    # Update this whenever your Colab ngrok URL changes (restart Colab → new URL).
    IMAGE_GEN_URL: str = "https://unurban-sade-nondomineering.ngrok-free.dev"

    # ── Module 5a: SMTP Server Settings ──────────────────────────────────────
    SMTP_EMAIL: str | None = None
    SMTP_PASSWORD: str | None = None
    
    class Config:
        env_file = ".env"          # ✅ Automatically loads from .env
        case_sensitive = True

settings = Settings()