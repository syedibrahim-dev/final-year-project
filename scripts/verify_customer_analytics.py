#!/usr/bin/env python3
"""
Customer Analytics Verification
================================

Calls the customer analytics service functions directly (no HTTP, no auth)
and prints a summary of each output. Lets you verify that ingestion worked
and the analytics pipeline produces meaningful results before wiring up
the frontend or hitting endpoints via curl.

Usage:
  python scripts/verify_customer_analytics.py --org-id 1
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.database import SessionLocal  # noqa: E402
from sqlalchemy import func  # noqa: E402

from models.inventory import Store, Product, SalesTransaction  # noqa: E402
from services.customer_analytics_service import (  # noqa: E402
    compute_rfm,
    compute_clv,
    compute_cohort_retention,
)


def _pick_biggest_store(db, org_id: int):
    """Return (store_id, name, txn_count) for the org's biggest store by txn count.
    Analytics always scope to one store — mixing stores with non-overlapping
    date ranges (e.g. OR-II 2009-2011 + FakeStore 2020) breaks BG/NBD because
    the snapshot_date anchors on the overall max, making older customers
    appear "dead" to the model.
    """
    rows = (
        db.query(
            Store.id,
            Store.name,
            func.count(SalesTransaction.id).label("c"),
        )
        .join(Product, Product.store_id == Store.id)
        .join(SalesTransaction, SalesTransaction.product_id == Product.id)
        .filter(Store.organization_id == org_id)
        .group_by(Store.id, Store.name)
        .order_by(func.count(SalesTransaction.id).desc())
        .all()
    )
    if not rows:
        return None
    return rows[0]


def hr(char: str = "-", length: int = 60) -> None:
    print(char * length)


# ══════════════════════════════════════════════════════════════════

def verify_rfm(db, org_id: int, store_id=None) -> bool:
    print()
    hr("=")
    print("  RFM SEGMENTATION  (Hughes 1994)")
    hr("=")

    result = compute_rfm(db, org_id=org_id, store_id=store_id)

    print(f"Snapshot date:   {result.get('snapshot_date', 'N/A')}")
    print(f"Total customers: {result.get('customer_count', 0):,}")

    if result.get("customer_count", 0) == 0:
        print("\n  [!] No customers found. Did you run the ingestion script?")
        return False

    segments = result.get("segments", {})
    if segments:
        print()
        print("Segments (sorted by count):")
        for name, stats in sorted(segments.items(), key=lambda x: -x[1]["count"]):
            count = stats["count"]
            pct = stats["pct"]
            avg_m = stats["avg_monetary"]
            avg_f = stats.get("avg_frequency", 0)
            bar_len = max(1, int(pct / 2))
            bar = "#" * bar_len
            print(
                f"  {name:20s} {count:>6,} ({pct:>5.1f}%)   "
                f"avg monetary=${avg_m:>8,.0f}  avg freq={avg_f:>5.1f}  {bar}"
            )

    # Top 3 customers by monetary
    customers = result.get("customers", [])
    top_3 = sorted(customers, key=lambda c: -c["monetary"])[:3]
    if top_3:
        print()
        print("Top 3 customers by monetary:")
        for c in top_3:
            print(
                f"  Customer {c['customer_id']}: "
                f"${c['monetary']:>10,.2f} | "
                f"F={c['frequency']:>3} | "
                f"R={c['recency_days']:>4}d | "
                f"Score={c['rfm_score']} | "
                f"{c['segment']}"
            )

    return True


# ══════════════════════════════════════════════════════════════════

def verify_clv(db, org_id: int, store_id=None) -> bool:
    print()
    hr("=")
    print("  BG/NBD CUSTOMER LIFETIME VALUE  (Fader, Hardie & Lee 2005)")
    hr("=")

    result = compute_clv(db, org_id=org_id, store_id=store_id, forecast_months=12)

    if "error" in result:
        print(f"\n  [!] {result['error']}")
        return False

    if result.get("customer_count", 0) == 0:
        print("\n  [!] No customers found.")
        return False

    summary = result.get("summary", {})
    if not summary or "total_predicted_clv" not in summary:
        print(f"\n  [!] {summary.get('note', 'No summary produced')}")
        return False

    print(f"Forecast horizon:      {result['forecast_months']} months")
    print(f"Total customers:       {result['customer_count']:,}")
    print(f"Total predicted CLV:   ${summary['total_predicted_clv']:>12,.2f}")
    print(f"Avg predicted CLV:     ${summary['avg_predicted_clv']:>12,.2f}")
    print(f"Top 20% CLV share:     {summary['top_20pct_clv_share']:>5.1f}%  (Pareto check)")
    print(f"Model:                 {summary.get('model', 'BG/NBD + Gamma-Gamma')}")

    top = result.get("top_customers", [])[:5]
    if top:
        print()
        print("Top 5 customers by predicted CLV:")
        for c in top:
            print(
                f"  Customer {c['customer_id']}: "
                f"CLV=${c['predicted_clv']:>8,.2f} | "
                f"pred txns={c['predicted_txns']:>5.2f} | "
                f"AOV=${c['predicted_avg_order_value']:>6.2f} | "
                f"alive={c['alive_probability']:.1%}"
            )

    return True


# ══════════════════════════════════════════════════════════════════

def verify_cohort(db, org_id: int, store_id=None) -> bool:
    print()
    hr("=")
    print("  COHORT RETENTION  (Silverstein / Skok)")
    hr("=")

    result = compute_cohort_retention(db, org_id=org_id, store_id=store_id, max_months=12)

    if result.get("cohort_count", 0) == 0:
        print("\n  [!] No cohorts found.")
        return False

    print(f"Total cohorts: {result['cohort_count']}")
    summary = result.get("summary", {})
    print(f"Avg retention @ month 1:  {summary.get('avg_retention_month_1', 0):>5.1f}%")
    print(f"Avg retention @ month 3:  {summary.get('avg_retention_month_3', 0):>5.1f}%")
    print(f"Avg retention @ month 6:  {summary.get('avg_retention_month_6', 0):>5.1f}%")
    print(f"Avg retention @ month 12: {summary.get('avg_retention_month_12', 0):>5.1f}%")

    # Print matrix preview (first 10 cohorts, first 7 months)
    cohorts = result.get("cohorts", [])
    if cohorts:
        print()
        print("Retention matrix (first 10 cohorts × first 7 months):")
        header = f"  {'Cohort':10s} {'Size':>6s}   "
        for offset in range(7):
            header += f"M{offset:<4d}  "
        print(header)
        print("  " + "-" * (len(header) - 2))

        for cohort in cohorts[:10]:
            row = f"  {cohort['cohort_month']:10s} {cohort['cohort_size']:>6,}   "
            for r in cohort["retention"][:7]:
                pct = r["pct"]
                row += f"{pct:>5.1f}% "
            print(row)

    return True


# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Verify customer analytics outputs for an organisation",
    )
    parser.add_argument(
        "--org-id", type=int, required=True,
        help="Organization id to verify",
    )
    parser.add_argument(
        "--store-id", type=int, default=None,
        help="Scope analytics to a specific store (defaults to biggest store by txn count). "
             "Use --store-id 0 to disable filter and run across all stores.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  CUSTOMER ANALYTICS VERIFICATION")
    print(f"  Organization ID: {args.org_id}")
    print("=" * 60)

    db = SessionLocal()
    try:
        # Resolve store_id
        if args.store_id == 0:
            store_id = None
            print("  Scope: ALL stores (aggregated — may produce mixed results)")
        elif args.store_id is None:
            # Default: pick biggest store (matches frontend behaviour)
            pick = _pick_biggest_store(db, args.org_id)
            if pick is None:
                print("  [!] No stores found for this org.")
                return
            store_id, store_name, txn_count = pick
            print(f"  Scope: store_id={store_id} '{store_name}' ({txn_count:,} transactions)")
            print("         (use --store-id 0 for org-wide, or --store-id N for specific)")
        else:
            store_id = args.store_id
            print(f"  Scope: store_id={store_id} (user-specified)")

        rfm_ok = verify_rfm(db, args.org_id, store_id=store_id)
        clv_ok = verify_clv(db, args.org_id, store_id=store_id)
        cohort_ok = verify_cohort(db, args.org_id, store_id=store_id)

        print()
        hr("=")
        print("  SUMMARY")
        hr("=")
        print(f"  RFM Segmentation:       {'OK' if rfm_ok else 'FAILED'}")
        print(f"  BG/NBD CLV:             {'OK' if clv_ok else 'FAILED'}")
        print(f"  Cohort Retention:       {'OK' if cohort_ok else 'FAILED'}")
        print()

        if rfm_ok and clv_ok and cohort_ok:
            print("  All 3 analytics produced meaningful output.")
            print("  API endpoints are ready: /analytics/rfm, /analytics/clv, /analytics/cohort-retention")
        else:
            print("  Some analytics failed or returned empty. Check the output above.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
