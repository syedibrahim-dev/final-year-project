import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.inventory import Product, SalesTransaction, InventoryForecast, StockAlert, Store

logger = logging.getLogger(__name__)

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    print("WARNING: Prophet library is not installed. Will fallback to EWMA for all forecasts.")

def generate_forecast(db: Session, org_id: int, product_id: int) -> dict:
    """
    Generate inventory forecast for a product using Prophet or EWMA.
    """
    # Verify product belongs to organization
    product = db.query(Product).join(Store).filter(
        Product.id == product_id,
        Store.organization_id == org_id
    ).first()
    
    if not product:
        raise ValueError("Product not found or access denied")
        
    # Get sales history
    transactions = db.query(SalesTransaction).filter(
        SalesTransaction.product_id == product_id
    ).order_by(SalesTransaction.sale_date).all()
    
    if not transactions:
        raise ValueError("No sales history available for forecasting")
        
    # Aggregate sales by date
    df = pd.DataFrame([{
        'ds': t.sale_date.date(),
        'y': t.quantity
    } for t in transactions])
    
    # Group by date and sum quantities
    daily_sales = df.groupby('ds')['y'].sum().reset_index()
    daily_sales['ds'] = pd.to_datetime(daily_sales['ds'])
    
    # Fill missing dates with 0
    date_range = pd.date_range(start=daily_sales['ds'].min(), end=daily_sales['ds'].max())
    daily_sales = daily_sales.set_index('ds').reindex(date_range, fill_value=0).reset_index()
    daily_sales.columns = ['ds', 'y']
    
    days_of_data = len(daily_sales)
    current_stock = product.current_stock
    
    if days_of_data >= 35 and PROPHET_AVAILABLE:
        # Use Prophet
        predicted_depletion_date, conf_score = _forecast_prophet(daily_sales, current_stock)
        model_used = 'prophet'
    else:
        # Fallback to EWMA
        predicted_depletion_date, conf_score = _forecast_ewma(daily_sales, current_stock)
        model_used = 'ewma'
        
    # Save the forecast
    forecast = InventoryForecast(
        product_id=product_id,
        predicted_depletion_date=predicted_depletion_date,
        model_used=model_used,
        confidence_score=conf_score
    )
    db.add(forecast)
    
    # Update or create alert if necessary
    _manage_alerts(db, product, predicted_depletion_date)
    
    db.commit()
    
    return {
        "product_id": product_id,
        "product_name": product.name,
        "current_stock": current_stock,
        "predicted_depletion_date": predicted_depletion_date.isoformat() if predicted_depletion_date else None,
        "model_used": model_used,
        "confidence_score": conf_score
    }
    
def _forecast_prophet(df: pd.DataFrame, current_stock: int):
    """
    Forecast using Meta's Prophet.
    Returns predicted depletion date and confidence score.
    """
    if current_stock <= 0:
        return datetime.utcnow(), 1.0
        
    m = Prophet(daily_seasonality=True, yearly_seasonality=False)
    m.fit(df)
    
    # Predict up to 90 days into future
    future = m.make_future_dataframe(periods=90)
    forecast = m.predict(future)
    
    # Get only future predictions
    last_date = df['ds'].max()
    future_forecast = forecast[forecast['ds'] > last_date].copy()
    
    # Ensure no negative predictions for sales
    future_forecast['yhat'] = future_forecast['yhat'].clip(lower=0)
    
    remaining_stock = current_stock
    depletion_date = None
    
    for _, row in future_forecast.iterrows():
        predicted_sale = row['yhat']
        remaining_stock -= predicted_sale
        
        if remaining_stock <= 0:
            depletion_date = row['ds'].to_pydatetime()
            break
            
    # Calculate simple confidence score based on error bounds width
    conf_score = 0.8 # baseline
    if depletion_date:
        # Adjust based on variance ratio
        avg_yhat = forecast['yhat'].mean()
        if avg_yhat > 0:
            variance = (forecast['yhat_upper'] - forecast['yhat_lower']).mean() / avg_yhat
            conf_score = max(0.1, min(0.95, 1.0 - (variance * 0.1)))
            
    return depletion_date, round(conf_score, 2)

def _forecast_ewma(df: pd.DataFrame, current_stock: int):
    """
    Forecast using Exponentially Weighted Moving Average.
    """
    if current_stock <= 0:
        return datetime.utcnow(), 1.0
        
    if len(df) == 0:
        return None, 0.0
        
    # Calculate EWMA
    span = min(14, len(df)) # Use up to 14 days for span
    ewma = df['y'].ewm(span=span, adjust=False).mean()
    
    latest_velocity = ewma.iloc[-1]
    
    # Calculate trend acceleration (difference between short term and long term EWMA)
    if len(df) >= 7:
        short_ewma = df['y'].ewm(span=3, adjust=False).mean().iloc[-1]
        acceleration = short_ewma - latest_velocity
        # Apply gentle acceleration bounded to not go negative
        daily_velocity = max(0.1, latest_velocity + (acceleration * 0.5))
    else:
        daily_velocity = max(0.1, latest_velocity)
        
    if daily_velocity < 0.01:
        # Too slow to predict
        return None, 0.0
        
    days_to_depletion = current_stock / daily_velocity
    
    # Cap at 180 days (6 months)
    if days_to_depletion > 180:
        return None, 0.4
        
    depletion_date = datetime.utcnow() + timedelta(days=days_to_depletion)
    return depletion_date, 0.60 # Lower confidence than prophet

def _manage_alerts(db: Session, product: Product, depletion_date: datetime):
    """
    Create or resolve stock alerts based on current stock and forecast.

    Alert types in order of urgency:
      1. OUT_OF_STOCK         — current_stock ≤ 0
      2. LOW_STOCK            — current_stock ≤ reorder_point already
      3. REORDER_SOON         — forecast says we'll hit reorder_point in ≤ REORDER_LEAD_TIME days
                                (this is the new key alert — gives buying lead time)
      4. DEPLETION_WARNING    — forecast says we'll hit zero in ≤ 14 days
                                (last-resort alert, kept for urgency)

    Why the new REORDER_SOON tier:
      The old code only warned 14 days before depletion, which is often too late
      for products with long supplier lead times. Real inventory systems trigger
      reordering when stock will hit the reorder_point — not when it hits zero.
    """
    REORDER_LEAD_TIME_DAYS = 14   # warn 14 days before predicted reorder
    DEPLETION_WARNING_DAYS = 14   # last-resort warning, still useful

    now = datetime.utcnow()
    existing_alert = db.query(StockAlert).filter(
        StockAlert.product_id == product.id,
        StockAlert.is_resolved == False,
    ).first()

    needs_alert = False
    alert_type = None
    message = None

    if product.current_stock <= 0:
        needs_alert = True
        alert_type = "OUT_OF_STOCK"
        message = f"{product.name} is out of stock."

    elif product.current_stock <= product.reorder_point:
        needs_alert = True
        alert_type = "LOW_STOCK"
        message = (
            f"{product.name} has reached reorder point "
            f"({product.current_stock} remaining, threshold {product.reorder_point})."
        )

    elif depletion_date:
        days_to_zero = (depletion_date - now).days

        if days_to_zero <= 0:
            needs_alert = True
            alert_type = "OUT_OF_STOCK"
            message = f"{product.name} forecast indicates depletion (date already passed)."

        elif days_to_zero <= DEPLETION_WARNING_DAYS:
            needs_alert = True
            alert_type = "DEPLETION_WARNING"
            message = f"{product.name} is forecasted to run out in {days_to_zero} days."

        else:
            # Compute when we'll hit reorder_point — this is the more useful warning.
            # velocity = (current_stock - 0) / days_to_zero  →  units/day burn rate
            # units_until_reorder = current_stock - reorder_point
            # days_to_reorder = units_until_reorder / velocity
            if days_to_zero > 0 and product.current_stock > product.reorder_point:
                velocity = product.current_stock / days_to_zero  # units per day
                units_until_reorder = product.current_stock - product.reorder_point
                days_to_reorder = int(units_until_reorder / velocity) if velocity > 0 else None

                if days_to_reorder is not None and days_to_reorder <= REORDER_LEAD_TIME_DAYS:
                    needs_alert = True
                    alert_type = "REORDER_SOON"
                    message = (
                        f"{product.name} will hit reorder point ({product.reorder_point} units) "
                        f"in ~{days_to_reorder} days. Place an order now to avoid stockout."
                    )

    if needs_alert:
        if existing_alert:
            if existing_alert.alert_type != alert_type or existing_alert.message != message:
                existing_alert.alert_type = alert_type
                existing_alert.message = message
        else:
            db.add(StockAlert(
                product_id=product.id,
                alert_type=alert_type,
                message=message,
            ))
    else:
        if existing_alert:
            existing_alert.is_resolved = True
            existing_alert.resolved_at = now


# ─── Bulk forecast refresh (called by APScheduler every 6 hours) ──────────────

def refresh_all_forecasts(db: Session) -> dict:
    """
    Re-forecast every product across every organisation that has at least one
    sales transaction. Called by the APScheduler job in main.py and also
    available as a manual admin endpoint trigger.

    Returns a summary dict with counts. Errors on individual products are
    logged but don't stop the loop.
    """
    started = datetime.utcnow()

    # Find all products that have at least one sales transaction.
    # Skipping products with zero sales saves work AND avoids the
    # "No sales history" ValueError from generate_forecast.
    product_ids_with_sales = (
        db.query(SalesTransaction.product_id)
        .distinct()
        .all()
    )
    product_ids = [pid for (pid,) in product_ids_with_sales]

    if not product_ids:
        return {
            "ran_at": started.isoformat(),
            "duration_seconds": 0,
            "products_total": 0,
            "products_succeeded": 0,
            "products_failed": 0,
            "errors": [],
        }

    # Get product → org_id mapping in a single query (so generate_forecast
    # can do its org_id verification without us hitting N queries here).
    product_org_map = (
        db.query(Product.id, Store.organization_id)
        .join(Store, Product.store_id == Store.id)
        .filter(Product.id.in_(product_ids))
        .all()
    )

    succeeded = 0
    failed = 0
    errors = []

    for product_id, org_id in product_org_map:
        try:
            generate_forecast(db, org_id, product_id)
            succeeded += 1
        except ValueError as ve:
            # Expected: "No sales history" or "Product not found"
            failed += 1
            errors.append({"product_id": product_id, "error": str(ve)})
            logger.debug(f"Skipping product {product_id}: {ve}")
        except Exception as e:
            failed += 1
            errors.append({"product_id": product_id, "error": str(e)})
            logger.exception(f"Forecast failed for product {product_id}")

    duration = (datetime.utcnow() - started).total_seconds()
    summary = {
        "ran_at": started.isoformat(),
        "duration_seconds": round(duration, 2),
        "products_total": len(product_ids),
        "products_succeeded": succeeded,
        "products_failed": failed,
        "errors": errors[:10],  # cap to avoid huge logs
    }
    print(f"📊 Forecast refresh complete: {succeeded}/{len(product_ids)} succeeded in {duration:.1f}s")
    return summary
