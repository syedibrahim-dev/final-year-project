"""
Customer Analytics Routes
=========================

Exposes RFM segmentation, BG/NBD Customer Lifetime Value, and cohort
retention endpoints. Scoped to the current user's organisation.

Endpoints:
  GET /analytics/rfm              → RFM scoring + segment summary
  GET /analytics/clv              → BG/NBD predicted customer lifetime value
  GET /analytics/cohort-retention → monthly cohort retention matrix
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from utils.database import get_db
from utils.dependencies import get_current_user
from models.user import User
from models.inventory import Store, Product, SalesTransaction, Customer
from sqlalchemy import func

from services.customer_analytics_service import (
    compute_rfm,
    compute_clv,
    compute_cohort_retention,
)

router = APIRouter(prefix="/analytics", tags=["Customer Analytics"])


@router.get("/stores")
def list_stores(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all stores in the current user's organisation along with
    per-store transaction / customer / product counts. Used by the
    frontend store-selector on the customer analytics page.
    """
    stores = (
        db.query(Store)
        .filter(Store.organization_id == current_user.organization_id)
        .order_by(Store.id)
        .all()
    )

    result = []
    for s in stores:
        product_count = db.query(func.count(Product.id)).filter_by(store_id=s.id).scalar() or 0
        customer_count = db.query(func.count(Customer.id)).filter_by(store_id=s.id).scalar() or 0
        txn_count = (
            db.query(func.count(SalesTransaction.id))
            .join(Product, Product.id == SalesTransaction.product_id)
            .filter(Product.store_id == s.id)
            .scalar()
            or 0
        )
        result.append({
            "id": s.id,
            "name": s.name,
            "platform": s.platform,
            "product_count": product_count,
            "customer_count": customer_count,
            "transaction_count": txn_count,
        })
    return {"stores": result}


@router.get("/rfm")
def get_rfm_segmentation(
    store_id: int | None = Query(None, description="Scope to a single store (optional)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    RFM (Recency / Frequency / Monetary) customer segmentation.

    Returns quintile scores (1-5 per dimension) and a labelled segment
    (Champions, Loyal, At-Risk, etc.) for every customer in the org.

    Reference: Hughes (1994) "Strategic Database Marketing"
    """
    try:
        org_id = current_user.organization_id
        result = compute_rfm(db, org_id=org_id, store_id=store_id)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RFM computation failed: {str(e)}",
        )


@router.get("/clv")
def get_customer_lifetime_value(
    store_id: int | None = Query(None, description="Scope to a single store (optional)"),
    forecast_months: int = Query(12, ge=1, le=36, description="Prediction horizon (months)"),
    discount_rate: float = Query(0.01, ge=0.0, le=0.5, description="Monthly discount rate for NPV"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    BG/NBD + Gamma-Gamma Customer Lifetime Value prediction.

    Uses the `lifetimes` library to fit a BG/NBD model (predicted purchase
    count) and a Gamma-Gamma model (predicted avg order value), then
    combines them into a discounted CLV over `forecast_months`.

    Reference: Fader, Hardie & Lee (2005) "RFM and CLV: Using Iso-value
    Curves for Customer Base Analysis." Journal of Marketing Research.
    """
    try:
        org_id = current_user.organization_id
        result = compute_clv(
            db,
            org_id=org_id,
            store_id=store_id,
            forecast_months=forecast_months,
            discount_rate=discount_rate,
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CLV computation failed: {str(e)}",
        )


@router.get("/cohort-retention")
def get_cohort_retention(
    store_id: int | None = Query(None, description="Scope to a single store (optional)"),
    max_months: int = Query(12, ge=1, le=24, description="Months of retention to report per cohort"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Monthly cohort retention analysis.

    Groups customers by their first-purchase month, then tracks the
    percentage of each cohort that returned in subsequent months.

    Output is structured as cohorts × month_offset retention percentages,
    suitable for rendering as a triangular heatmap on the frontend.
    """
    try:
        org_id = current_user.organization_id
        result = compute_cohort_retention(
            db,
            org_id=org_id,
            store_id=store_id,
            max_months=max_months,
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cohort retention failed: {str(e)}",
        )
