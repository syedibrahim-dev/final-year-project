"""
RAG Service — thin wrapper around rag/ module.

All ingestion and retrieval goes through the unified rag.pipeline.RAGPipeline,
which uses SpacyTextSplitter for sentence-aware chunking and cross-encoder
re-ranking for retrieval.  This module re-exports the functions that consumers
(roleplay prompts, knowledge agent, MCQ pipeline, knowledge chatbot) expect.
"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# ── Robust import ────────────────────────────────────────────────
try:
    from rag.pipeline import RAGPipeline
    CHROMA_AVAILABLE = True
except Exception as e:
    logger.warning(f"ChromaDB/RAG not available: {e}")
    CHROMA_AVAILABLE = False

# ── Lazy singleton ───────────────────────────────────────────────
_pipeline = None


def _get_pipeline() -> "RAGPipeline":
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


# ── Public API (unchanged signatures) ────────────────────────────

def ingest_pdf_to_rag(
    pdf_path: str,
    content_id: str,
    org_id: int
) -> Tuple[int, int]:
    """
    Ingest a PDF file into RAG system (ChromaDB).
    Returns: (num_chunks, page_count)
    """
    if not CHROMA_AVAILABLE:
        raise RuntimeError("ChromaDB is not available — cannot ingest documents")

    pipeline = _get_pipeline()
    result = pipeline.ingest_document(
        file_path=pdf_path,
        content_id=content_id,
        org_id=org_id,
    )
    return result["chunk_count"], result["page_count"]


def retrieve_relevant_chunks(
    query: str,
    org_id: int,
    k: int = 5
) -> List[dict]:
    """
    Retrieve relevant chunks for a query using RAG + cross-encoder re-ranking.
    Returns: List of {chunk, metadata, score}
    """
    if not CHROMA_AVAILABLE:
        logger.debug("ChromaDB not available — skipping RAG retrieval")
        return []

    try:
        pipeline = _get_pipeline()
        raw = pipeline.retrieve(query=query, org_id=org_id, k=k)

        # Normalise keys to what consumers expect:
        #   rag/retriever returns  {content, metadata, relevance_score, ...}
        #   consumers expect       {chunk,   metadata, score}
        formatted = []
        for item in raw:
            formatted.append({
                "chunk": item.get("content", ""),
                "metadata": item.get("metadata", {}),
                "score": item.get("relevance_score", 0.0),
            })
        return formatted

    except Exception as e:
        logger.warning(f"RAG retrieval failed: {e}")
        return []
