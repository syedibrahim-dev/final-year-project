from typing import List, Tuple
import traceback
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
try:
    # Preferred modern packages (LangChain 0.2+)
    from langchain_huggingface import HuggingFaceEmbeddings as SentenceTransformerEmbeddings
except Exception:
    # Backward-compatible fallback for older environments
    from langchain_community.embeddings import SentenceTransformerEmbeddings

try:
    # Preferred modern package (LangChain 0.2+)
    from langchain_chroma import Chroma
except Exception:
    # Backward-compatible fallback for older environments
    from langchain_community.vectorstores import Chroma
from config.settings import settings

try:
    import chromadb
except Exception:
    chromadb = None

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


def _direct_chroma_search(embedding_model, collection_name: str, query: str, org_id: int, k: int) -> List[dict]:
    """
    Bypass LangChain Chroma wrapper entirely and query chromadb directly.
    This avoids the _type KeyError caused by stale on-disk collection metadata.
    """
    if chromadb is None:
        return []

    import os, shutil

    persist_dir = settings.CHROMA_PERSIST_DIR

    # Try with a fresh in-memory client reading an existing collection
    try:
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.get_collection(name=collection_name)
    except Exception:
        # Collection doesn't exist or the DB itself is corrupted.
        # Nuke the stale data so future ingestions start clean.
        print(f"⚠️  ChromaDB data at '{persist_dir}' is corrupted / incompatible. Resetting it.")
        try:
            if os.path.isdir(persist_dir):
                shutil.rmtree(persist_dir)
                os.makedirs(persist_dir, exist_ok=True)
        except Exception as cleanup_err:
            print(f"   Could not clean up chroma dir: {cleanup_err}")
        return []

    query_embedding = embedding_model.embed_query(query)
    raw = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    docs = raw.get("documents", [[]])[0]
    metadatas = raw.get("metadatas", [[]])[0]
    distances = raw.get("distances", [[]])[0]

    formatted = []
    for idx, doc_text in enumerate(docs):
        metadata = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}
        score = distances[idx] if idx < len(distances) and distances[idx] is not None else 0.0
        formatted.append({"chunk": doc_text, "metadata": metadata, "score": float(score)})

    print(f"RAG retrieval path=direct_chroma, chunks={len(formatted)} for org_id={org_id}")
    return formatted


def retrieve_relevant_chunks(
    query: str,
    org_id: int,
    k: int = 5
) -> List[dict]:
    """
    Retrieve relevant chunks for a query using RAG.
    Returns: List of {chunk, metadata, score}

    Tries the LangChain Chroma wrapper first; if the wrapper itself crashes
    (e.g. _type KeyError from stale on-disk metadata) it falls back to
    querying chromadb directly.
    """
    collection_name = f"org_{org_id}_collection"

    try:
        embedding_model = SentenceTransformerEmbeddings(
            model_name=settings.EMBEDDING_MODEL
        )
    except Exception as emb_err:
        print(f"RAG: failed to load embedding model: {emb_err}")
        return []

    # --- Attempt 1: LangChain Chroma wrapper -----------------------------------
    try:
        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embedding_model,
            persist_directory=settings.CHROMA_PERSIST_DIR,
        )

        retrieval_path = "langchain_scored"
        try:
            results = vectorstore.similarity_search_with_score(query, k=k)
        except Exception:
            retrieval_path = "langchain_plain"
            docs = vectorstore.similarity_search(query, k=k)
            results = [(doc, 0.0) for doc in docs]

        formatted_results = []
        for doc, score in results:
            formatted_results.append({
                "chunk": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score),
            })

        print(f"RAG retrieval path={retrieval_path}, chunks={len(formatted_results)} for org_id={org_id}")
        return formatted_results

    except Exception as wrapper_err:
        # The Chroma() constructor itself crashed (e.g. _type KeyError).
        print(f"LangChain Chroma wrapper failed for org_id={org_id}: {wrapper_err}")
        print("Falling back to direct chromadb query...")

    # --- Attempt 2: Direct chromadb client (bypasses LangChain entirely) --------
    try:
        return _direct_chroma_search(embedding_model, collection_name, query, org_id, k)
    except Exception as direct_err:
        print(f"Direct chromadb query also failed for org_id={org_id}: {direct_err}")
        traceback.print_exc()
        return []