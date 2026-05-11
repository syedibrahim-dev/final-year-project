"""
Forecast Jobs Service
======================

In-memory background job registry for bulk inventory forecast refresh.

Why in-memory? FYP-scale persistence isn't needed — jobs complete within
minutes to hours and results (the InventoryForecast + StockAlert rows)
are persisted to the DB by `generate_forecast`. The registry just tracks
live progress so the UI can poll it.

For production you'd replace this with Redis / Celery / SQLAlchemy-backed
job table, but the interface (`start_job`, `get_job`, `serialize_job`)
stays the same.

Thread-safety: all reads/writes to `_JOBS` go through `_LOCK`.
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.inventory import Product, Store, SalesTransaction
from utils.database import SessionLocal

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  REGISTRY
# ══════════════════════════════════════════════════════════════════

_JOBS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()

# Keep finished jobs around for this long so the UI can display the
# "last completed" state after the poll finishes.
_JOB_TTL_SECONDS = 3600  # 1 hour

# Cap error payload size so a catastrophic run doesn't balloon memory
_MAX_ERRORS_RETAINED = 10


def _cleanup_old_jobs() -> None:
    """Drop finished jobs older than the TTL."""
    now = datetime.utcnow()
    with _LOCK:
        to_remove = [
            jid for jid, job in _JOBS.items()
            if job["status"] in ("succeeded", "failed")
            and job.get("finished_at")
            and (now - job["finished_at"]).total_seconds() > _JOB_TTL_SECONDS
        ]
        for jid in to_remove:
            del _JOBS[jid]


def _create_job(store_id: Optional[int], org_id: int) -> Dict[str, Any]:
    """
    Register a new job entry. Raises ValueError if another job for the
    same (org, store) scope is already running.
    """
    _cleanup_old_jobs()

    with _LOCK:
        for existing in _JOBS.values():
            if (
                existing["org_id"] == org_id
                and existing["store_id"] == store_id
                and existing["status"] in ("queued", "running")
            ):
                raise ValueError(
                    f"A forecast job is already running for this scope "
                    f"(job_id={existing['id']})"
                )

        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "store_id": store_id,
            "org_id": org_id,
            "status": "queued",   # queued → running → succeeded | failed
            "total": 0,
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "errors": [],
            "last_product_name": None,
            "started_at": datetime.utcnow(),
            "finished_at": None,
        }
        _JOBS[job_id] = job
        return job


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Return the raw job dict (or None). Caller should not mutate."""
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def list_jobs(org_id: int) -> List[Dict[str, Any]]:
    """Return all jobs for an org (useful for admin views)."""
    with _LOCK:
        return [dict(j) for j in _JOBS.values() if j["org_id"] == org_id]


def serialize_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-safe snapshot with a computed progress percentage."""
    total = job.get("total", 0) or 0
    processed = job.get("processed", 0) or 0
    return {
        "id": job["id"],
        "store_id": job.get("store_id"),
        "status": job["status"],
        "total": total,
        "processed": processed,
        "succeeded": job.get("succeeded", 0),
        "failed": job.get("failed", 0),
        "errors": job.get("errors", []),
        "last_product_name": job.get("last_product_name"),
        "started_at": job["started_at"].isoformat() if job.get("started_at") else None,
        "finished_at": job["finished_at"].isoformat() if job.get("finished_at") else None,
        "progress_pct": round(processed / total * 100, 1) if total > 0 else 0.0,
    }


# ══════════════════════════════════════════════════════════════════
#  WORKER
# ══════════════════════════════════════════════════════════════════

def _set(job_id: str, **updates) -> None:
    """Atomically update fields on a job."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if job:
            job.update(updates)


def _increment(job_id: str, field: str, by: int = 1) -> None:
    """Atomically bump a counter field."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if job:
            job[field] = job.get(field, 0) + by


def _append_error(job_id: str, error: Dict[str, Any]) -> None:
    """Append an error entry (capped)."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if job and len(job["errors"]) < _MAX_ERRORS_RETAINED:
            job["errors"].append(error)


def _run_job(job_id: str) -> None:
    """
    Thread target: iterates every product in scope, calls generate_forecast,
    updates progress. One DB session per job so the worker thread has its
    own connection (FastAPI's request-scoped get_db dependency doesn't apply
    in a background thread).
    """
    # Lazy import to avoid circular (inventory_service imports our registry? no,
    # but keeping this pattern anyway)
    from services.inventory_service import generate_forecast

    job = get_job(job_id)
    if job is None:
        logger.error(f"run_job: job {job_id} vanished before start")
        return

    db: Session = SessionLocal()
    try:
        # Resolve products in scope: must have at least one sale
        q = (
            db.query(Product.id, Product.name)
            .join(Store, Store.id == Product.store_id)
            .join(SalesTransaction, SalesTransaction.product_id == Product.id)
            .filter(Store.organization_id == job["org_id"])
            .group_by(Product.id, Product.name)
        )
        if job["store_id"] is not None:
            q = q.filter(Product.store_id == job["store_id"])

        products = q.all()

        _set(job_id, total=len(products), status="running")

        if not products:
            _set(
                job_id,
                status="succeeded",
                finished_at=datetime.utcnow(),
            )
            return

        for pid, pname in products:
            try:
                generate_forecast(db, job["org_id"], pid)
                _increment(job_id, "processed")
                _increment(job_id, "succeeded")
                _set(job_id, last_product_name=pname)
            except Exception as e:
                _increment(job_id, "processed")
                _increment(job_id, "failed")
                _append_error(job_id, {
                    "product_id": pid,
                    "product_name": (pname or "")[:80],
                    "error": str(e)[:200],
                })
                logger.warning(
                    f"[forecast_job {job_id}] Product {pid} forecast failed: {e}"
                )

        _set(job_id, status="succeeded", finished_at=datetime.utcnow())
        logger.info(
            f"[forecast_job {job_id}] Done — {job['succeeded'] if (job := get_job(job_id)) else '?'} succeeded"
        )

    except Exception as e:
        logger.error(f"[forecast_job {job_id}] Crashed: {e}")
        import traceback
        traceback.print_exc()
        _append_error(job_id, {"error": f"Job crashed: {str(e)[:200]}"})
        _set(job_id, status="failed", finished_at=datetime.utcnow())
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════

def start_job(store_id: Optional[int], org_id: int) -> Dict[str, Any]:
    """
    Create a forecast refresh job and launch its worker thread.
    Returns the initial job snapshot (status='queued').
    """
    job = _create_job(store_id=store_id, org_id=org_id)
    thread = threading.Thread(target=_run_job, args=(job["id"],), daemon=True)
    thread.start()
    return job
