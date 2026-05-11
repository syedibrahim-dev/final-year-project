"""
Customer Analytics Service
===========================

Research-backed customer intelligence on top of SalesTransaction / Customer
data. Implements:

  1. RFM segmentation (Recency, Frequency, Monetary) with quintile scoring
     and standard segment labels (Champions, Loyal, At-Risk, etc.).
     Reference: Hughes (1994) "Strategic Database Marketing".

  2. BG/NBD Customer Lifetime Value using the `lifetimes` library.
     Reference: Fader, Hardie & Lee (2005) "RFM and CLV: Using Iso-value
     Curves for Customer Base Analysis". Journal of Marketing Research.

  3. Monthly cohort retention analysis.
     Reference: standard SaaS/ecommerce technique (Silverstein, Skok).

All functions take a SQLAlchemy Session + org_id so they can be reused
from routes or scripts.
"""
from __future__ import annotations

import logging
import os
import warnings
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy.orm import Session

# Silence scipy's verbose optimizer output when BG/NBD or Gamma-Gamma retries
# on smaller samples. These warnings are informational — we already handle
# convergence failures via the retry/fallback ladder.
warnings.filterwarnings("ignore", category=RuntimeWarning, module="lifetimes")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

from models.inventory import Store, Product, Customer, SalesTransaction

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  DATA LOADING HELPER
# ══════════════════════════════════════════════════════════════════

def _load_transactions_df(
    db: Session,
    org_id: int,
    store_id: Optional[int] = None,
) -> pd.DataFrame:
    """
    Pull all transactions for an org (optionally scoped to one store) into
    a pandas DataFrame with columns: customer_id, sale_date, total_amount,
    quantity, product_id, invoice_no.

    Returns an empty DataFrame if no data is found.
    """
    query = (
        db.query(
            SalesTransaction.customer_id,
            SalesTransaction.sale_date,
            SalesTransaction.total_amount,
            SalesTransaction.quantity,
            SalesTransaction.product_id,
            SalesTransaction.invoice_no,
        )
        .join(Product, Product.id == SalesTransaction.product_id)
        .join(Store, Store.id == Product.store_id)
        .filter(Store.organization_id == org_id)
        .filter(SalesTransaction.customer_id.isnot(None))
    )

    if store_id is not None:
        query = query.filter(Product.store_id == store_id)

    rows = query.all()
    if not rows:
        return pd.DataFrame(
            columns=["customer_id", "sale_date", "total_amount", "quantity", "product_id", "invoice_no"]
        )

    df = pd.DataFrame([
        {
            "customer_id":  r.customer_id,
            "sale_date":    r.sale_date,
            "total_amount": float(r.total_amount or 0.0),
            "quantity":     int(r.quantity or 0),
            "product_id":   r.product_id,
            "invoice_no":   r.invoice_no,
        }
        for r in rows
    ])
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    return df


# ══════════════════════════════════════════════════════════════════
#  RFM SEGMENTATION
# ══════════════════════════════════════════════════════════════════

def _rfm_segment_label(r: int, f: int, m: int) -> str:
    """
    Map (R, F, M) quintile scores to a segment label.
    Standard rfm-analysis segmentation (based on Hughes 1994).

    Each score is 1-5 (5 = best).
    """
    score = f"{r}{f}{m}"
    # Simplified segmentation — focus on 8 clear actionable buckets
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 4:
        return "Loyal Customers"
    if r >= 4 and f <= 2:
        return "New Customers"
    if r >= 3 and f >= 2 and m >= 3:
        return "Potential Loyalists"
    if r <= 2 and f >= 4 and m >= 4:
        return "Can't Lose Them"
    if r <= 2 and f >= 3:
        return "At Risk"
    if r <= 2 and f <= 2 and m >= 3:
        return "Hibernating"
    return "Lost"


def compute_rfm(
    db: Session,
    org_id: int,
    store_id: Optional[int] = None,
    snapshot_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Compute RFM scores + segment labels for all customers in the given org.

    Returns:
        {
            "snapshot_date":  ISO date string,
            "customer_count": int,
            "segments": {
                "Champions":          {"count": N, "avg_monetary": $, "pct": %},
                ...
            },
            "customers": [
                {
                    "customer_id":  int,
                    "recency_days": int,
                    "frequency":    int,
                    "monetary":     float,
                    "r_score": 1-5, "f_score": 1-5, "m_score": 1-5,
                    "rfm_score":   str (e.g. "555"),
                    "segment":      str,
                },
                ...
            ]
        }
    """
    df = _load_transactions_df(db, org_id, store_id)
    if df.empty:
        return {
            "snapshot_date": None,
            "customer_count": 0,
            "segments": {},
            "customers": [],
        }

    # Snapshot date = day after the last observed transaction
    if snapshot_date is None:
        snapshot_date = (df["sale_date"].max() + timedelta(days=1)).to_pydatetime()

    # Aggregate per customer
    grouped = df.groupby("customer_id").agg(
        last_purchase=("sale_date", "max"),
        frequency=("invoice_no", lambda s: s.nunique() if s.notna().any() else len(s)),
        monetary=("total_amount", "sum"),
    ).reset_index()

    # Recency = days since last purchase (relative to snapshot_date)
    grouped["recency_days"] = (pd.Timestamp(snapshot_date) - grouped["last_purchase"]).dt.days
    grouped["monetary"] = grouped["monetary"].round(2)

    # ── Quintile scoring ──
    # R: lower days = better (score 5)  → quantile-based rank, inverted
    # F: higher freq = better (score 5)
    # M: higher monetary = better (score 5)
    try:
        grouped["r_score"] = pd.qcut(
            grouped["recency_days"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]
        ).astype(int)
    except ValueError:
        grouped["r_score"] = 3  # not enough variation, default middle

    try:
        grouped["f_score"] = pd.qcut(
            grouped["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]
        ).astype(int)
    except ValueError:
        grouped["f_score"] = 3

    try:
        grouped["m_score"] = pd.qcut(
            grouped["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]
        ).astype(int)
    except ValueError:
        grouped["m_score"] = 3

    grouped["rfm_score"] = (
        grouped["r_score"].astype(str) +
        grouped["f_score"].astype(str) +
        grouped["m_score"].astype(str)
    )
    grouped["segment"] = grouped.apply(
        lambda row: _rfm_segment_label(row["r_score"], row["f_score"], row["m_score"]),
        axis=1,
    )

    # ── Build segment summary ──
    seg_summary = grouped.groupby("segment").agg(
        count=("customer_id", "count"),
        avg_monetary=("monetary", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_recency=("recency_days", "mean"),
    ).reset_index()

    total = len(grouped)
    segments: Dict[str, Dict[str, Any]] = {}
    for _, row in seg_summary.iterrows():
        segments[row["segment"]] = {
            "count":        int(row["count"]),
            "pct":          round((row["count"] / total) * 100, 1),
            "avg_monetary": round(float(row["avg_monetary"]), 2),
            "avg_frequency": round(float(row["avg_frequency"]), 1),
            "avg_recency_days": round(float(row["avg_recency"]), 1),
        }

    # ── Flatten customer list ──
    customers = grouped[[
        "customer_id", "recency_days", "frequency", "monetary",
        "r_score", "f_score", "m_score", "rfm_score", "segment",
    ]].to_dict("records")

    # Cast numpy types to native Python for JSON serialization
    for c in customers:
        c["customer_id"] = int(c["customer_id"])
        c["recency_days"] = int(c["recency_days"])
        c["frequency"] = int(c["frequency"])
        c["monetary"] = float(c["monetary"])
        c["r_score"] = int(c["r_score"])
        c["f_score"] = int(c["f_score"])
        c["m_score"] = int(c["m_score"])

    return {
        "snapshot_date": snapshot_date.isoformat() if snapshot_date else None,
        "customer_count": total,
        "segments": segments,
        "customers": customers,
    }


# ══════════════════════════════════════════════════════════════════
#  BG/NBD CLV (Fader, Hardie & Lee 2005)
# ══════════════════════════════════════════════════════════════════

def compute_clv(
    db: Session,
    org_id: int,
    store_id: Optional[int] = None,
    forecast_months: int = 12,
    discount_rate: float = 0.01,
) -> Dict[str, Any]:
    """
    BG/NBD + Gamma-Gamma customer lifetime value prediction.

    Uses the `lifetimes` library's BetaGeoFitter (Fader, Hardie & Lee 2005)
    for expected transaction count, and GammaGammaFitter for expected
    monetary value per transaction.

    Args:
        forecast_months: prediction horizon in months (default 12)
        discount_rate:   monthly discount for NPV (default 1%)

    Returns:
        {
            "forecast_months": int,
            "customer_count":  int,
            "summary": {
                "total_predicted_clv": $,
                "avg_predicted_clv":   $,
                "top_20pct_clv_share": %,    # Pareto check
            },
            "top_customers": [
                {
                    "customer_id":                   int,
                    "frequency":                     int (purchases - 1),
                    "recency":                       float (days between first and last),
                    "T":                             float (days since first purchase),
                    "monetary_value":                float,
                    "predicted_txns":                float,
                    "predicted_avg_order_value":     float,
                    "predicted_clv":                 float,
                    "alive_probability":             float,
                },
                ...   (top 20 by predicted CLV)
            ]
        }

    Returns empty summary if lifetimes isn't installed or data is insufficient.
    """
    # Lazy import so the service file remains importable even if `lifetimes`
    # isn't yet installed. The /analytics/clv route will return a helpful
    # error message instead of crashing import.
    try:
        from lifetimes import BetaGeoFitter, GammaGammaFitter
        from lifetimes.utils import summary_data_from_transaction_data
    except ImportError as e:
        logger.warning(f"lifetimes not installed — CLV unavailable ({e})")
        return {
            "error": "lifetimes library not installed. Run: pip install lifetimes==0.11.3",
            "forecast_months": forecast_months,
            "customer_count": 0,
            "summary": {},
            "top_customers": [],
        }

    df = _load_transactions_df(db, org_id, store_id)
    if df.empty or df["customer_id"].nunique() < 10:
        return {
            "forecast_months": forecast_months,
            "customer_count": int(df["customer_id"].nunique()) if not df.empty else 0,
            "summary": {"note": "Insufficient data (need at least 10 customers)"},
            "top_customers": [],
        }

    # lifetimes needs: customer_id, datetime column, monetary_value column
    # Build a per-customer summary (frequency, recency, T, monetary_value)
    df_input = df.rename(columns={"sale_date": "date"})
    summary = summary_data_from_transaction_data(
        df_input,
        customer_id_col="customer_id",
        datetime_col="date",
        monetary_value_col="total_amount",
        observation_period_end=df_input["date"].max(),
        freq="D",
    )

    # summary.columns: frequency, recency, T, monetary_value
    if len(summary) < 10:
        return {
            "forecast_months": forecast_months,
            "customer_count": len(summary),
            "summary": {"note": "Insufficient customer history for CLV model"},
            "top_customers": [],
        }

    # ── Fit BG/NBD (purchase count model) ──
    try:
        bgf = BetaGeoFitter(penalizer_coef=0.001)
        bgf.fit(summary["frequency"], summary["recency"], summary["T"])
    except Exception as e:
        logger.error(f"BG/NBD fit failed: {e}")
        return {
            "error": f"BG/NBD fit failed: {e}",
            "forecast_months": forecast_months,
            "customer_count": len(summary),
            "summary": {},
            "top_customers": [],
        }

    # Days to predict: months * ~30
    prediction_days = forecast_months * 30
    summary["predicted_txns"] = bgf.conditional_expected_number_of_purchases_up_to_time(
        prediction_days,
        summary["frequency"],
        summary["recency"],
        summary["T"],
    )
    summary["alive_probability"] = bgf.conditional_probability_alive(
        summary["frequency"],
        summary["recency"],
        summary["T"],
    )

    # ── Fit Gamma-Gamma (monetary value model) ──
    # Requires frequency > 0 (only returning customers).
    # On smaller samples the default penalizer_coef=0.001 sometimes fails
    # to converge — retry with progressively stronger regularization.
    returning = summary[summary["frequency"] > 0].copy()
    gg_fitted = False

    if len(returning) >= 10:
        for penalizer in (0.001, 0.01, 0.1, 1.0):
            try:
                # Suppress scipy's verbose OptimizeWarning output during fit attempts
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    ggf = GammaGammaFitter(penalizer_coef=penalizer)
                    ggf.fit(returning["frequency"], returning["monetary_value"])

                summary["predicted_avg_order_value"] = ggf.conditional_expected_average_profit(
                    summary["frequency"],
                    summary["monetary_value"],
                )
                summary["predicted_clv"] = ggf.customer_lifetime_value(
                    bgf,
                    summary["frequency"],
                    summary["recency"],
                    summary["T"],
                    summary["monetary_value"],
                    time=forecast_months,
                    discount_rate=discount_rate,
                    freq="D",
                )
                gg_fitted = True
                if penalizer > 0.001:
                    logger.info(f"Gamma-Gamma converged with penalizer_coef={penalizer}")
                break
            except Exception as e:
                logger.warning(
                    f"Gamma-Gamma fit failed at penalizer_coef={penalizer}: {e}"
                )
                continue

    if not gg_fitted:
        # Heuristic fallback: CLV ≈ predicted_txns × observed_avg_monetary
        # discounted to present value. Not as rigorous as Gamma-Gamma but
        # produces sensible numbers for the demo / small-sample case.
        logger.warning("Gamma-Gamma could not converge — using heuristic CLV fallback")
        summary["predicted_avg_order_value"] = summary["monetary_value"]
        # Discount factor over forecast horizon (monthly compounding)
        discount_factor = (1.0 - (1.0 + discount_rate) ** (-forecast_months)) / discount_rate if discount_rate > 0 else forecast_months
        # Roughly: "expected spend over period / 12 months" × discount factor
        monthly_rate = summary["predicted_txns"] / max(forecast_months, 1) * summary["monetary_value"]
        summary["predicted_clv"] = monthly_rate * discount_factor

    # Clean up any NaN / inf values
    summary = summary.fillna(0).replace([float("inf"), float("-inf")], 0)

    # ── Aggregate summary stats ──
    total_clv = float(summary["predicted_clv"].sum())
    avg_clv = float(summary["predicted_clv"].mean())
    sorted_clv = summary["predicted_clv"].sort_values(ascending=False)
    top_20_count = max(1, int(len(sorted_clv) * 0.2))
    top_20_clv = float(sorted_clv.head(top_20_count).sum())
    top_20_share = (top_20_clv / total_clv * 100) if total_clv > 0 else 0.0

    # ── Top 20 customers by CLV ──
    top_customers_df = summary.sort_values("predicted_clv", ascending=False).head(20)
    top_customers: List[Dict[str, Any]] = []
    for customer_id, row in top_customers_df.iterrows():
        top_customers.append({
            "customer_id":               int(customer_id),
            "frequency":                 int(row["frequency"]),
            "recency":                   round(float(row["recency"]), 1),
            "T":                         round(float(row["T"]), 1),
            "monetary_value":            round(float(row["monetary_value"]), 2),
            "predicted_txns":            round(float(row["predicted_txns"]), 2),
            "predicted_avg_order_value": round(float(row["predicted_avg_order_value"]), 2),
            "predicted_clv":             round(float(row["predicted_clv"]), 2),
            "alive_probability":         round(float(row["alive_probability"]), 3),
        })

    return {
        "forecast_months": forecast_months,
        "customer_count":  int(len(summary)),
        "summary": {
            "total_predicted_clv":  round(total_clv, 2),
            "avg_predicted_clv":    round(avg_clv, 2),
            "top_20pct_clv_share":  round(top_20_share, 1),
            "model": "BG/NBD + Gamma-Gamma (Fader, Hardie & Lee 2005)",
        },
        "top_customers": top_customers,
    }


# ══════════════════════════════════════════════════════════════════
#  COHORT RETENTION
# ══════════════════════════════════════════════════════════════════

def compute_cohort_retention(
    db: Session,
    org_id: int,
    store_id: Optional[int] = None,
    max_months: int = 12,
) -> Dict[str, Any]:
    """
    Monthly cohort retention analysis.

    Groups customers by their first-purchase month, then tracks what
    percentage of each cohort purchased again in subsequent months.

    Args:
        max_months: how many months of retention to report per cohort

    Returns:
        {
            "cohort_count":  int,
            "max_months":    int,
            "cohorts": [
                {
                    "cohort_month": "2010-01",
                    "cohort_size":  234,
                    "retention": [
                        {"month_offset": 0, "active": 234, "pct": 100.0},
                        {"month_offset": 1, "active":  82, "pct":  35.0},
                        ...
                    ]
                },
                ...
            ],
            "summary": {
                "avg_retention_month_1": %,
                "avg_retention_month_3": %,
                "avg_retention_month_6": %,
            }
        }
    """
    df = _load_transactions_df(db, org_id, store_id)
    if df.empty:
        return {
            "cohort_count": 0,
            "max_months": max_months,
            "cohorts": [],
            "summary": {},
        }

    # Strip to date (remove time) at month granularity
    df["month"] = df["sale_date"].dt.to_period("M")

    # First purchase month per customer
    first_month = df.groupby("customer_id")["month"].min().rename("cohort_month")
    df = df.merge(first_month, on="customer_id")

    # Months since cohort start
    df["month_offset"] = (df["month"] - df["cohort_month"]).apply(lambda x: x.n)

    # Pivot: cohort_month × month_offset → unique customer count
    cohort_counts = df.groupby(["cohort_month", "month_offset"])["customer_id"].nunique().unstack(fill_value=0)

    # Cohort sizes (month_offset == 0)
    cohort_sizes = cohort_counts.iloc[:, 0]

    # Retention % = count / cohort_size * 100
    retention_pct = cohort_counts.divide(cohort_sizes, axis=0) * 100

    # Truncate to max_months
    retention_pct = retention_pct.iloc[:, :max_months + 1]
    cohort_counts = cohort_counts.iloc[:, :max_months + 1]

    # ── Build structured output ──
    cohorts: List[Dict[str, Any]] = []
    for cohort_month in retention_pct.index:
        row_data = []
        for offset in retention_pct.columns:
            active = int(cohort_counts.loc[cohort_month, offset])
            pct = float(retention_pct.loc[cohort_month, offset])
            row_data.append({
                "month_offset": int(offset),
                "active":       active,
                "pct":          round(pct, 1),
            })
        cohorts.append({
            "cohort_month": str(cohort_month),
            "cohort_size":  int(cohort_sizes.loc[cohort_month]),
            "retention":    row_data,
        })

    # ── Aggregate summary ──
    def _avg_at_offset(n: int) -> float:
        if n not in retention_pct.columns:
            return 0.0
        col = retention_pct[n]
        # Only count cohorts that have had at least n months to mature
        valid = col[col.index + n <= retention_pct.index.max()]
        return round(float(valid.mean()), 1) if len(valid) > 0 else 0.0

    summary = {
        "avg_retention_month_1": _avg_at_offset(1),
        "avg_retention_month_3": _avg_at_offset(3),
        "avg_retention_month_6": _avg_at_offset(6),
        "avg_retention_month_12": _avg_at_offset(12),
    }

    return {
        "cohort_count": len(cohorts),
        "max_months":   max_months,
        "cohorts":      cohorts,
        "summary":      summary,
    }
