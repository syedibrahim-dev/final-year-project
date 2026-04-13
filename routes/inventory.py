from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload, aliased
from sqlalchemy import func
from typing import List, Dict, Any
from utils.database import get_db
from utils.dependencies import get_current_user, role_required
from models.user import User
from models.inventory import Product, Store, InventoryForecast, StockAlert
from services.inventory_service import generate_forecast, refresh_all_forecasts

router = APIRouter(prefix="/inventory", tags=["Inventory"])

@router.get("/products")
def get_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all products + their current stock + their LATEST forecast for the
    user's organization in a SINGLE query (no N+1).

    Strategy:
      1. Subquery: max(forecast_date) per product_id
      2. Outer join Product → Store (for store name) → InventoryForecast
         filtered to that max date
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
    rows = (
        db.query(Product, Store.name.label("store_name"), InventoryForecast)
        .join(Store, Product.store_id == Store.id)
        .outerjoin(latest_dates, latest_dates.c.pid == Product.id)
        .outerjoin(
            InventoryForecast,
            (InventoryForecast.product_id == Product.id)
            & (InventoryForecast.forecast_date == latest_dates.c.max_date),
        )
        .filter(Store.organization_id == current_user.organization_id)
        .all()
    )

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all active stock alerts for the user's organization"""
    alerts = db.query(StockAlert).join(Product).join(Store).filter(
        Store.organization_id == current_user.organization_id,
        StockAlert.is_resolved == False
    ).order_by(StockAlert.created_at.desc()).all()

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
    Manual trigger for the bulk forecast refresh job.

    Normally APScheduler runs this every 6 hours, but admins can hit this
    endpoint to force a fresh forecast across all products immediately —
    useful before a quarterly review or after bulk-importing sales data.

    Returns a summary with succeeded/failed counts and the first 10 errors.
    """
    summary = refresh_all_forecasts(db)
    return summary
