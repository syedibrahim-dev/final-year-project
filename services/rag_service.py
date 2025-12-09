import os
from typing import List, Tuple
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from config.settings import settings

def ingest_pdf_to_rag(
    pdf_path: str,
    content_id: str,
    org_id: int
) -> Tuple[int, int]:
    """
    Ingest a PDF file into RAG system (ChromaDB)
    Returns: (num_chunks, page_count)
    """
    # Load PDF
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()
    page_count = len(pages)
    
    # Split into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len
    )
    chunks = text_splitter.split_documents(pages)
    
    # Add metadata
    for i, chunk in enumerate(chunks):
        chunk.metadata["content_id"] = content_id
        chunk.metadata["org_id"] = org_id
        chunk.metadata["chunk_index"] = i
    
    # Create embeddings
    embedding_model = SentenceTransformerEmbeddings(
        model_name=settings.EMBEDDING_MODEL
    )
    
    # Store in ChromaDB
    collection_name = f"org_{org_id}_collection"
    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embedding_model,
        persist_directory=settings.CHROMA_PERSIST_DIR
    )
    
    vectorstore.add_documents(chunks)
    
    return len(chunks), page_count


def retrieve_relevant_chunks(
    query: str,
    org_id: int,
    k: int = 5
) -> List[dict]:
    """
    Retrieve relevant chunks for a query using RAG
    Returns: List of {chunk, metadata, score}
    """
    embedding_model = SentenceTransformerEmbeddings(
        model_name=settings.EMBEDDING_MODEL
    )
    
    collection_name = f"org_{org_id}_collection"
    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embedding_model,
        persist_directory=settings.CHROMA_PERSIST_DIR
    )
    
    # Similarity search with scores
    results = vectorstore.similarity_search_with_score(query, k=k)
    
    formatted_results = []
    for doc, score in results:
        formatted_results.append({
            "chunk": doc.page_content,
            "metadata": doc.metadata,
            "score": float(score)
        })
    
    return formatted_results