import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    
    # Database - will read from .env or use default
    DATABASE_URL: str = "mysql+pymysql://root:1234@localhost:3306/salesforge_db"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # LLM Configuration — Q8_0 everywhere
    LOCAL_LLM_MODEL: str = "llama3.1:8b-instruct-q8_0"
    # COLAB MODE: set LOCAL_LLM_BASE_URL to your ngrok tunnel URL (e.g. https://xxxx.ngrok-free.app)
    # CPU MODE:   keep as http://localhost:11434
    LOCAL_LLM_BASE_URL: str = "https://flatware-spied-cuddle.ngrok-free.dev"
    LOCAL_LLM_TEMPERATURE: float = 0.7
    # GPU MODE (revert): set LLM_NUM_GPU = 22  (22/33 layers on GPU, rest spill to system RAM)
    LLM_NUM_GPU: int = 0  # CPU-only: 0 disables GPU offloading

    # MCQ-specific LLM
    MCQ_LLM_MODEL: str = "llama3.1:8b-instruct-q8_0"

    # Roleplay-specific LLM
    ROLEPLAY_LLM_MODEL: str = "llama3.1:8b-instruct-q8_0"

    # Post-session evaluation LLM (same model — no swap needed)
    EVAL_LLM_MODEL: str = "llama3.1:8b-instruct-q8_0"
    # GPU MODE (revert): set EVAL_NUM_GPU = 22
    EVAL_NUM_GPU: int = 0  # CPU-only

    # Multi-Agent Configuration
    ANALYST_LLM_MODEL: str = "llama3.1:8b-instruct-q8_0"
    ANALYST_SKIP_INTERVAL: int = 3                 # Run analyst every 3rd turn (reduces Ollama load on CPU/tunnel)
    ENABLE_ANALYST_AGENT: bool = True              # Toggle analyst agent on/off
    ENABLE_COACHING_HINTS: bool = True             # Toggle coaching hints in UI

    # SalesRLAgent Conversion Predictor (deepmost)
    ENABLE_SALESRL_AGENT: bool = True              # Toggle real-time conversion prediction
    SALESRL_LLM_MODEL: str = "llama3.1:8b-instruct-q8_0"  # Same model as roleplay — no GPU swap needed
    SALESRL_PYTHON: str = r"D:\fyp-2026\venv311_deepmost\Scripts\python.exe"
    SALESRL_PREDICT_INTERVAL: int = 1              # Run prediction every turn

    # Embedding Model (Ollama-served locally; 768-dim, superior semantic understanding)
    EMBEDDING_MODEL: str = "nomic-embed-text"
    # Embeddings always run locally — separate from LLM which may be on Colab
    EMBEDDING_BASE_URL: str = "http://localhost:11434"
    
    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # Chunking
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # ── Module 5b: AI Image Generation (Colab FLUX API) ──────────────────────
    # Set this in .env to your current Colab ngrok URL. The URL changes every
    # time you restart the Colab notebook, so the admin can also override it
    # at runtime via PATCH /marketing/settings/image-url (no restart needed).
    # If unset, image generation gracefully degrades — caption-only posts work.
    IMAGE_GEN_URL: str | None = None

    # ── Module 5a: SMTP Server Settings ──────────────────────────────────────
    SMTP_EMAIL: str | None = None
    SMTP_PASSWORD: str | None = None

    # ── Module 5b: Marketing publishing channels (alternatives to Meta API) ──
    # All optional — set the ones you want to use, leave others blank.
    DISCORD_WEBHOOK_URL: str | None = None        # Server settings → Integrations → Webhooks
    TELEGRAM_BOT_TOKEN: str | None = None         # Get from @BotFather on Telegram
    TELEGRAM_CHAT_ID:  str | None = None          # @YourChannel or numeric -100xxxxxxxxxx
    GENERIC_WEBHOOK_URL: str | None = None        # Zapier / Make / n8n / IFTTT trigger URL
    MARKETING_DIGEST_RECIPIENTS: str | None = None  # Comma-separated emails for digest
    PUBLIC_BASE_URL: str | None = None            # e.g. https://yourdomain.com — for image URLs in webhook payloads

    class Config:
        env_file = ".env"          # ✅ Automatically loads from .env
        case_sensitive = True

settings = Settings()