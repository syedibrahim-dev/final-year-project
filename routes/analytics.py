from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from utils.database import get_db
from utils.dependencies import get_current_user
from models.user import User

from services.analytics_service import (
    get_store_kpis,
    get_sales_trends,
    get_top_products,
    detect_sales_anomalies
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/dashboard")
def get_analytics_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all core analytics metrics for the dashboard view.
    Includes KPIs, top performing products, and daily sales trends.
    """
    try:
        org_id = current_user.organization_id
        
        kpis = get_store_kpis(db, org_id)
        trends = get_sales_trends(db, org_id, days=30)
        top_products = get_top_products(db, org_id, limit=5, days=30)
        anomalies = detect_sales_anomalies(db, org_id, days=60)
        
        return {
            "kpis": kpis,
            "trends": trends,
            "top_products": top_products,
            "anomalies": anomalies
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analytics error: {str(e)}"
        )

@router.get("/anomalies")
def get_anomalies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = 60
):
    """
    Get detailed breakdown of transaction anomalies.
    """
    try:
        org_id = current_user.organization_id
        anomalies = detect_sales_anomalies(db, org_id, days=days)
        return {"anomalies": anomalies}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection error: {str(e)}"
        )
