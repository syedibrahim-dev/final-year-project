import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.inventory import Store, Product, SalesTransaction

def get_store_kpis(db: Session, org_id: int):
    """
    Calculate KPIs: Total Revenue, Total Orders, Average Order Value (AOV),
    and % changes compared to the previous 30 days.
    """
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)

    # Current period stats
    current_transactions = db.query(
        func.sum(SalesTransaction.total_amount).label('revenue'),
        func.count(SalesTransaction.id).label('orders')
    ).join(Product).join(Store).filter(
        Store.organization_id == org_id,
        SalesTransaction.sale_date >= thirty_days_ago,
        SalesTransaction.sale_date <= now
    ).first()

    current_revenue = current_transactions.revenue or 0.0
    current_orders = current_transactions.orders or 0
    current_aov = current_revenue / current_orders if current_orders > 0 else 0.0

    # Previous period stats
    prev_transactions = db.query(
        func.sum(SalesTransaction.total_amount).label('revenue'),
        func.count(SalesTransaction.id).label('orders')
    ).join(Product).join(Store).filter(
        Store.organization_id == org_id,
        SalesTransaction.sale_date >= sixty_days_ago,
        SalesTransaction.sale_date < thirty_days_ago
    ).first()

    prev_revenue = prev_transactions.revenue or 0.0
    prev_orders = prev_transactions.orders or 0
    prev_aov = prev_revenue / prev_orders if prev_orders > 0 else 0.0

    def calc_growth(current, previous):
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 2)

    return {
        "revenue": {
            "value": round(current_revenue, 2),
            "growth": calc_growth(current_revenue, prev_revenue)
        },
        "orders": {
            "value": current_orders,
            "growth": calc_growth(current_orders, prev_orders)
        },
        "aov": {
            "value": round(current_aov, 2),
            "growth": calc_growth(current_aov, prev_aov)
        }
    }

def get_sales_trends(db: Session, org_id: int, days: int = 30):
    """
    Get daily revenue and sales volume for the past N days.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    transactions = db.query(SalesTransaction).join(Product).join(Store).filter(
        Store.organization_id == org_id,
        SalesTransaction.sale_date >= start_date
    ).all()
    
    if not transactions:
        return []
        
    df = pd.DataFrame([{
        'date': t.sale_date.date(),
        'revenue': t.total_amount or 0.0,
        'quantity': t.quantity
    } for t in transactions])
    
    daily_stats = df.groupby('date').agg({
        'revenue': 'sum',
        'quantity': 'sum'
    }).reset_index()
    
    # Fill missing dates with 0
    date_range = pd.date_range(start=start_date.date(), end=datetime.utcnow().date())
    daily_stats['date'] = pd.to_datetime(daily_stats['date'])
    daily_stats = daily_stats.set_index('date').reindex(date_range, fill_value=0).reset_index()
    daily_stats.columns = ['date', 'revenue', 'quantity']
    
    # Format for JSON
    daily_stats['date'] = daily_stats['date'].dt.strftime('%Y-%m-%d')
    daily_stats['revenue'] = daily_stats['revenue'].round(2)
    
    return daily_stats.to_dict('records')

def get_top_products(db: Session, org_id: int, limit: int = 5, days: int = 30):
    """
    Get top selling products by revenue and quantity over N days.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    top_revenue = db.query(
        Product.id,
        Product.name,
        Product.sku,
        func.sum(SalesTransaction.total_amount).label('total_revenue'),
        func.sum(SalesTransaction.quantity).label('total_quantity')
    ).join(SalesTransaction).join(Store).filter(
        Store.organization_id == org_id,
        SalesTransaction.sale_date >= start_date
    ).group_by(Product.id).order_by(
        func.sum(SalesTransaction.total_amount).desc()
    ).limit(limit).all()
    
    return [{
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "revenue": round(p.total_revenue or 0.0, 2),
        "quantity": int(p.total_quantity or 0)
    } for p in top_revenue]

def detect_sales_anomalies(db: Session, org_id: int, days: int = 60):
    """
    Detect statistical anomalies in daily sales using Z-scores.
    Flags days where revenue is significantly higher or lower than the moving average.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    transactions = db.query(SalesTransaction).join(Product).join(Store).filter(
        Store.organization_id == org_id,
        SalesTransaction.sale_date >= start_date
    ).all()
    
    if len(transactions) < 7: # Need at least a week of data
        return []
        
    df = pd.DataFrame([{
        'date': t.sale_date.date(),
        'revenue': t.total_amount or 0.0,
        'quantity': t.quantity
    } for t in transactions])
    
    daily_revenue = df.groupby('date')['revenue'].sum().reset_index()
    daily_revenue['date'] = pd.to_datetime(daily_revenue['date'])
    
    # Needs a complete date range
    date_range = pd.date_range(start=daily_revenue['date'].min(), end=daily_revenue['date'].max())
    daily_revenue = daily_revenue.set_index('date').reindex(date_range, fill_value=0).reset_index()
    daily_revenue.columns = ['date', 'revenue']
    
    if len(daily_revenue) < 14: # Wait for more history to do reliable stats
        return []
        
    # Calculate 7-day rolling mean and std dev
    rolling_mean = daily_revenue['revenue'].rolling(window=7, min_periods=1).mean()
    rolling_std = daily_revenue['revenue'].rolling(window=7, min_periods=1).std()
    
    # Calculate Z-score
    # Avoid division by zero
    rolling_std = rolling_std.replace(0, 1) 
    daily_revenue['z_score'] = (daily_revenue['revenue'] - rolling_mean) / rolling_std
    
    # Anomaly threshold: Z-score > 2 (significant spike) or < -2 (significant drop)
    daily_revenue['rolling_mean'] = rolling_mean
    
    anomalies = daily_revenue[
        ((daily_revenue['z_score'] > 2.0) | (daily_revenue['z_score'] < -2.0)) &
        ~((daily_revenue['revenue'] == 0) & (daily_revenue['rolling_mean'] < 50))
    ].copy()
    
    results = []
    for idx, row in anomalies.iterrows():
        is_spike = row['z_score'] > 0
        expected = row['rolling_mean']
        
        results.append({
            "date": row['date'].strftime('%Y-%m-%d'),
            "actual_revenue": round(row['revenue'], 2),
            "expected_revenue": round(expected, 2),
            "type": "spike" if is_spike else "drop",
            "z_score": round(row['z_score'], 2),
            "severity": "high" if abs(row['z_score']) > 3 else "medium"
        })
        
    # Sort newest first
    results.sort(key=lambda x: x['date'], reverse=True)
    return results
