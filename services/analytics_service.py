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
    Detect statistical anomalies in daily sales using day-of-week aware Z-scores.

    The naive approach (straight 7-day rolling) flags every weekend dip as a
    "drop" because Sat/Sun are systematically lower than weekdays. This version
    compares each day against the EWM mean *of the same weekday* — Mondays vs
    Mondays, Saturdays vs Saturdays — so seasonal weekly patterns don't trip
    the detector.

    Algorithm:
      1. Build a complete daily revenue series (fill gaps with 0)
      2. Group by weekday (Mon=0..Sun=6)
      3. For each weekday: compute exponentially weighted mean and std of past
         observations of THAT weekday only (4-period span ≈ last 4 weeks)
      4. Z-score: (revenue - dow_ewm_mean) / dow_ewm_std
      5. Flag |Z| > 1.8 (slightly tighter than the naive 2.0 threshold because
         the dow-aware baseline is sharper — fewer false positives so we can
         lower the bar)
      6. Filter zero-revenue days where dow baseline is also near-zero
         (handles permanently-closed days)
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    transactions = db.query(SalesTransaction).join(Product).join(Store).filter(
        Store.organization_id == org_id,
        SalesTransaction.sale_date >= start_date
    ).all()

    if len(transactions) < 7:
        return []

    df = pd.DataFrame([{
        'date': t.sale_date.date(),
        'revenue': t.total_amount or 0.0,
        'quantity': t.quantity
    } for t in transactions])

    daily_revenue = df.groupby('date')['revenue'].sum().reset_index()
    daily_revenue['date'] = pd.to_datetime(daily_revenue['date'])

    # Complete date range with zero-fill
    date_range = pd.date_range(start=daily_revenue['date'].min(), end=daily_revenue['date'].max())
    daily_revenue = daily_revenue.set_index('date').reindex(date_range, fill_value=0).reset_index()
    daily_revenue.columns = ['date', 'revenue']

    if len(daily_revenue) < 14:
        return []

    # ── Day-of-week aware baseline ──────────────────────────────────────────
    daily_revenue['dow'] = daily_revenue['date'].dt.dayofweek  # 0=Mon, 6=Sun

    # For each weekday group, compute EWM mean and std using only past
    # observations of that same weekday. span=4 ≈ "last 4 weeks of Mondays".
    # Use shift(1) so the current day isn't included in its own baseline.
    def _per_dow_ewm(group, span=4):
        shifted = group.shift(1)  # exclude current observation from baseline
        return pd.DataFrame({
            'dow_mean': shifted.ewm(span=span, adjust=False, min_periods=1).mean(),
            'dow_std':  shifted.ewm(span=span, adjust=False, min_periods=2).std(),
        })

    grouped = daily_revenue.groupby('dow')['revenue']
    dow_stats_list = []
    for dow_value, group in grouped:
        stats = _per_dow_ewm(group)
        stats.index = group.index
        dow_stats_list.append(stats)
    dow_stats = pd.concat(dow_stats_list).sort_index()

    daily_revenue['dow_mean'] = dow_stats['dow_mean']
    daily_revenue['dow_std']  = dow_stats['dow_std']

    # First few weeks lack baseline — drop those rows from consideration
    daily_revenue = daily_revenue.dropna(subset=['dow_mean'])

    # Proportional std floor: max($5, 15% of dow_mean). This prevents tiny
    # variance windows from generating huge z-scores on small absolute swings.
    # E.g. a Sat with mean=$30 gets floor=$5 (not $1), so a $90 day yields
    # z = (90-30)/max(actual_std, 5) ≈ 12 — still flagged, but proportional.
    proportional_floor = (daily_revenue['dow_mean'].abs() * 0.15).clip(lower=5.0)
    daily_revenue['dow_std'] = daily_revenue['dow_std'].fillna(0)
    daily_revenue['dow_std'] = daily_revenue[['dow_std']].max(axis=1).combine(proportional_floor, max)

    daily_revenue['z_score'] = (daily_revenue['revenue'] - daily_revenue['dow_mean']) / daily_revenue['dow_std']

    # Threshold tightened from 2.0 → 1.8 because the dow-aware baseline is
    # sharper (less seasonal noise → fewer false positives → can lower bar)
    Z_THRESHOLD = 1.8

    anomalies = daily_revenue[
        ((daily_revenue['z_score'] > Z_THRESHOLD) | (daily_revenue['z_score'] < -Z_THRESHOLD))
        # Filter days where this weekday is normally zero (permanently closed)
        & ~((daily_revenue['revenue'] == 0) & (daily_revenue['dow_mean'] < 50))
    ].copy()

    DOW_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    results = []
    for idx, row in anomalies.iterrows():
        is_spike = row['z_score'] > 0
        results.append({
            "date":              row['date'].strftime('%Y-%m-%d'),
            "weekday":           DOW_NAMES[int(row['dow'])],
            "actual_revenue":    round(row['revenue'], 2),
            "expected_revenue":  round(row['dow_mean'], 2),  # this weekday's typical level
            "type":              "spike" if is_spike else "drop",
            "z_score":           round(row['z_score'], 2),
            "severity":          "high" if abs(row['z_score']) > 3 else "medium",
        })

    results.sort(key=lambda x: x['date'], reverse=True)
    return results
