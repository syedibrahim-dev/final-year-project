#!/usr/bin/env python3
"""
Schema Migration: Customer Analytics
=====================================

Drops the legacy `sales_transactions` table (and any existing `customers`
table from a failed prior attempt), then runs `init_db()` to recreate them
with the new schema that adds:

  - SalesTransaction.customer_id   (FK → customers)
  - SalesTransaction.invoice_no    (order grouping)
  - new Customer table

IMPORTANT:
  - This DELETES all existing rows in `sales_transactions`.
  - Other tables (users, organizations, products, stores, roleplay, mcq,
    marketing, etc.) are left UNTOUCHED.
  - Run once, before the first Online Retail II ingestion.

Usage:
  python scripts/migrate_customer_schema.py
  python scripts/migrate_customer_schema.py --yes   # skip confirmation
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path

# Project root on sys.path so `from models...` works when run as script
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect  # noqa: E402

from utils.database import engine, init_db  # noqa: E402
import models  # noqa: F401,E402  -- ensure all SQLAlchemy models are registered


def main():
    parser = argparse.ArgumentParser(
        description="Migrate schema to add customer_id / invoice_no / customers",
    )
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    print("=" * 60)
    print("  CUSTOMER ANALYTICS SCHEMA MIGRATION")
    print("=" * 60)
    print()

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    sales_exists = "sales_transactions" in existing_tables
    customers_exists = "customers" in existing_tables

    print("Current state:")
    print(f"  sales_transactions table: {'EXISTS' if sales_exists else 'not found'}")
    print(f"  customers table:          {'EXISTS' if customers_exists else 'not found'}")
    print()

    # Count existing rows if the table is there
    existing_txn_count = 0
    if sales_exists:
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM sales_transactions"))
                existing_txn_count = result.scalar() or 0
            print(f"  Existing sales_transactions rows: {existing_txn_count:,}")
            print()
        except Exception as e:
            print(f"  (could not count existing rows: {e})")
            print()

    print("This migration will:")
    if sales_exists:
        print(f"  1. DROP sales_transactions  (LOSES {existing_txn_count:,} rows)")
    if customers_exists:
        print("  2. DROP customers")
    print("  3. Run init_db() -> recreates with new schema (customer_id + invoice_no fields)")
    print()
    print("Other tables (users, organizations, products, stores, roleplay,")
    print("mcq, marketing, etc.) are UNTOUCHED.")
    print()

    if not args.yes:
        confirm = input("Type 'yes' to proceed: ").strip().lower()
        if confirm != "yes":
            print("Aborted.")
            sys.exit(0)

    print("\nExecuting migration...")
    try:
        with engine.begin() as conn:
            # Disable FK checks so the drop order doesn't matter
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

            if sales_exists:
                conn.execute(text("DROP TABLE IF EXISTS sales_transactions"))
                print("  [x] Dropped sales_transactions")

            if customers_exists:
                conn.execute(text("DROP TABLE IF EXISTS customers"))
                print("  [x] Dropped customers")

            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    except Exception as e:
        print(f"\n  Migration failed during DROP: {e}")
        sys.exit(1)

    print()
    print("Recreating tables from current models...")
    try:
        init_db()
        print("  [ok] init_db() complete")
    except Exception as e:
        print(f"\n  init_db() failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Verify
    inspector2 = inspect(engine)
    tables_now = set(inspector2.get_table_names())
    customers_ok = "customers" in tables_now
    sales_ok = "sales_transactions" in tables_now

    print()
    print("Verification:")
    print(f"  customers table:          {'OK' if customers_ok else 'MISSING'}")
    print(f"  sales_transactions table: {'OK' if sales_ok else 'MISSING'}")

    if sales_ok:
        # Check that new columns exist
        cols = {c["name"] for c in inspector2.get_columns("sales_transactions")}
        has_customer_id = "customer_id" in cols
        has_invoice_no = "invoice_no" in cols
        print(f"  sales_transactions.customer_id: {'OK' if has_customer_id else 'MISSING'}")
        print(f"  sales_transactions.invoice_no:  {'OK' if has_invoice_no else 'MISSING'}")

    print()
    print("=" * 60)
    print("  MIGRATION COMPLETE")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Install the new dep:   pip install lifetimes==0.11.3")
    print("  2. Download + ingest:     python scripts/ingest_online_retail_ii.py --download --org-id 1")
    print("  3. Verify analytics:      python scripts/verify_customer_analytics.py --org-id 1")
    print()


if __name__ == "__main__":
    main()
