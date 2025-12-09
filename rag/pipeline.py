"""
RAG Pipeline: Main orchestrator for document ingestion and retrieval
"""

from typing import List, Dict, Any, Optional
from pathlib import Path

from rag.embeddings import EmbeddingManager
from rag.vectorstore import VectorStoreManager
from rag.retriever import RAGRetriever
from config.settings import settings


class RAGPipeline:
    """Main RAG pipeline orchestrator"""
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        embedding_model: Optional[str] = None
    ):
        """
        Initialize RAG Pipeline
        
        Args:
            persist_directory: Directory to persist ChromaDB data
            embedding_model: Name of embedding model to use
        """
        
        print("\n" + "="*60)
        print("🚀 INITIALIZING RAG PIPELINE")
        print("="*60)
        
        # Use settings if not provided
        persist_dir = persist_directory or settings.CHROMA_PERSIST_DIR
        embed_model = embedding_model or settings.EMBEDDING_MODEL
        
        # Initialize components
        print(f"📦 Embedding Model: {embed_model}")
        print(f"📁 Persist Directory: {persist_dir}")
        
        self.embedding_manager = EmbeddingManager(model_name=embed_model)
        self.vectorstore_manager = VectorStoreManager(
            persist_directory=persist_dir,
            embedding_manager=self.embedding_manager
        )
        self.retriever = RAGRetriever(vectorstore_manager=self.vectorstore_manager)
        
        print("✅ RAG Pipeline initialized successfully")
        print("="*60 + "\n")
    
    def ingest_document(
        self,
        file_path: str,
        content_id: str,
        org_id: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest a document into the RAG system
        
        Args:
            file_path: Path to the document file
            content_id: Unique content identifier
            org_id: Organization ID
            metadata: Additional metadata (file_name, version, uploader_id, etc.)
        
        Returns:
            Dictionary with ingestion results
        """
        
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_name = metadata.get("file_name", Path(file_path).name) if metadata else Path(file_path).name
        
        try:
            result = self.vectorstore_manager.ingest_document(
                file_path=file_path,
                org_id=org_id,
                content_id=content_id,
                file_name=file_name,
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP
            )
            
            return result
        
        except Exception as e:
            print(f"❌ Pipeline ingestion failed: {e}")
            raise
    
    def retrieve(
        self,
        query: str,
        org_id: int,
        k: int = 5,
        return_as_string: bool = False,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Retrieve relevant content chunks
        
        Args:
            query: Search query
            org_id: Organization ID
            k: Number of results to return
            return_as_string: If True, return concatenated string; else return list
            filter_metadata: Additional metadata filters
        
        Returns:
            List of chunks or concatenated string
        """
        
        try:
            if return_as_string:
                return self.retriever.retrieve_context_string(query, org_id, k)
            else:
                return self.retriever.retrieve_relevant_chunks(
                    query, org_id, k, filter_metadata
                )
        
        except Exception as e:
            print(f"❌ Pipeline retrieval failed: {e}")
            raise
    
    def delete_document(self, content_id: str, org_id: int) -> None:
        """
        Delete a document from the RAG system
        
        Args:
            content_id: Content identifier
            org_id: Organization ID
        """
        
        try:
            self.vectorstore_manager.delete_content(org_id, content_id)
        except Exception as e:
            print(f"❌ Pipeline deletion failed: {e}")
            raise
    
    def list_documents(self, org_id: int) -> List[Dict[str, Any]]:
        """
        List all documents in an organization
        
        Args:
            org_id: Organization ID
            
        Returns:
            List of document metadata
        """
        
        try:
            return self.vectorstore_manager.list_contents(org_id)
        except Exception as e:
            print(f"❌ Pipeline list failed: {e}")
            raise
    
    def get_stats(self, org_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get statistics about the vector store
        
        Args:
            org_id: Optional organization ID to filter
            
        Returns:
            Dictionary with statistics
        """
        
        try:
            if org_id:
                contents = self.list_documents(org_id)
                total_chunks = sum(c.get('total_chunks', 0) for c in contents)
                return {
                    "org_id": org_id,
                    "document_count": len(contents),
                    "total_chunks": total_chunks
                }
            else:
                return {
                    "message": "Provide org_id for specific stats"
                }
        except Exception as e:
            return {"error": str(e)}