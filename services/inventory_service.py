import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.inventory import Product, SalesTransaction, InventoryForecast, StockAlert, Store

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
    Create or resolve alerts based on current stock and depletion date.
    """
    now = datetime.utcnow()
    existing_alert = db.query(StockAlert).filter(
        StockAlert.product_id == product.id,
        StockAlert.is_resolved == False
    ).first()
    
    needs_alert = False
    alert_type = None
    message = None
    
    if product.current_stock <= 0:
        needs_alert = True
        alert_type = "OUT_OF_STOCK"
        message = f"Product {product.name} is out of stock!"
    elif product.current_stock <= product.reorder_point:
        needs_alert = True
        alert_type = "LOW_STOCK"
        message = f"Product {product.name} has reached reorder point ({product.current_stock} remaining)."
    elif depletion_date and (depletion_date - now).days <= 14:
        needs_alert = True
        alert_type = "DEPLETION_WARNING"
        days_left = (depletion_date - now).days
        message = f"Product {product.name} is forecasted to run out in {days_left} days."
        
    if needs_alert:
        if existing_alert:
            # Update existing alert if type changed
            if existing_alert.alert_type != alert_type:
                existing_alert.alert_type = alert_type
                existing_alert.message = message
        else:
            # Create new alert
            new_alert = StockAlert(
                product_id=product.id,
                alert_type=alert_type,
                message=message
            )
            db.add(new_alert)
    else:
        if existing_alert:
            # Resolve existing alert
            existing_alert.is_resolved = True
            existing_alert.resolved_at = now
