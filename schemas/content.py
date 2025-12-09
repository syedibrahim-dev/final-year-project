from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ContentUpload(BaseModel):
    """Schema for uploading content"""
    file_name: str = Field(..., description="Name of the file")
    version: str = Field(default="1.0", description="Content version")
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_name": "sales_training_guide.pdf",
                "version": "1.0"
            }
        }


class ContentUploadResponse(BaseModel):
    """Response after uploading content"""
    content_id: str
    file_name: str
    version: str
    page_count: int
    chunk_count: int
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "content_id": "content_1_abc123",
                "file_name": "sales_guide.pdf",
                "version": "1.0",
                "page_count": 15,
                "chunk_count": 42,
                "message": "Content uploaded and processed successfully"
            }
        }


class ContentOut(BaseModel):
    """Training content metadata"""
    id: int
    content_id: str
    file_name: str
    version: str
    page_count: int
    chunk_count: int
    upload_date: datetime
    uploader_id: int
    organization_id: int
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "content_id": "content_1_abc123",
                "file_name": "sales_guide.pdf",
                "version": "1.0",
                "page_count": 15,
                "chunk_count": 42,
                "upload_date": "2025-12-08T10:30:00",
                "uploader_id": 1,
                "organization_id": 1
            }
        }


class ContentRetrieveRequest(BaseModel):
    """Request to retrieve content"""
    query: str = Field(..., min_length=3, description="Search query")
    k: int = Field(default=5, ge=1, le=20, description="Number of results")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "How to handle objections in sales?",
                "k": 5
            }
        }


class ContentChunk(BaseModel):
    """A single content chunk from retrieval"""
    content: str = Field(..., description="Chunk text content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relevance score")
    distance: Optional[float] = Field(None, description="Distance score from query")
    source: Optional[str] = Field(None, description="Source file name")
    page: Optional[int] = Field(None, description="Page number")
    chunk_index: Optional[int] = Field(None, description="Chunk index in document")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "The discovery phase is crucial for understanding customer needs...",
                "metadata": {
                    "content_id": "content_1_abc123",
                    "source_file": "sales_guide.pdf",
                    "chunk_index": 5,
                    "org_id": 1
                },
                "relevance_score": 0.87,
                "distance": 0.13,
                "source": "sales_guide.pdf",
                "page": 3,
                "chunk_index": 5
            }
        }


class RetrievalResult(BaseModel):
    """Response from content retrieval"""
    query: str = Field(..., description="Original search query")
    results: List[ContentChunk] = Field(default_factory=list, description="Retrieved chunks")
    count: int = Field(..., ge=0, description="Number of results returned")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "How to handle objections?",
                "results": [
                    {
                        "content": "When handling objections, first acknowledge the concern...",
                        "metadata": {"content_id": "content_1_abc123"},
                        "relevance_score": 0.92,
                        "source": "sales_guide.pdf"
                    }
                ],
                "count": 5
            }
        }


class ContentDeleteResponse(BaseModel):
    """Response after deleting content"""
    message: str
    content_id: str
    file_name: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Content deleted successfully",
                "content_id": "content_1_abc123",
                "file_name": "sales_guide.pdf"
            }
        }


class ContentListResponse(BaseModel):
    """Response for listing content"""
    total: int = Field(..., ge=0, description="Total number of content items")
    items: List[ContentOut] = Field(default_factory=list, description="Content items")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 3,
                "items": [
                    {
                        "id": 1,
                        "content_id": "content_1_abc123",
                        "file_name": "sales_guide.pdf",
                        "version": "1.0",
                        "page_count": 15,
                        "chunk_count": 42,
                        "upload_date": "2025-12-08T10:30:00",
                        "uploader_id": 1,
                        "organization_id": 1
                    }
                ]
            }
        }


class ContentStatsResponse(BaseModel):
    """Statistics about content"""
    org_id: Optional[int] = None
    document_count: int = Field(default=0, ge=0)
    total_chunks: int = Field(default=0, ge=0)
    message: Optional[str] = None
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "org_id": 1,
                "document_count": 5,
                "total_chunks": 210
            }
        }


# Backwards compatibility aliases
RetrievalRequest = ContentRetrieveRequest
ContentDelete = ContentDeleteResponse