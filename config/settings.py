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

    # Agentic Post-Session Evaluator (tool-use loop on top of Ollama function calling)
    # When True, post-session feedback uses AgenticEvaluator instead of PerformanceAgent.
    # On any failure falls back to PerformanceAgent automatically — safe to toggle.
    # Off by default because tool-use adds 30-90s latency per evaluation.
    ENABLE_AGENTIC_EVALUATOR: bool = False

    # Agentic Post-Session Fact-Checker (deep claim audit with RAG + scope checks)
    # When True, post-session evaluation also runs AgenticFactChecker and appends
    # a `fact_check_report` to the evaluation response. Additive — on failure the
    # report is simply omitted; existing per-turn accuracy_data is unchanged.
    # Off by default because tool-use adds 30-60s extra latency per evaluation.
    ENABLE_AGENTIC_FACT_CHECK: bool = False

    # Scheduled Inventory Forecast Refresh (APScheduler)
    # WARNING: on large catalogs (e.g. 4,000+ products from Online Retail II)
    # each refresh cycle can take hours. Default off — trigger manually via
    # POST /inventory/refresh-all-forecasts when needed.
    ENABLE_SCHEDULED_FORECAST_REFRESH: bool = False

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
        # Resolve .env as an absolute path relative to the PROJECT ROOT,
        # not the process's current working directory. This fixes the
        # "SMTP credentials not configured" bug where uvicorn started
        # from a different directory couldn't find the file.
        env_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".env",
        )
        case_sensitive = True

settings = Settings()