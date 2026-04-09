"""
Publishing channels — alternatives to Meta/LinkedIn APIs that don't need
official platform OAuth.

Each channel function:
  • Takes (post, settings_or_config) and tries to deliver the post.
  • Returns a dict: {"channel": str, "success": bool, "timestamp": iso, "detail": str, "external_id": str|None}
  • NEVER raises — failures are returned as success=False so one channel's
    failure doesn't poison the rest.

Supported channels (no platform-API access required):
  • discord    — Discord webhook (paste a webhook URL from any server)
  • telegram   — Telegram bot → channel (token from @BotFather, free)
  • webhook    — Generic POST to any URL (Zapier / Make / n8n / IFTTT / your own)
  • email      — Email digest (uses existing SMTP_EMAIL/SMTP_PASSWORD)

Why these instead of Meta Graph API?
  Discord and Telegram have NO app-review requirement, are free, and the
  posts are publicly visible (good for FYP demos). The generic webhook lets
  the user pipe to anything via no-code tools. Email is the universal
  fallback that always works if SMTP is configured.
"""
from __future__ import annotations

import json
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import requests

from config.settings import settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result(channel: str, success: bool, detail: str, external_id: Optional[str] = None) -> dict:
    return {
        "channel": channel,
        "success": success,
        "timestamp": _now(),
        "detail": detail,
        "external_id": external_id,
    }


def _image_path(image_filename: Optional[str]) -> Optional[Path]:
    """Resolve a marketing image filename to its absolute disk path."""
    if not image_filename:
        return None
    media_dir = Path(__file__).parent.parent / "media" / "marketing"
    p = media_dir / Path(image_filename).name  # strip path-traversal
    return p if p.exists() else None


# ──────────────────────────────────────────────────────────────────
# 1. Discord webhook
# ──────────────────────────────────────────────────────────────────
def publish_to_discord(post, webhook_url: Optional[str] = None) -> dict:
    """
    Post to a Discord channel via webhook.

    Setup (30 seconds):
      1. In Discord: Server Settings → Integrations → Webhooks → New Webhook
      2. Copy the URL
      3. Paste into DISCORD_WEBHOOK_URL in .env

    Discord webhooks support text + image upload via multipart in a single call.
    """
    url = webhook_url or settings.DISCORD_WEBHOOK_URL
    if not url:
        return _result("discord", False, "DISCORD_WEBHOOK_URL not configured")

    img_path = _image_path(post.image_filename)
    payload_json = {
        "content": post.caption[:2000],  # Discord 2000-char hard limit
        "username": "SalesForge AI",
    }

    try:
        if img_path:
            # Multipart: text + file in one call
            with open(img_path, "rb") as f:
                files = {"file": (img_path.name, f, "image/png")}
                data = {"payload_json": json.dumps(payload_json)}
                r = requests.post(url, data=data, files=files, timeout=20)
        else:
            r = requests.post(url, json=payload_json, timeout=20)

        if r.status_code in (200, 204):
            # Discord returns the message object on success when wait=true is set;
            # without wait, returns 204 No Content
            return _result("discord", True, f"Posted (HTTP {r.status_code})")
        else:
            return _result("discord", False, f"HTTP {r.status_code}: {r.text[:200]}")
    except requests.exceptions.Timeout:
        return _result("discord", False, "Request timed out (20s)")
    except Exception as e:
        return _result("discord", False, f"{type(e).__name__}: {e}")


# ──────────────────────────────────────────────────────────────────
# 2. Telegram bot → channel
# ──────────────────────────────────────────────────────────────────
def publish_to_telegram(
    post,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> dict:
    """
    Post to a Telegram channel/chat via bot API.

    Setup (2 minutes, free):
      1. In Telegram: search @BotFather → /newbot → name your bot → copy token
      2. Create a public channel, add the bot as admin
      3. Get the channel ID (e.g., @YourChannel or numeric -100xxxxxxxxxx)
      4. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env

    Uses sendPhoto if image present, otherwise sendMessage.
    """
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    chat = chat_id or settings.TELEGRAM_CHAT_ID
    if not token or not chat:
        return _result("telegram", False, "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured")

    img_path = _image_path(post.image_filename)
    base = f"https://api.telegram.org/bot{token}"

    try:
        if img_path:
            # sendPhoto with caption (caption max 1024 chars)
            with open(img_path, "rb") as f:
                files = {"photo": (img_path.name, f, "image/png")}
                data = {"chat_id": chat, "caption": post.caption[:1024]}
                r = requests.post(f"{base}/sendPhoto", data=data, files=files, timeout=20)
        else:
            # sendMessage (max 4096 chars)
            data = {"chat_id": chat, "text": post.caption[:4096]}
            r = requests.post(f"{base}/sendMessage", data=data, timeout=20)

        if r.status_code == 200:
            body = r.json()
            if body.get("ok"):
                msg_id = str(body.get("result", {}).get("message_id", ""))
                return _result("telegram", True, "Posted", external_id=msg_id)
            else:
                return _result("telegram", False, f"API rejected: {body.get('description', '')}")
        else:
            return _result("telegram", False, f"HTTP {r.status_code}: {r.text[:200]}")
    except requests.exceptions.Timeout:
        return _result("telegram", False, "Request timed out (20s)")
    except Exception as e:
        return _result("telegram", False, f"{type(e).__name__}: {e}")


# ──────────────────────────────────────────────────────────────────
# 3. Generic webhook (Zapier / Make / n8n / IFTTT / custom)
# ──────────────────────────────────────────────────────────────────
def publish_to_webhook(post, webhook_url: Optional[str] = None) -> dict:
    """
    POST the post payload to a user-supplied URL.

    Setup:
      1. Create a Zap/Scenario in Zapier/Make/n8n/IFTTT with a webhook trigger
      2. Copy the trigger's URL
      3. Set GENERIC_WEBHOOK_URL in .env
      4. Wire the trigger to whatever action you want (Buffer → Twitter, etc.)

    Payload includes everything the receiver might need: caption, platforms,
    image URL (served by /marketing/images/{filename}), post metadata.
    """
    url = webhook_url or settings.GENERIC_WEBHOOK_URL
    if not url:
        return _result("webhook", False, "GENERIC_WEBHOOK_URL not configured")

    payload = {
        "post_id": post.id,
        "caption": post.caption,
        "image_filename": post.image_filename,
        "image_url": (
            f"{settings.PUBLIC_BASE_URL}/marketing/images/{post.image_filename}"
            if post.image_filename and settings.PUBLIC_BASE_URL else None
        ),
        "platforms": post.platforms or [],
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        "organization_id": post.organization_id,
        "created_by": post.created_by,
    }

    try:
        r = requests.post(url, json=payload, timeout=15)
        if 200 <= r.status_code < 300:
            return _result("webhook", True, f"Delivered (HTTP {r.status_code})")
        else:
            return _result("webhook", False, f"HTTP {r.status_code}: {r.text[:200]}")
    except requests.exceptions.Timeout:
        return _result("webhook", False, "Request timed out (15s)")
    except Exception as e:
        return _result("webhook", False, f"{type(e).__name__}: {e}")


# ──────────────────────────────────────────────────────────────────
# 4. Email digest (uses existing SMTP_EMAIL/SMTP_PASSWORD)
# ──────────────────────────────────────────────────────────────────
def publish_to_email(post, recipients: Optional[list[str]] = None) -> dict:
    """
    Email the post to a recipient list as an HTML digest with embedded image.

    Setup: same SMTP_EMAIL/SMTP_PASSWORD as the lead outreach module.

    Recipients default to MARKETING_DIGEST_RECIPIENTS in .env (comma-separated)
    or SMTP_EMAIL itself if no list is configured.
    """
    if not settings.SMTP_EMAIL or not settings.SMTP_PASSWORD:
        return _result("email", False, "SMTP_EMAIL/SMTP_PASSWORD not configured")

    if not recipients:
        if settings.MARKETING_DIGEST_RECIPIENTS:
            recipients = [r.strip() for r in settings.MARKETING_DIGEST_RECIPIENTS.split(",") if r.strip()]
        else:
            recipients = [settings.SMTP_EMAIL]

    if not recipients:
        return _result("email", False, "No recipients resolved")

    img_path = _image_path(post.image_filename)
    platforms = ", ".join(post.platforms or []) or "all platforms"

    msg = MIMEMultipart("related")
    msg["Subject"] = f"[SalesForge] New marketing post for {platforms}"
    msg["From"] = settings.SMTP_EMAIL
    msg["To"] = ", ".join(recipients)

    html_body = f"""\
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2563eb;">New Marketing Post Ready</h2>
        <p><strong>Target platforms:</strong> {platforms}</p>
        <p><strong>Post ID:</strong> #{post.id}</p>
        <hr>
        <div style="white-space: pre-wrap; font-size: 14px; line-height: 1.6;">{post.caption}</div>
        {'<hr><img src="cid:postimg" style="max-width: 100%; height: auto;">' if img_path else ''}
        <hr>
        <p style="color: #6b7280; font-size: 12px;">Sent by SalesForge AI · Marketing Module</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, "html"))

    if img_path:
        with open(img_path, "rb") as f:
            img = MIMEImage(f.read())
            img.add_header("Content-ID", "<postimg>")
            img.add_header("Content-Disposition", "inline", filename=img_path.name)
            msg.attach(img)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_EMAIL, recipients, msg.as_string())
        return _result("email", True, f"Sent to {len(recipients)} recipient(s)")
    except smtplib.SMTPAuthenticationError:
        return _result("email", False, "SMTP auth failed — check SMTP_EMAIL/SMTP_PASSWORD (Gmail App Password required)")
    except Exception as e:
        return _result("email", False, f"{type(e).__name__}: {e}")


# ──────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────
CHANNEL_FUNCTIONS = {
    "discord": publish_to_discord,
    "telegram": publish_to_telegram,
    "webhook": publish_to_webhook,
    "email": publish_to_email,
}


def publish_to_channels(post, channels: list[str]) -> list[dict]:
    """
    Try to publish a post to every channel in `channels`. Returns a list of
    per-channel result dicts. One channel's failure does not affect the others.

    Falls back to a no-op success result if `channels` is empty (preserves the
    old "scheduled in DB only" behaviour for backwards compat).
    """
    if not channels:
        return [{
            "channel": "stub",
            "success": True,
            "timestamp": _now(),
            "detail": "No channels configured — DB-only publish (legacy mode)",
            "external_id": None,
        }]

    results = []
    for ch in channels:
        fn = CHANNEL_FUNCTIONS.get(ch)
        if not fn:
            results.append(_result(ch, False, f"Unknown channel '{ch}'"))
            continue
        try:
            results.append(fn(post))
        except Exception as e:
            # Defensive — fn should never raise but just in case
            logger.exception("Channel %s raised", ch)
            results.append(_result(ch, False, f"Unhandled: {type(e).__name__}: {e}"))
    return results


def get_channel_status() -> dict:
    """
    Report which channels are currently configured (without exposing secrets).
    Useful for the frontend's channel picker — disable channels not yet set up.
    """
    return {
        "discord": bool(settings.DISCORD_WEBHOOK_URL),
        "telegram": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
        "webhook": bool(settings.GENERIC_WEBHOOK_URL),
        "email": bool(settings.SMTP_EMAIL and settings.SMTP_PASSWORD),
    }
