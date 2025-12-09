from typing import List
from langchain_community.embeddings import HuggingFaceEmbeddings

class EmbeddingManager:
    """Manages embedding model initialization and text embedding"""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._embedding_function = None
        print(f"📦 Initializing EmbeddingManager with model: {model_name}")
    
    @property
    def embedding_function(self) -> HuggingFaceEmbeddings:
        """Lazy load embedding model"""
        if self._embedding_function is None:
            print(f"🔄 Loading embedding model: {self.model_name}")
            self._embedding_function = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            print(f"✅ Embedding model loaded successfully")
        return self._embedding_function
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string"""
        return self.embedding_function.embed_query(text)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents"""
        return self.embedding_function.embed_documents(texts)