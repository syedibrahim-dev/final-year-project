from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import os
import tempfile
from pathlib import Path

from utils.database import get_db
from utils.dependencies import get_current_user, role_required
from models.user import User
from models.training_content import TrainingContent
from schemas.content import (
    ContentUploadResponse,
    ContentOut,
    RetrievalResult,
    ContentChunk,
    ContentDeleteResponse,
    ContentStatsResponse
)
from rag.pipeline import RAGPipeline

router = APIRouter(prefix="/orgs/{org_id}/content", tags=["Content Management"])

# Lazy-load RAG pipeline (don't initialize on import)
_rag_pipeline: Optional[RAGPipeline] = None


def get_rag_pipeline() -> RAGPipeline:
    """Get or initialize RAG pipeline (lazy loading)"""
    global _rag_pipeline
    if _rag_pipeline is None:
        print("🔄 Initializing RAG pipeline on first use...")
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


@router.post("/upload", response_model=ContentUploadResponse)
async def upload_content(
    org_id: int,
    file: UploadFile = File(...),
    version: str = Form("1.0"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "manager", "trainer"]))
):
    """Upload training content (PDF/TXT)"""
    
    print(f"\n{'='*60}")
    print(f"📤 UPLOAD REQUEST RECEIVED")
    print(f"{'='*60}")
    print(f"👤 User: {current_user.email} (ID: {current_user.id})")
    print(f"🏢 Org ID: {org_id}")
    print(f"📄 File: {file.filename}")
    print(f"📦 Content Type: {file.content_type}")
    print(f"🏷️  Version: {version}")
    print(f"{'='*60}\n")
    
    # Verify user belongs to this org
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied to this organization")
    
    # Validate file type
    allowed_types = ["application/pdf", "text/plain"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not supported. Use PDF or TXT."
        )
    
    # Validate file size (10MB limit)
    file_content = await file.read()
    file_size = len(file_content)
    max_size = 10 * 1024 * 1024  # 10MB
    
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File size {file_size} bytes exceeds maximum {max_size} bytes"
        )
    
    print(f"✅ File validation passed ({file_size} bytes)")
    
    # Reset file pointer
    await file.seek(0)
    
    try:
        # Generate unique content ID
        content_id = f"content_{org_id}_{uuid.uuid4().hex[:8]}"
        
        print(f"🏷️  Generated Content ID: {content_id}")
        
        # Use cross-platform temp directory
        temp_dir = tempfile.gettempdir()
        safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._- ")
        temp_path = os.path.join(temp_dir, f"{content_id}_{safe_filename}")
        
        print(f"💾 Saving to temp: {temp_path}")
        
        # Save file temporarily
        with open(temp_path, "wb") as f:
            f.write(file_content)
        
        print(f"✅ File saved successfully")
        
        # Verify file exists
        if not os.path.exists(temp_path):
            raise Exception(f"Failed to save file to {temp_path}")
        
        print(f"🔄 Starting RAG pipeline processing...")
        
        # Get RAG pipeline (lazy load)
        rag_pipeline = get_rag_pipeline()
        
        # Process with RAG pipeline
        result = rag_pipeline.ingest_document(
            file_path=temp_path,
            content_id=content_id,
            org_id=org_id,
            metadata={
                "file_name": file.filename,
                "version": version,
                "uploader_id": current_user.id
            }
        )
        
        print(f"✅ RAG processing complete!")
        print(f"   📊 Chunks created: {result['chunk_count']}")
        print(f"   📄 Pages processed: {result.get('page_count', 0)}")
        
        # Store metadata in database
        content = TrainingContent(
            content_id=content_id,
            file_name=file.filename,
            version=version,
            page_count=result.get("page_count", 0),
            chunk_count=result["chunk_count"],
            uploader_id=current_user.id,
            organization_id=org_id
        )
        
        db.add(content)
        db.commit()
        db.refresh(content)
        
        print(f"💾 Metadata saved to database (ID: {content.id})")
        
        # Clean up temp file
        try:
            os.remove(temp_path)
            print(f"🗑️  Cleaned up temp file")
        except Exception as cleanup_error:
            print(f"⚠️  Could not delete temp file: {cleanup_error}")
        
        print(f"\n{'='*60}")
        print(f"✅ UPLOAD COMPLETE")
        print(f"{'='*60}\n")
        
        return ContentUploadResponse(
            content_id=content_id,
            file_name=file.filename,
            version=version,
            page_count=result.get("page_count", 0),
            chunk_count=result["chunk_count"],
            message="Content uploaded and processed successfully"
        )
    
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ UPLOAD FAILED")
        print(f"{'='*60}")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process upload: {str(e)}"
        )


@router.get("/", response_model=List[ContentOut])
def list_content(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all training content for an organization"""
    
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    contents = db.query(TrainingContent).filter(
        TrainingContent.organization_id == org_id
    ).order_by(TrainingContent.upload_date.desc()).all()
    
    return contents


@router.get("/retrieve", response_model=RetrievalResult)
def retrieve_content(
    org_id: int,
    query: str,
    k: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve relevant content chunks using RAG"""
    
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not query or len(query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters")
    
    try:
        print(f"\n🔍 Content Retrieval Request")
        print(f"   Query: {query}")
        print(f"   Org ID: {org_id}")
        print(f"   Results requested: {k}")
        
        # Get RAG pipeline (lazy load)
        rag_pipeline = get_rag_pipeline()
        
        results = rag_pipeline.retrieve(
            query=query,
            org_id=org_id,
            k=k
        )
        
        print(f"✅ Retrieved {len(results)} results")
        
        # Convert to ContentChunk objects
        chunks = [ContentChunk(**result) for result in results]
        
        return RetrievalResult(
            query=query,
            results=chunks,
            count=len(chunks)
        )
    
    except Exception as e:
        print(f"❌ Retrieval failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@router.delete("/{content_id}", response_model=ContentDeleteResponse)
def delete_content(
    org_id: int,
    content_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "manager"]))
):
    """Delete training content"""
    
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Find content
    content = db.query(TrainingContent).filter(
        TrainingContent.content_id == content_id,
        TrainingContent.organization_id == org_id
    ).first()
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    try:
        print(f"\n🗑️  Deleting content: {content_id}")
        print(f"   File: {content.file_name}")
        
        # Get RAG pipeline (lazy load)
        rag_pipeline = get_rag_pipeline()
        
        # Delete from ChromaDB
        rag_pipeline.delete_document(content_id, org_id)
        print(f"   ✅ Deleted from vector store")
        
        # Delete from database
        file_name = content.file_name
        db.delete(content)
        db.commit()
        print(f"   ✅ Deleted from database")
        
        return ContentDeleteResponse(
            message=f"Content {content_id} deleted successfully",
            content_id=content_id,
            file_name=file_name
        )
    
    except Exception as e:
        db.rollback()
        print(f"❌ Delete failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.get("/stats", response_model=ContentStatsResponse)
def get_content_stats(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get content statistics for organization"""
    
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        # Get RAG pipeline (lazy load)
        rag_pipeline = get_rag_pipeline()
        
        stats = rag_pipeline.get_stats(org_id)
        return ContentStatsResponse(**stats)
    
    except Exception as e:
        print(f"❌ Stats failed: {str(e)}")
        return ContentStatsResponse(
            error=str(e)
        )