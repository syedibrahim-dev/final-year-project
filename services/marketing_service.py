"""
Marketing service — post lifecycle management and LLM caption generation.
"""
import requests
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timezone

from models.marketing import MarketingPost
from config.settings import settings


# ───────────────────────── Caption generation ───────────────────────────────

def generate_caption_with_llm(
    product_name: str,
    platform: str,
    tone: str = "professional",
    additional_context: str = "",
) -> str:
    """
    Generate a social media caption using the local Ollama LLM (phi3:mini).

    Args:
        product_name:       Name (or short description) of the product/offer.
        platform:           Target platform — 'facebook', 'instagram', or 'linkedin'.
        tone:               Writing tone — 'professional', 'casual', 'exciting', etc.
        additional_context: Any extra info (price, key benefit, target audience).

    Returns:
        Generated caption string.

    Raises:
        Exception if LLM is unreachable.
    """
    platform_guides = {
        "instagram": "casual and punchy, include 4-6 relevant hashtags at the end, use 1-2 emojis, max 150 words",
        "facebook":  "conversational and engaging, optional light emoji use, 150-250 words, no hashtag spam",
        "linkedin":  "professional and value-driven, no hashtags, 100-180 words, focus on business impact",
    }
    guide = platform_guides.get(platform, "clear and concise, 150 words")

    system_prompt = (
        "You are a high-performing social media copywriter. "
        "Write compelling posts that stop the scroll and drive real engagement. "
        "Respond ONLY with the post text — no preamble, no quotes around it, no explanation."
    )

    user_prompt = (
        f"Write a {tone} {platform} post for: {product_name}\n"
        f"Style rules: {guide}\n"
        + (f"Extra context: {additional_context}\n" if additional_context else "")
        + "Write the post now:"
    )

    payload = {
        "model": settings.LOCAL_LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.85, "num_predict": 350},
    }

    try:
        response = requests.post(
            f"{settings.LOCAL_LLM_BASE_URL}/api/chat",
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
    except requests.exceptions.Timeout:
        raise Exception("Caption generation timed out. Is Ollama running?")
    except Exception as e:
        raise Exception(f"Caption generation failed: {e}")


# ───────────────────────── Post CRUD ────────────────────────────────────────

def create_post(
    db: Session,
    org_id: int,
    user_id: int,
    caption: str,
    image_prompt: str,
    platforms: List[str],
    status: str = "draft",
    image_filename: Optional[str] = None,
    image_seed: Optional[int] = None,
    scheduled_at: Optional[datetime] = None,
    target_channels: Optional[List[str]] = None,
) -> MarketingPost:
    """Persist a new marketing post record.

    `platforms` are display labels (Facebook/Instagram/LinkedIn) for tone tuning.
    `target_channels` are the actual delivery destinations (discord/telegram/webhook/email)
    used by `publish_due_posts` — empty list ⇒ legacy "DB-only" publish.
    """
    post = MarketingPost(
        organization_id=org_id,
        created_by=user_id,
        caption=caption,
        image_prompt=image_prompt,
        image_filename=image_filename,
        image_seed=image_seed,
        platforms=platforms,
        target_channels=target_channels or [],
        status=status,
        scheduled_at=scheduled_at,
        created_at=datetime.now(timezone.utc),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    print(f"📝 Created post {post.id} (status={status}, channels={target_channels or 'none'}) for org {org_id}")
    return post


def get_posts(
    db: Session,
    org_id: int,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[MarketingPost]:
    """Return posts for an organisation, newest first."""
    query = db.query(MarketingPost).filter(
        MarketingPost.organization_id == org_id
    )
    if status:
        query = query.filter(MarketingPost.status == status)
    return query.order_by(desc(MarketingPost.created_at)).offset(offset).limit(limit).all()


def get_post(db: Session, post_id: int, org_id: int) -> Optional[MarketingPost]:
    """Fetch a single post by ID, scoped to the org."""
    return db.query(MarketingPost).filter(
        MarketingPost.id == post_id,
        MarketingPost.organization_id == org_id,
    ).first()


def delete_post(db: Session, post_id: int, org_id: int) -> bool:
    """Delete a post and its image file from disk."""
    post = get_post(db, post_id, org_id)
    if not post:
        return False

    # Remove the image file if it exists
    if post.image_filename:
        from pathlib import Path
        img_path = Path(__file__).parent.parent / "media" / "marketing" / post.image_filename
        if img_path.exists():
            try:
                img_path.unlink()
                print(f"🗑️  Deleted image file: {post.image_filename}")
            except Exception as e:
                print(f"⚠️  Could not delete image {post.image_filename}: {e}")

    db.delete(post)
    db.commit()
    return True


# ───────────────────────── Scheduler job ────────────────────────────────────

def publish_due_posts(db: Session) -> None:
    """
    Called by APScheduler every 60 seconds.

    Finds posts with status='scheduled' whose scheduled_at has passed and
    publishes them via the channels listed in post.target_channels.

    Channel options (no Meta/LinkedIn API access required):
      • discord  — webhook URL (Server settings → Integrations → Webhooks)
      • telegram — bot token from @BotFather + chat_id
      • webhook  — generic POST to Zapier/Make/n8n/IFTTT
      • email    — SMTP digest with embedded image

    Each channel attempt is logged in post.publish_log; one channel's failure
    does not poison the others. Final status reflects the aggregate:
      • all succeeded   → "published"
      • some succeeded  → "partial_failure"
      • all failed      → "failed"
      • no channels set → "published" (legacy DB-only behaviour, with stub log)
    """
    from services.publishing_channels import publish_to_channels  # local import avoids circular

    now = datetime.now(timezone.utc)

    due = db.query(MarketingPost).filter(
        MarketingPost.status == "scheduled",
        MarketingPost.scheduled_at <= now,
    ).all()

    if not due:
        return

    print(f"⏰ Scheduler: {len(due)} post(s) due for publishing")

    for post in due:
        channels = post.target_channels or []
        try:
            results = publish_to_channels(post, channels)
            post.publish_log = results

            successes = [r for r in results if r["success"]]
            failures = [r for r in results if not r["success"]]

            if not failures:
                post.status = "published"
                post.published_at = now
                channel_names = ", ".join(r["channel"] for r in successes) or "stub"
                print(f"   ✅ Post {post.id} published via {channel_names}")
            elif successes:
                post.status = "partial_failure"
                post.published_at = now
                ok = ", ".join(r["channel"] for r in successes)
                bad = ", ".join(f"{r['channel']}({r['detail'][:40]})" for r in failures)
                post.publish_error = f"Partial: ✓{ok}  ✗{bad}"
                print(f"   ⚠️  Post {post.id} partial — ok: {ok}; failed: {bad}")
            else:
                post.status = "failed"
                post.publish_error = "; ".join(f"{r['channel']}: {r['detail']}" for r in failures)
                print(f"   ❌ Post {post.id} all channels failed: {post.publish_error}")

        except Exception as e:
            post.status = "failed"
            post.publish_error = f"Orchestrator crash: {type(e).__name__}: {e}"
            print(f"   ❌ Post {post.id} crashed: {e}")

    db.commit()
