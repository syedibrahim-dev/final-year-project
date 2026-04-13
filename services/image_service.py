"""
Image Generation Service
Calls the Colab-hosted FLUX.1-dev-fp8 API to generate marketing images.
Images are saved to media/marketing/ and served via /marketing/images/{filename}.

Uses an async job pattern so the HTTP request returns immediately:
  1. POST /generate-image/start  → {job_id}          (returns in <1 s)
  2. GET  /jobs/{job_id}         → {status, result}   (poll every 5 s)

Runtime URL override:
  The Colab ngrok URL changes on every Colab restart. Instead of editing
  settings.py + restarting the backend, the admin can update the URL at
  runtime via PATCH /marketing/settings/image-url. The new URL is held in
  module memory and survives until the next backend restart.

Graceful degradation:
  If no URL is set (neither .env nor runtime override), or the URL is
  unreachable, image generation fails fast with a clear error. The marketing
  module still works for caption-only posts.
"""
import requests
import base64
import uuid
import threading
from pathlib import Path
from typing import Optional
from config.settings import settings

# Local media directory — created on first use
MEDIA_DIR = Path(__file__).parent.parent / "media" / "marketing"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# ─── Runtime URL override ────────────────────────────────────────────────────
# Lives in module memory; admin updates via PATCH /marketing/settings/image-url.
# Resets to settings.IMAGE_GEN_URL on backend restart.
_runtime_url: Optional[str] = None
_url_lock = threading.Lock()


def get_image_url() -> Optional[str]:
    """Effective image gen URL: runtime override > settings > None."""
    with _url_lock:
        return _runtime_url or settings.IMAGE_GEN_URL


def set_image_url(new_url: Optional[str]) -> None:
    """Admin endpoint hook — set the runtime URL override."""
    global _runtime_url
    with _url_lock:
        _runtime_url = (new_url or "").strip() or None
    print(f"🔧 Image gen URL updated to: {_runtime_url or '(unset — using settings default)'}")


def check_image_service_health(timeout: int = 5) -> dict:
    """
    Probe the image gen URL with a short HEAD/GET to see if it's reachable.
    Returns {url, configured, reachable, latency_ms, error}.
    Used by GET /marketing/settings/image-url and the frontend's health badge.
    """
    url = get_image_url()
    if not url:
        return {
            "url": None,
            "configured": False,
            "reachable": False,
            "latency_ms": None,
            "error": "No URL configured (IMAGE_GEN_URL unset and no runtime override)",
        }

    import time
    start = time.monotonic()
    try:
        # Probe the root path. Colab notebook usually responds with 200 or 404
        # to GET / — both prove the tunnel is alive. Anything that returns an
        # HTTP status (even 5xx) means the server exists.
        r = _session.get(url.rstrip("/") + "/", timeout=timeout)
        latency = int((time.monotonic() - start) * 1000)
        return {
            "url": url,
            "configured": True,
            "reachable": True,
            "latency_ms": latency,
            "status_code": r.status_code,
            "error": None,
        }
    except requests.exceptions.ConnectionError:
        return {
            "url": url,
            "configured": True,
            "reachable": False,
            "latency_ms": None,
            "error": "Connection refused — Colab/ngrok tunnel may have died. Restart Colab and update the URL.",
        }
    except requests.exceptions.Timeout:
        return {
            "url": url,
            "configured": True,
            "reachable": False,
            "latency_ms": None,
            "error": f"No response within {timeout}s",
        }
    except Exception as e:
        return {
            "url": url,
            "configured": True,
            "reachable": False,
            "latency_ms": None,
            "error": f"{type(e).__name__}: {e}",
        }

# Ngrok adds a browser redirect page for free-tier URLs.
# This header bypasses it for programmatic requests.
NGROK_HEADERS = {
    "ngrok-skip-browser-warning": "true",
    "Content-Type": "application/json",
}

# ─── HTTP session with keep-alive ────────────────────────────────────────────
# A persistent session uses HTTP keep-alive, which helps maintain the
# connection through ngrok's free-tier tunnel during long generations.
_session = requests.Session()
_session.headers.update(NGROK_HEADERS)

# Timeout: (connect_timeout, read_timeout)
#   - 30s to establish the TCP connection (if Colab/ngrok is unreachable, fail fast)
#   - None for read = wait indefinitely for the response (images take 7-10+ min)
# We do NOT retry on failure because retrying sends a NEW generation request
# to Colab, which starts the image from scratch and can cause GPU OOM.
CONNECT_TIMEOUT = 30
READ_TIMEOUT = None  # wait as long as Colab needs

# ─── In-memory job store ─────────────────────────────────────────────────────
# Keyed by job_id (UUID hex string).
# Each value: {"status": "pending"|"done"|"failed", "result": {...}, "error": "..."}
#
# This lives in process memory — jobs are lost on server restart, which is fine
# for a FYP. A production system would use Redis.
_jobs: dict = {}
_jobs_lock = threading.Lock()


def _call_colab_api(
    prompt: str,
    width: int,
    height: int,
    steps: int,
    seed: int,
    base_url: str = None,
) -> dict:
    """
    Blocking call to the Colab FLUX API.
    Uses a keep-alive session and unlimited read timeout.
    Does NOT retry — retrying would start a new generation on Colab.
    Returns {success, image_filename, image_base64, seed}.

    Raises RuntimeError immediately if no image gen URL is configured.
    """
    effective_url = base_url or get_image_url()
    if not effective_url:
        raise RuntimeError(
            "No image gen URL configured. Set IMAGE_GEN_URL in .env or update via "
            "PATCH /marketing/settings/image-url. Marketing posts work without images — "
            "skip the image generation step."
        )
    url = effective_url.rstrip("/") + "/generate"

    payload = {
        "prompt": prompt,
        "width": min(width, 1280),
        "height": min(height, 1280),
        "steps": steps,
        "seed": seed,
        "response_format": "base64",
    }

    print(f"🎨 Calling image gen API  prompt='{prompt[:60]}...'")
    response = _session.post(url, json=payload, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    response.raise_for_status()
    data = response.json()

    if not data.get("success"):
        raise RuntimeError(data.get("error", "API returned success=false"))

    raw_bytes = base64.b64decode(data["image_base64"])
    filename = f"{uuid.uuid4().hex}.png"
    filepath = MEDIA_DIR / filename

    with open(filepath, "wb") as f:
        f.write(raw_bytes)

    print(f"✅ Image saved: {filename}  ({len(raw_bytes) // 1024} KB)")

    return {
        "success": True,
        "image_filename": filename,
        "image_base64": data["image_base64"],
        "seed": data.get("seed", 0),
    }


# ─── Public API ───────────────────────────────────────────────────────────────

def start_image_job(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    seed: int = 0,
) -> str:
    """
    Start image generation in a background thread and return a job_id immediately.
    Poll get_job_status(job_id) to check progress.
    """
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {"status": "pending", "result": None, "error": None}

    def _worker():
        try:
            result = _call_colab_api(prompt, width, height, steps, seed)
            with _jobs_lock:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["result"] = result
        except requests.exceptions.ConnectionError:
            msg = (
                "Cannot connect to image generation server. "
                "Make sure Colab is running and the ngrok URL is correct."
            )
            print(f"❌ {msg}")
            with _jobs_lock:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = msg
        except Exception as e:
            print(f"❌ Image generation error: {e}")
            with _jobs_lock:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = str(e)

    threading.Thread(target=_worker, daemon=True).start()
    print(f"🚀 Image job {job_id} started in background thread")
    return job_id


def get_job_status(job_id: str) -> dict | None:
    """
    Return current job state, or None if job_id is unknown.
    Shape: {status: 'pending'|'done'|'failed', result: {...}|None, error: str|None}
    """
    with _jobs_lock:
        return _jobs.get(job_id)


# Keep the old synchronous function for internal/service use
def generate_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    seed: int = 0,
    base_url: str = None,
) -> dict:
    """Synchronous wrapper — use start_image_job() from API routes instead."""
    try:
        return _call_colab_api(prompt, width, height, steps, seed, base_url)
    except requests.exceptions.ConnectionError:
        msg = "Cannot connect to image generation server."
        return {"success": False, "error": msg}
    except Exception as e:
        return {"success": False, "error": str(e)}
