from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload, aliased
from sqlalchemy import func

from utils.database import get_db
from utils.dependencies import get_current_user, role_required
from models.user import User
from models.inventory import Product, Store, InventoryForecast, StockAlert
from services.inventory_service import generate_forecast, refresh_all_forecasts
from services.forecast_jobs import start_job, get_job, serialize_job

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("/products")
def get_products(
    store_id: Optional[int] = Query(None, description="Scope to a single store (optional)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all products + their current stock + their LATEST forecast for the
    user's organization in a SINGLE query (no N+1). Pass `store_id` to scope
    to a specific store.
    """
    # Subquery: latest forecast date per product
    latest_dates = (
        db.query(
            InventoryForecast.product_id.label("pid"),
            func.max(InventoryForecast.forecast_date).label("max_date"),
        )
        .group_by(InventoryForecast.product_id)
        .subquery()
    )

    # Single query: products + store + (optional) latest forecast row
    q = (
        db.query(Product, Store.name.label("store_name"), InventoryForecast)
        .join(Store, Product.store_id == Store.id)
        .outerjoin(latest_dates, latest_dates.c.pid == Product.id)
        .outerjoin(
            InventoryForecast,
            (InventoryForecast.product_id == Product.id)
            & (InventoryForecast.forecast_date == latest_dates.c.max_date),
        )
        .filter(Store.organization_id == current_user.organization_id)
    )
    if store_id is not None:
        q = q.filter(Product.store_id == store_id)
    rows = q.all()

    result = [
        {
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "store": store_name,
            "current_stock": p.current_stock,
            "reorder_point": p.reorder_point,
            "price": p.price,
            "predicted_depletion_date": (
                forecast.predicted_depletion_date if forecast else None
            ),
            "model_used": forecast.model_used if forecast else None,
            "confidence_score": forecast.confidence_score if forecast else None,
            "last_forecast_at": forecast.forecast_date.isoformat() if forecast else None,
        }
        for p, store_name, forecast in rows
    ]

    return {"products": result}

@router.post("/forecast/{product_id}")
def trigger_forecast(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger an on-demand forecast for a specific product"""
    try:
        result = generate_forecast(db, current_user.organization_id, product_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forecasting error: {str(e)}"
        )

@router.get("/alerts")
def get_alerts(
    store_id: Optional[int] = Query(None, description="Scope to a single store (optional)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all active stock alerts for the user's organization"""
    q = db.query(StockAlert).join(Product).join(Store).filter(
        Store.organization_id == current_user.organization_id,
        StockAlert.is_resolved == False,
    )
    if store_id is not None:
        q = q.filter(Product.store_id == store_id)
    alerts = q.order_by(StockAlert.created_at.desc()).all()

    return {
        "alerts": [{
            "id": a.id,
            "product_id": a.product_id,
            "product_name": a.product.name,
            "alert_type": a.alert_type,
            "message": a.message,
            "created_at": a.created_at
        } for a in alerts]
    }


@router.post("/refresh-all-forecasts")
def trigger_refresh_all_forecasts(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "manager"])),
):
    """
    SYNCHRONOUS bulk refresh — kept for backward compatibility and admin
    scripts. Blocks the HTTP connection until every product is forecast.
    For stores with many products prefer the async variant
    (`/refresh-all-forecasts/async`) which returns a job id immediately.
    """
    summary = refresh_all_forecasts(db)
    return summary


@router.post("/refresh-all-forecasts/async")
def trigger_refresh_all_forecasts_async(
    store_id: Optional[int] = Query(None, description="Scope to a single store (optional)"),
    current_user: User = Depends(role_required(["admin", "manager"])),
):
    """
    Start a background forecast-refresh job. Returns the job id immediately
    so the frontend can poll `/inventory/refresh-jobs/{job_id}` for progress.
    Only one concurrent job per (org, store) scope is allowed.
    """
    try:
        job = start_job(store_id=store_id, org_id=current_user.organization_id)
        return serialize_job(job)
    except ValueError as e:
        # Another job is already running for this scope
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get("/refresh-jobs/{job_id}")
def get_refresh_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return live progress for a forecast refresh job."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found (may have expired)",
        )
    if job.get("org_id") != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this job",
        )
    return serialize_job(job)
