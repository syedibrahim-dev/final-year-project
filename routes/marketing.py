"""
Marketing API Routes — Module 5b: AI Marketing Post Generator
Covers: image generation, caption generation, post CRUD, image serving.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from utils.database import get_db
from utils.dependencies import get_current_user, role_required
from models.user import User
from services import image_service, marketing_service
from services.publishing_channels import get_channel_status, publish_to_channels, CHANNEL_FUNCTIONS
from config.settings import settings

router = APIRouter(prefix="/marketing", tags=["Marketing"])

VALID_CHANNELS = list(CHANNEL_FUNCTIONS.keys())  # ["discord", "telegram", "webhook", "email"]

# Where generated images live on disk
MEDIA_DIR = Path(__file__).parent.parent / "media" / "marketing"

VALID_PLATFORMS = ["facebook", "instagram", "linkedin"]
VALID_STATUSES  = ["draft", "scheduled"]


# ═══════════════════════ Pydantic request models ════════════════════════════

class GenerateImageRequest(BaseModel):
    prompt: str
    width:  int = 1024
    height: int = 1024
    steps:  int = 20
    seed:   int = 0     # 0 = random


class GenerateCaptionRequest(BaseModel):
    product_name:       str
    platform:           str = "instagram"
    tone:               str = "professional"
    additional_context: str = ""


class CreatePostRequest(BaseModel):
    caption:         str
    image_prompt:    str
    platforms:       List[str]
    status:          str = "draft"
    image_filename:  Optional[str] = None
    image_seed:      Optional[int] = None
    scheduled_at:    Optional[datetime] = None
    target_channels: Optional[List[str]] = None  # ["discord","telegram","webhook","email"]


class UpdateImageUrlRequest(BaseModel):
    url: str


# ═══════════════════════ Image generation (async job) ═══════════════════════

@router.post("/generate-image/start")
def start_image_generation(
    request: GenerateImageRequest,
    current_user: User = Depends(role_required(["admin", "manager"])),
):
    """
    Kick off image generation in a background thread and return a job_id immediately.
    The client should then poll GET /marketing/jobs/{job_id} every 5 seconds.
    """
    job_id = image_service.start_image_job(
        prompt=request.prompt,
        width=request.width,
        height=request.height,
        steps=request.steps,
        seed=request.seed,
    )
    return {"job_id": job_id, "status": "pending"}


@router.get("/jobs/{job_id}")
def get_image_job(
    job_id: str,
    current_user: User = Depends(role_required(["admin", "manager"])),
):
    """
    Poll the status of an image generation job.
    Returns:
      - {status: 'pending'}              — still running
      - {status: 'done', ...result}      — finished, result contains image_filename + image_base64
      - {status: 'failed', error: '...'}  — something went wrong
    """
    job = image_service.get_job_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "done":
        return {"status": "done", **job["result"]}
    if job["status"] == "failed":
        return {"status": "failed", "error": job["error"]}
    return {"status": "pending"}



@router.get("/images/{filename}")
def serve_image(filename: str):
    """
    Serve a previously generated image file.
    No auth required — filenames are UUID-based (not guessable).
    """
    # Prevent path-traversal: strip any directory component
    safe_name = Path(filename).name
    filepath = MEDIA_DIR / safe_name

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(str(filepath), media_type="image/png")


# ═══════════════════════ Caption generation ═════════════════════════════════

@router.post("/generate-caption")
def generate_caption_endpoint(
    request: GenerateCaptionRequest,
    current_user: User = Depends(role_required(["admin", "manager"])),
):
    """
    Generate a social media caption for a product using the local Ollama LLM.
    """
    if request.platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"platform must be one of {VALID_PLATFORMS}",
        )

    try:
        caption = marketing_service.generate_caption_with_llm(
            product_name=request.product_name,
            platform=request.platform,
            tone=request.tone,
            additional_context=request.additional_context,
        )
        return {"success": True, "caption": caption}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )


# ═══════════════════════ Post CRUD ══════════════════════════════════════════

@router.post("/posts", status_code=status.HTTP_201_CREATED)
def create_post(
    request: CreatePostRequest,
    current_user: User = Depends(role_required(["admin", "manager"])),
    db: Session = Depends(get_db),
):
    """Save a marketing post (draft or scheduled)."""
    # Validate status
    if request.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {VALID_STATUSES}",
        )

    # Scheduling requires a date
    if request.status == "scheduled" and not request.scheduled_at:
        raise HTTPException(
            status_code=400,
            detail="scheduled_at is required when status is 'scheduled'",
        )

    # Validate platforms
    bad = [p for p in request.platforms if p not in VALID_PLATFORMS]
    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform(s): {bad}. Must be one of {VALID_PLATFORMS}",
        )

    if not request.platforms:
        raise HTTPException(status_code=400, detail="At least one platform is required")

    # Validate target_channels if provided
    if request.target_channels:
        bad_ch = [c for c in request.target_channels if c not in VALID_CHANNELS]
        if bad_ch:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid channel(s): {bad_ch}. Must be one of {VALID_CHANNELS}",
            )

    # Block scheduling unconfigured channels — fail fast instead of at publish time
    if request.status == "scheduled" and request.target_channels:
        configured = get_channel_status()
        unconfigured = [c for c in request.target_channels if not configured.get(c)]
        if unconfigured:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot schedule to unconfigured channels: {unconfigured}. "
                    f"Set the relevant env vars (e.g., DISCORD_WEBHOOK_URL) and restart."
                ),
            )

    post = marketing_service.create_post(
        db=db,
        org_id=current_user.organization_id,
        user_id=current_user.id,
        caption=request.caption,
        image_prompt=request.image_prompt,
        platforms=request.platforms,
        status=request.status,
        image_filename=request.image_filename,
        image_seed=request.image_seed,
        scheduled_at=request.scheduled_at,
        target_channels=request.target_channels,
    )

    return _serialize(post)


@router.get("/posts")
def list_posts(
    status:  Optional[str] = Query(None, description="Filter by status"),
    limit:   int = Query(50, le=100),
    offset:  int = Query(0, ge=0),
    current_user: User = Depends(role_required(["admin", "manager"])),
    db: Session = Depends(get_db),
):
    """List marketing posts for this organisation, newest first."""
    posts = marketing_service.get_posts(
        db=db,
        org_id=current_user.organization_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"posts": [_serialize(p) for p in posts], "total": len(posts)}


@router.get("/posts/{post_id}")
def get_post(
    post_id: int,
    current_user: User = Depends(role_required(["admin", "manager"])),
    db: Session = Depends(get_db),
):
    """Get a single marketing post."""
    post = marketing_service.get_post(db, post_id, current_user.organization_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return _serialize(post)


@router.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    current_user: User = Depends(role_required(["admin", "manager"])),
    db: Session = Depends(get_db),
):
    """Delete a post and its generated image file."""
    deleted = marketing_service.delete_post(db, post_id, current_user.organization_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"success": True, "message": "Post deleted"}


# ═══════════════════════ Publishing channels ════════════════════════════════

@router.get("/channels")
def list_channel_status(
    current_user: User = Depends(role_required(["admin", "manager"])),
):
    """
    Return which publishing channels are configured. The frontend uses this
    to disable un-configured channels in the picker.
    """
    return {
        "channels": [
            {"id": ch, "configured": is_set, "name": ch.capitalize()}
            for ch, is_set in get_channel_status().items()
        ]
    }


@router.post("/posts/{post_id}/publish-now")
def publish_post_now(
    post_id: int,
    current_user: User = Depends(role_required(["admin", "manager"])),
    db: Session = Depends(get_db),
):
    """
    Manually publish a draft/scheduled post immediately, bypassing the
    scheduler. Useful for testing channel configurations and for "publish now"
    UI buttons.
    """
    post = marketing_service.get_post(db, post_id, current_user.organization_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status == "published":
        raise HTTPException(status_code=400, detail="Post is already published")

    channels = post.target_channels or []
    results = publish_to_channels(post, channels)
    post.publish_log = results

    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    now = datetime.utcnow()

    if not failures:
        post.status = "published"
        post.published_at = now
    elif successes:
        post.status = "partial_failure"
        post.published_at = now
        post.publish_error = "; ".join(f"{r['channel']}: {r['detail']}" for r in failures)
    else:
        post.status = "failed"
        post.publish_error = "; ".join(f"{r['channel']}: {r['detail']}" for r in failures)

    db.commit()
    db.refresh(post)
    return _serialize(post)


# ═══════════════════════ Settings ═══════════════════════════════════════════

@router.get("/settings/image-url")
def get_image_gen_url(
    current_user: User = Depends(role_required(["admin", "manager"])),
):
    """
    Return the currently configured image generation URL plus a health probe
    so the UI can show a green/red badge.
    """
    return image_service.check_image_service_health(timeout=4)


@router.patch("/settings/image-url")
def update_image_gen_url(
    request: UpdateImageUrlRequest,
    current_user: User = Depends(role_required(["admin"])),
):
    """
    Update the image gen URL at runtime — no backend restart needed.

    Use this when the Colab notebook restarts and a new ngrok URL is issued:
      1. Copy the new public URL from your Colab cell output
      2. PATCH this endpoint with {"url": "https://new-tunnel.ngrok.io"}
      3. Image generation immediately uses the new URL

    Setting an empty string clears the override and falls back to .env.
    """
    image_service.set_image_url(request.url)
    return image_service.check_image_service_health(timeout=4)


# ═══════════════════════ Helpers ════════════════════════════════════════════

def _serialize(post) -> dict:
    return {
        "id":              post.id,
        "caption":         post.caption,
        "image_prompt":    post.image_prompt,
        "image_filename":  post.image_filename,
        "image_seed":      post.image_seed,
        "platforms":       post.platforms,
        "target_channels": post.target_channels or [],
        "status":          post.status,
        "scheduled_at":    post.scheduled_at.isoformat() if post.scheduled_at else None,
        "published_at":    post.published_at.isoformat() if post.published_at else None,
        "publish_error":   post.publish_error,
        "publish_log":     post.publish_log or [],
        "created_at":      post.created_at.isoformat() if post.created_at else None,
        "created_by":      post.created_by,
    }
