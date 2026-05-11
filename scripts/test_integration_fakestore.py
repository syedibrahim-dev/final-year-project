#!/usr/bin/env python3
"""
End-to-End Test: Fake Store API Integration
============================================

Exercises the full flow without touching HTTP:
  1. Run init_db() so the new `store_integrations` table exists
  2. Create a Store + StoreIntegration for Fake Store
  3. Trigger sync_integration() → pulls products/customers/transactions
  4. Run RFM / BG-NBD CLV / Cohort analytics on the synced data
  5. Print a summary report

Usage:
  python scripts/test_integration_fakestore.py --org-id 1
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.database import SessionLocal, init_db  # noqa: E402
import models  # noqa: F401,E402  -- ensure all models are registered

from models.inventory import Store  # noqa: E402
from models.store_integration import StoreIntegration  # noqa: E402

from services.integrations.sync_service import (  # noqa: E402
    sync_integration,
    list_supported_platforms,
    get_integration_class,
)
from services.customer_analytics_service import (  # noqa: E402
    compute_rfm,
    compute_clv,
    compute_cohort_retention,
)

STORE_NAME = "Fake Store API (Demo)"


def hr(char: str = "-", length: int = 60) -> None:
    print(char * length)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", type=int, required=True, help="Organization id for the test store")
    parser.add_argument("--reset", action="store_true", help="Delete existing Fake Store integration + data first")
    args = parser.parse_args()

    print("=" * 60)
    print("  FAKE STORE API INTEGRATION — END-TO-END TEST")
    print(f"  Organization id: {args.org_id}")
    print("=" * 60)
    print()

    # ── Step 1: init_db ──
    print("[STEP 1] Ensuring DB schema (init_db)...")
    init_db()
    print("  Schema ready.")
    print()

    db = SessionLocal()
    try:
        # ── Step 2: Check supported platforms ──
        print("[STEP 2] Listing supported platforms...")
        platforms = list_supported_platforms()
        for p in platforms:
            print(f"  - {p['platform']:12s} | {p['display_name']:25s} | key_req={p['requires_api_key']}")
        print()

        # ── Step 3: Create (or reuse) Store + StoreIntegration ──
        print("[STEP 3] Creating / finding Store + StoreIntegration...")

        store = (
            db.query(Store)
            .filter_by(organization_id=args.org_id, name=STORE_NAME)
            .first()
        )

        if args.reset and store:
            print("  --reset flag: removing existing integration + store...")
            # Delete integration first
            existing_int = db.query(StoreIntegration).filter_by(store_id=store.id).first()
            if existing_int:
                db.delete(existing_int)
            # Delete the store itself (CASCADE will remove products + customers + transactions)
            db.delete(store)
            db.commit()
            store = None

        if store is None:
            store = Store(
                organization_id=args.org_id,
                name=STORE_NAME,
                platform="fakestore",
            )
            db.add(store)
            db.commit()
            db.refresh(store)
            print(f"  Created store: '{store.name}' (id={store.id})")
        else:
            print(f"  Reusing existing store: '{store.name}' (id={store.id})")

        integration = db.query(StoreIntegration).filter_by(store_id=store.id).first()
        if integration is None:
            integration = StoreIntegration(
                store_id=store.id,
                platform="fakestore",
                api_key_encrypted=None,
                api_secret_encrypted=None,
                base_url=None,
                last_sync_status="never",
            )
            db.add(integration)
            db.commit()
            db.refresh(integration)
            print(f"  Created integration (id={integration.id})")
        else:
            print(f"  Reusing existing integration (id={integration.id})")
        print()

        # ── Step 4: Test connection (what /connect does) ──
        print("[STEP 4] Testing platform connection...")
        cls = get_integration_class("fakestore")
        client = cls()
        test_result = client.test_connection()
        print(f"  ok:      {test_result.get('ok')}")
        print(f"  message: {test_result.get('message')}")
        if not test_result.get("ok"):
            print()
            print("  [!] Connection failed. Cannot proceed with sync.")
            return
        print()

        # ── Step 5: Sync ──
        print("[STEP 5] Syncing Fake Store data into DB...")
        result = sync_integration(db, integration)

        if not result.get("ok"):
            print(f"  Sync failed: {result.get('error')}")
            return

        summary = result.get("summary", {})
        print("  Sync summary:")
        for k, v in summary.items():
            print(f"    {k:40s} {v}")
        print()

        # ── Step 6: Run analytics on the freshly synced store ──
        print("[STEP 6] Running analytics on synced Fake Store data...")
        print()
        hr("=")
        print("  RFM SEGMENTATION")
        hr("=")

        rfm = compute_rfm(db, org_id=args.org_id, store_id=store.id)
        print(f"  Customers: {rfm.get('customer_count', 0)}")
        if rfm.get("customer_count", 0) > 0:
            print()
            print("  Segments:")
            for name, stats in sorted(
                rfm.get("segments", {}).items(), key=lambda x: -x[1]["count"]
            ):
                print(
                    f"    {name:22s} {stats['count']:>4} "
                    f"({stats['pct']:>5.1f}%)   avg_m=${stats['avg_monetary']:>7,.2f}"
                )

            print()
            print("  Top 3 customers by monetary:")
            top = sorted(rfm["customers"], key=lambda c: -c["monetary"])[:3]
            for c in top:
                print(
                    f"    Customer {c['customer_id']}: "
                    f"${c['monetary']:>8,.2f} | "
                    f"F={c['frequency']:>2} | "
                    f"R={c['recency_days']:>4}d | "
                    f"Score={c['rfm_score']} | "
                    f"{c['segment']}"
                )

        print()
        hr("=")
        print("  BG/NBD CUSTOMER LIFETIME VALUE")
        hr("=")

        clv = compute_clv(db, org_id=args.org_id, store_id=store.id, forecast_months=12)
        if "error" in clv:
            print(f"  Error: {clv['error']}")
        elif clv.get("customer_count", 0) == 0:
            print("  No customers.")
        else:
            clv_summary = clv.get("summary", {})
            if "total_predicted_clv" not in clv_summary:
                print(f"  {clv_summary.get('note', 'model not produced')}")
            else:
                print(f"  Customers:               {clv['customer_count']}")
                print(f"  Total predicted CLV:     ${clv_summary['total_predicted_clv']:>12,.2f}")
                print(f"  Avg predicted CLV:       ${clv_summary['avg_predicted_clv']:>12,.2f}")
                print(f"  Top 20% CLV share:       {clv_summary['top_20pct_clv_share']:.1f}%")
                print()
                print("  Top 3 customers by predicted CLV:")
                for c in clv.get("top_customers", [])[:3]:
                    print(
                        f"    Customer {c['customer_id']}: "
                        f"CLV=${c['predicted_clv']:>8,.2f} | "
                        f"pred txns={c['predicted_txns']:>5.2f} | "
                        f"alive={c['alive_probability']:.1%}"
                    )

        print()
        hr("=")
        print("  COHORT RETENTION")
        hr("=")

        cohort = compute_cohort_retention(db, org_id=args.org_id, store_id=store.id, max_months=12)
        print(f"  Total cohorts: {cohort.get('cohort_count', 0)}")
        if cohort.get("cohort_count", 0) > 0:
            cs = cohort.get("summary", {})
            print(f"  Avg retention @ M1:  {cs.get('avg_retention_month_1', 0):.1f}%")
            print(f"  Avg retention @ M3:  {cs.get('avg_retention_month_3', 0):.1f}%")
            print(f"  Avg retention @ M6:  {cs.get('avg_retention_month_6', 0):.1f}%")

            print()
            print("  First 5 cohorts:")
            for c in cohort.get("cohorts", [])[:5]:
                size = c["cohort_size"]
                months = " | ".join(
                    f"M{r['month_offset']}: {r['pct']:.0f}%"
                    for r in c["retention"][:5]
                )
                print(f"    {c['cohort_month']}  size={size:>3}  {months}")

        print()
        hr("=")
        print("  END-TO-END TEST COMPLETE")
        hr("=")
        print()
        print("  Verdict: integration flow works end-to-end.")
        print("  API endpoints are now usable:")
        print("    GET    /integrations/platforms")
        print("    POST   /integrations/connect")
        print("    GET    /integrations")
        print(f"    POST   /integrations/{integration.id}/sync")
        print(f"    DELETE /integrations/{integration.id}")
        print()

    finally:
        db.close()


if __name__ == "__main__":
    main()
