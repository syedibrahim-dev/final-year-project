from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from utils.database import get_db
from utils.dependencies import get_current_user
from models.user import User
from models.inventory import Product, Store, InventoryForecast, StockAlert
from services.inventory_service import generate_forecast

router = APIRouter(prefix="/inventory", tags=["Inventory"])

@router.get("/products")
def get_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all products and their current stock for the user's organization"""
    products = db.query(Product).join(Store).filter(
        Store.organization_id == current_user.organization_id
    ).all()
    
    result = []
    for p in products:
        # Get latest forecast
        latest_forecast = db.query(InventoryForecast).filter(
            InventoryForecast.product_id == p.id
        ).order_by(InventoryForecast.forecast_date.desc()).first()
        
        result.append({
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "store": p.store.name,
            "current_stock": p.current_stock,
            "reorder_point": p.reorder_point,
            "price": p.price,
            "predicted_depletion_date": latest_forecast.predicted_depletion_date if latest_forecast else None
        })
        
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
