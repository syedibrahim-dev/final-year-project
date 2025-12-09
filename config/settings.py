import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    
    # Database - will read from .env or use default
    DATABASE_URL: str = "mysql+pymysql://shah:pokemon1234@localhost:3306/salesforge_db"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # LLM Configuration
    LOCAL_LLM_MODEL: str = "phi3:mini"
    LOCAL_LLM_BASE_URL: str = "http://localhost:11434"
    LOCAL_LLM_TEMPERATURE: float = 0.7
    
    # Embedding Model
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    
    # Chunking
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    
    class Config:
        env_file = ".env"          # ✅ Automatically loads from .env
        case_sensitive = True

settings = Settings()