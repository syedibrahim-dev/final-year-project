from typing import List, Optional, Dict, Any
from pathlib import Path
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from rag.embeddings import EmbeddingManager

class VectorStoreManager:
    """Manages Chroma vector store operations"""
    
    def __init__(
        self, 
        persist_directory: str = "./chroma_data",
        embedding_manager: Optional[EmbeddingManager] = None
    ):
        self.persist_directory = persist_directory
        self.embedding_manager = embedding_manager or EmbeddingManager()
        
        # Ensure directory exists
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        
        print(f"📁 VectorStore directory: {persist_directory}")
    
    def get_collection(self, org_id: int) -> Chroma:
        """Get or create Chroma collection for organization"""
        collection_name = f"org_{org_id}_collection"
        
        try:
            vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embedding_manager.embedding_function,
                collection_name=collection_name
            )
            return vectorstore
        except Exception as e:
            print(f"❌ Error getting collection for org {org_id}: {e}")
            raise
    
    def ingest_document(
        self, 
        file_path: str, 
        org_id: int, 
        content_id: str,
        file_name: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ) -> Dict[str, Any]:
        """
        Ingest document (PDF or TXT) into vector store
        
        Args:
            file_path: Path to document
            org_id: Organization ID
            content_id: Unique content identifier
            file_name: Original filename
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            
        Returns:
            Dictionary with ingestion results
        """
        
        print(f"\n📄 Ingesting document: {file_name}")
        print(f"   Path: {file_path}")
        print(f"   Content ID: {content_id}")
        print(f"   Org ID: {org_id}")
        
        try:
            # Load document based on file type
            documents = self._load_document(file_path)
            page_count = len(documents)
            
            print(f"✅ Loaded {page_count} pages")
            
            # Split into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            chunks = text_splitter.split_documents(documents)
            chunk_count = len(chunks)
            
            print(f"✅ Split into {chunk_count} chunks")
            
            # Add metadata to each chunk
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "content_id": content_id,
                    "source_file": file_name,
                    "chunk_index": i,
                    "total_chunks": chunk_count,
                    "org_id": org_id
                })
            
            # Get collection and add documents with manually generated embeddings
            collection = self.get_collection(org_id)
            
            print(f"🔄 Generating embeddings and storing in ChromaDB...")
            
            # Manually generate embeddings to avoid LangChain wrapper issues
            texts = [chunk.page_content for chunk in chunks]
            metadatas = [chunk.metadata for chunk in chunks]
            
            # Generate embeddings explicitly
            embeddings = self.embedding_manager.embed_documents(texts)
            
            if not embeddings:
                raise Exception("Embedding model returned empty embeddings")
            
            print(f"   ✅ Generated {len(embeddings)} embeddings (dim={len(embeddings[0])})")
            
            # Generate unique IDs for each chunk
            import uuid
            ids = [f"{content_id}_chunk_{i}_{uuid.uuid4().hex[:8]}" for i in range(len(texts))]
            
            # Use ChromaDB's native add via the LangChain wrapper's underlying collection
            collection.add_texts(
                texts=texts,
                metadatas=metadatas,
                embeddings=embeddings,
                ids=ids
            )
            
            # Persist to disk
            if hasattr(collection, 'persist'):
                collection.persist()
            
            print(f"✅ Successfully stored {chunk_count} chunks")
            
            return {
                "page_count": page_count,
                "chunk_count": chunk_count,
                "content_id": content_id,
                "status": "success"
            }
        
        except Exception as e:
            print(f"❌ Document ingestion failed: {e}")
            raise Exception(f"Failed to ingest document: {str(e)}")
    
    def _load_document(self, file_path: str) -> List[Any]:
        """Load document based on file type"""
        
        file_ext = Path(file_path).suffix.lower()
        
        try:
            if file_ext == ".pdf":
                loader = PyPDFLoader(file_path)
            elif file_ext == ".txt":
                loader = TextLoader(file_path, encoding='utf-8')
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
            
            documents = loader.load()
            
            if not documents:
                raise ValueError("No content extracted from document")
            
            return documents
        
        except Exception as e:
            raise Exception(f"Failed to load document: {str(e)}")
    
    def delete_content(self, org_id: int, content_id: str) -> None:
        """Delete content from vector store"""
        
        print(f"🗑️  Deleting content: {content_id} from org {org_id}")
        
        try:
            collection = self.get_collection(org_id)
            
            # Get all chunks with this content_id
            results = collection.get(
                where={"content_id": content_id}
            )
            
            if results and results.get('ids'):
                chunk_ids = results['ids']
                print(f"   Found {len(chunk_ids)} chunks to delete")
                
                # Delete the chunks
                collection.delete(ids=chunk_ids)
                
                # Persist changes
                if hasattr(collection, 'persist'):
                    collection.persist()
                
                print(f"✅ Deleted {len(chunk_ids)} chunks")
            else:
                print(f"⚠️  No chunks found for content_id: {content_id}")
        
        except Exception as e:
            print(f"❌ Delete failed: {e}")
            raise Exception(f"Failed to delete content: {str(e)}")
    
    def list_contents(self, org_id: int) -> List[Dict[str, Any]]:
        """List all content IDs in organization's collection"""
        
        try:
            collection = self.get_collection(org_id)
            
            # Get all documents in the collection
            results = collection.get()
            
            if not results or not results.get('metadatas'):
                return []
            
            # Extract unique content IDs
            content_map = {}
            for metadata in results['metadatas']:
                content_id = metadata.get('content_id')
                if content_id and content_id not in content_map:
                    content_map[content_id] = {
                        "content_id": content_id,
                        "source_file": metadata.get('source_file', 'Unknown'),
                        "total_chunks": metadata.get('total_chunks', 0)
                    }
            
            return list(content_map.values())
        
        except Exception as e:
            print(f"❌ Failed to list contents: {e}")
            return []