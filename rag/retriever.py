from typing import List, Dict, Any, Optional
from rag.vectorstore import VectorStoreManager

class RAGRetriever:
    """Retrieves relevant chunks from vector store"""
    
    def __init__(self, vectorstore_manager: VectorStoreManager):
        self.vectorstore_manager = vectorstore_manager
        print("✅ RAGRetriever initialized")
    
    def retrieve_relevant_chunks(
        self, 
        query: str, 
        org_id: int, 
        k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-k relevant chunks for a query
        
        Args:
            query: Search query
            org_id: Organization ID
            k: Number of chunks to retrieve
            filter_metadata: Additional metadata filters
            
        Returns:
            List of dicts with chunk content and metadata
        """
        
        print(f"\n🔍 Retrieving chunks for query: '{query}'")
        print(f"   Org ID: {org_id}")
        print(f"   Requested chunks: {k}")
        
        try:
            collection = self.vectorstore_manager.get_collection(org_id)
            
            # Build filter
            where_filter = {"org_id": org_id}
            if filter_metadata:
                where_filter.update(filter_metadata)
            
            # Perform similarity search with score
            results = collection.similarity_search_with_score(
                query=query,
                k=k,
                filter=where_filter
            )
            
            print(f"✅ Retrieved {len(results)} chunks")
            
            # Format results
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "relevance_score": float(1 - score),  # Convert distance to similarity
                    "distance": float(score),
                    "source": doc.metadata.get("source_file", "Unknown"),
                    "page": doc.metadata.get("page", 0),
                    "chunk_index": doc.metadata.get("chunk_index", 0)
                })
            
            return formatted_results
        
        except Exception as e:
            print(f"❌ Retrieval failed: {e}")
            raise Exception(f"Failed to retrieve chunks: {str(e)}")
    
    def retrieve_context_string(
        self, 
        query: str, 
        org_id: int, 
        k: int = 5,
        separator: str = "\n\n---\n\n"
    ) -> str:
        """
        Retrieve relevant chunks and return as single context string
        
        Args:
            query: Search query
            org_id: Organization ID
            k: Number of chunks to retrieve
            separator: String to separate chunks
            
        Returns:
            Concatenated string of all retrieved chunks
        """
        
        chunks = self.retrieve_relevant_chunks(query, org_id, k)
        
        if not chunks:
            return ""
        
        # Concatenate chunk contents with metadata headers
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "Unknown")
            relevance = chunk.get("relevance_score", 0)
            
            header = f"[Chunk {i} - Source: {source} - Relevance: {relevance:.2f}]"
            context_parts.append(f"{header}\n{chunk['content']}")
        
        return separator.join(context_parts)