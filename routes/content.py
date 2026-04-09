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
    ContentStatsResponse,
    URLScrapeRequest,
    URLScrapeResponse,
    MediaUploadResponse,
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


# ══════════════════════════════════════════════════════════════
#  URL SCRAPING ENDPOINT
# ══════════════════════════════════════════════════════════════

@router.post("/scrape-url", response_model=URLScrapeResponse)
async def scrape_url_content(
    org_id: int,
    request: URLScrapeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "manager", "trainer"]))
):
    """Scrape a URL and ingest the text content into RAG"""
    
    print(f"\n{'='*60}")
    print(f"🌐 URL SCRAPE REQUEST")
    print(f"{'='*60}")
    print(f"👤 User: {current_user.email} (ID: {current_user.id})")
    print(f"🏢 Org ID: {org_id}")
    print(f"🔗 URL: {request.url}")
    print(f"{'='*60}\n")
    
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied to this organization")
    
    try:
        from services.url_scraper import scrape_url_to_file
        
        # Scrape the URL
        print(f"🔄 Scraping URL...")
        scrape_result = scrape_url_to_file(request.url)
        
        print(f"✅ Scraped {scrape_result['word_count']} words from {scrape_result['domain']}")
        print(f"   Title: {scrape_result['title']}")
        
        # Generate content ID
        content_id = f"url_{org_id}_{uuid.uuid4().hex[:8]}"
        file_name = f"{scrape_result['domain']}_{Path(scrape_result['url']).name or 'page'}"
        
        # Ingest into RAG pipeline
        print(f"🔄 Ingesting into RAG pipeline...")
        rag_pipeline = get_rag_pipeline()
        result = rag_pipeline.ingest_document(
            file_path=scrape_result["file_path"],
            content_id=content_id,
            org_id=org_id,
            metadata={
                "file_name": file_name,
                "version": request.version,
                "uploader_id": current_user.id,
                "source_type": "url",
                "source_url": request.url,
            }
        )
        
        print(f"✅ RAG ingestion complete! {result['chunk_count']} chunks created")
        
        # Store in database
        content = TrainingContent(
            content_id=content_id,
            file_name=file_name,
            source_type="url",
            source_url=request.url,
            version=request.version,
            page_count=0,
            chunk_count=result["chunk_count"],
            uploader_id=current_user.id,
            organization_id=org_id,
        )
        db.add(content)
        db.commit()
        db.refresh(content)
        
        # Clean up temp file
        try:
            os.remove(scrape_result["file_path"])
        except Exception:
            pass
        
        print(f"\n{'='*60}")
        print(f"✅ URL SCRAPE COMPLETE")
        print(f"{'='*60}\n")
        
        return URLScrapeResponse(
            content_id=content_id,
            file_name=file_name,
            source_type="url",
            source_url=request.url,
            version=request.version,
            word_count=scrape_result["word_count"],
            chunk_count=result["chunk_count"],
            title=scrape_result["title"],
            message=f"URL scraped and ingested successfully ({scrape_result['word_count']} words, {result['chunk_count']} chunks)",
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        print(f"❌ URL scrape failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"URL scrape failed: {str(e)}")


# ══════════════════════════════════════════════════════════════
#  MEDIA UPLOAD / TRANSCRIPTION ENDPOINT
# ══════════════════════════════════════════════════════════════

@router.post("/upload-media", response_model=MediaUploadResponse)
async def upload_media_content(
    org_id: int,
    file: UploadFile = File(...),
    version: str = Form("1.0"),
    language: str = Form("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "manager", "trainer"]))
):
    """Upload and transcribe audio/video, then ingest transcript into RAG"""
    
    print(f"\n{'='*60}")
    print(f"🎥 MEDIA UPLOAD REQUEST")
    print(f"{'='*60}")
    print(f"👤 User: {current_user.email} (ID: {current_user.id})")
    print(f"🏢 Org ID: {org_id}")
    print(f"📄 File: {file.filename}")
    print(f"🌐 Language: {language}")
    print(f"{'='*60}\n")
    
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied to this organization")
    
    # Validate file type
    allowed_extensions = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma",
                          ".mp4", ".webm", ".mkv", ".avi", ".mov"}
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type {ext} not supported. Supported: {', '.join(sorted(allowed_extensions))}"
        )
    
    # Validate file size (100MB limit for media)
    file_content = await file.read()
    file_size = len(file_content)
    max_size = 100 * 1024 * 1024  # 100MB
    
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File size {file_size} bytes exceeds maximum {max_size} bytes (100MB)"
        )
    
    print(f"✅ File validation passed ({file_size / 1024 / 1024:.1f} MB)")
    
    try:
        from services.media_transcriber import transcribe_to_file
        
        # Save uploaded file to temp
        temp_dir = tempfile.gettempdir()
        safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._- ")
        media_temp_path = os.path.join(temp_dir, f"media_{safe_filename}")
        
        with open(media_temp_path, "wb") as f:
            f.write(file_content)
        
        print(f"💾 Saved media to temp: {media_temp_path}")
        
        # Transcribe
        print(f"🔄 Transcribing with Whisper (this may take a minute)...")
        transcript_result = transcribe_to_file(
            file_path=media_temp_path,
            original_filename=file.filename,
            model_size="base",
            language=language if language != "auto" else None,
        )
        
        print(f"✅ Transcription complete: {transcript_result['word_count']} words, {transcript_result['duration']:.0f}s")
        
        # Generate content ID
        content_id = f"media_{org_id}_{uuid.uuid4().hex[:8]}"
        
        # Ingest transcript into RAG pipeline
        print(f"🔄 Ingesting transcript into RAG pipeline...")
        rag_pipeline = get_rag_pipeline()
        result = rag_pipeline.ingest_document(
            file_path=transcript_result["file_path"],
            content_id=content_id,
            org_id=org_id,
            metadata={
                "file_name": file.filename,
                "version": version,
                "uploader_id": current_user.id,
                "source_type": "media",
                "duration": transcript_result["duration"],
                "language": transcript_result["language"],
            }
        )
        
        print(f"✅ RAG ingestion complete! {result['chunk_count']} chunks created")
        
        # Store in database
        content = TrainingContent(
            content_id=content_id,
            file_name=file.filename,
            source_type="media",
            version=version,
            page_count=0,
            chunk_count=result["chunk_count"],
            uploader_id=current_user.id,
            organization_id=org_id,
        )
        db.add(content)
        db.commit()
        db.refresh(content)
        
        # Clean up temp files
        for path in [media_temp_path, transcript_result.get("file_path")]:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        
        print(f"\n{'='*60}")
        print(f"✅ MEDIA TRANSCRIPTION COMPLETE")
        print(f"{'='*60}\n")
        
        return MediaUploadResponse(
            content_id=content_id,
            file_name=file.filename,
            source_type="media",
            version=version,
            duration=transcript_result["duration"],
            word_count=transcript_result["word_count"],
            chunk_count=result["chunk_count"],
            language=transcript_result["language"],
            message=f"Media transcribed and ingested ({transcript_result['word_count']} words, {result['chunk_count']} chunks, {transcript_result['duration']:.0f}s audio)",
        )
    
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        print(f"❌ Media transcription failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Media transcription failed: {str(e)}")


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