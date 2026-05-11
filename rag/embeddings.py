from typing import List
import numpy as np
from langchain_community.embeddings import OllamaEmbeddings
from config.settings import settings


def _normalize(vectors):
    """L2-normalize embedding vectors to unit length.

    Matches the old HuggingFaceEmbeddings(encode_kwargs={'normalize_embeddings': True})
    behaviour so that ChromaDB L2 distances stay in [0, 2] and downstream
    score thresholds remain valid.
    """
    arr = np.array(vectors, dtype=np.float32)
    if arr.ndim == 1:
        norm = float(np.linalg.norm(arr))
        return (arr / max(norm, 1e-12)).tolist()
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return (arr / norms).tolist()


class NormalizedOllamaEmbeddings(OllamaEmbeddings):
    """OllamaEmbeddings with L2-normalized output.

    ChromaDB calls embed_query / embed_documents directly on the object
    passed as embedding_function, so normalization must happen here —
    not in an outer wrapper — to ensure both ingestion AND retrieval
    queries produce unit-length vectors.
    """

    def embed_query(self, text: str) -> List[float]:
        raw = super().embed_query(text)
        return _normalize(raw)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        raw = super().embed_documents(texts)
        return _normalize(raw)


class EmbeddingManager:
    """Manages embedding model initialization and text embedding.

    Uses Ollama-served nomic-embed-text (768-dim) for document and query
    embeddings.  The Ollama server must be running and the model pulled
    (`ollama pull nomic-embed-text`) before first use.
    """

    def __init__(self, model_name: str = "nomic-embed-text"):
        self.model_name = model_name
        self._embedding_function = None
        print(f"  Initializing EmbeddingManager with model: {model_name}")

    @property
    def embedding_function(self) -> NormalizedOllamaEmbeddings:
        """Lazy load embedding model via Ollama (normalized output)"""
        if self._embedding_function is None:
            print(f"  Loading embedding model via Ollama: {self.model_name}")
            self._embedding_function = NormalizedOllamaEmbeddings(
                model=self.model_name,
                base_url=getattr(settings, 'EMBEDDING_BASE_URL', 'http://localhost:11434'),
            )
            print(f"  Embedding model loaded successfully")
        return self._embedding_function

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string (L2-normalized)"""
        return self.embedding_function.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents (L2-normalized)"""
        return self.embedding_function.embed_documents(texts)
