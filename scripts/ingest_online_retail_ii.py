#!/usr/bin/env python3
"""
Online Retail II Ingestion Script
==================================

Loads the UCI Online Retail II dataset (Chen, Sain & Guo 2012) into the
SalesForge database for downstream customer analytics (RFM + BG/NBD CLV,
cohort retention, etc.).

Dataset citation:
    Chen, D., Sain, S.L., & Guo, K. (2012). "Data mining for the online
    retail industry: A case study of RFM model-based customer segmentation
    using data mining." Journal of Database Marketing & Customer Strategy
    Management.

Download:
    https://archive.ics.uci.edu/ml/machine-learning-databases/00502/online_retail_II.xlsx

Usage:
    # Manual file + ingest into org 1
    python scripts/ingest_online_retail_ii.py --file data/online_retail_II.xlsx --org-id 1

    # Auto-download from UCI
    python scripts/ingest_online_retail_ii.py --download --org-id 1

    # Clear and re-ingest
    python scripts/ingest_online_retail_ii.py --download --org-id 1 --force

    # Sample for quick dev (first N rows after cleaning)
    python scripts/ingest_online_retail_ii.py --download --org-id 1 --sample 50000
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path

# Ensure project root on sys.path so `from models...` works when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd  # noqa: E402

from utils.database import SessionLocal, init_db  # noqa: E402
from models.inventory import (  # noqa: E402
    Store,
    Product,
    Customer,
    SalesTransaction,
)


UCI_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/00502/online_retail_II.xlsx"
DEFAULT_STORE_NAME = "Online Retail II (Demo)"
DEFAULT_SKU_PREFIX = "OR2_"
BATCH_SIZE = 5000


# ══════════════════════════════════════════════════════════════════
#  DOWNLOAD
# ══════════════════════════════════════════════════════════════════

def download_dataset(dest_path: Path) -> bool:
    """Download Online Retail II from UCI if not already present."""
    if dest_path.exists():
        size_mb = dest_path.stat().st_size / 1e6
        print(f"  Already exists: {dest_path} ({size_mb:.1f} MB)")
        return True

    print(f"  Downloading from UCI: {UCI_URL}")
    print(f"  Destination:          {dest_path}")

    try:
        import requests
        resp = requests.get(UCI_URL, stream=True, timeout=120)
        resp.raise_for_status()

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                written += len(chunk)
                if written % (1024 * 1024) < 65536:
                    print(f"    {written / 1e6:.1f} MB downloaded", end="\r")

        print(f"\n  Downloaded {written / 1e6:.1f} MB")
        return True
    except Exception as e:
        print(f"  Download failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
#  LOAD + CLEAN
# ══════════════════════════════════════════════════════════════════

def load_and_clean(
    file_path: Path,
    sample: int | None = None,
    sample_customers: int | None = None,
) -> pd.DataFrame:
    """Load xlsx, concatenate both sheets, filter to usable rows.

    Two sampling modes:
      - `sample`: first N rows chronologically (narrow time window, bad for cohorts)
      - `sample_customers`: pick N random customers, keep ALL their transactions
        (preserves full date range and each customer's full purchase history —
        critical for BG/NBD fit and cohort retention accuracy)
    """
    print(f"  Reading {file_path} (this may take 30-60 seconds)...")

    try:
        sheets = pd.read_excel(file_path, sheet_name=None)  # all sheets
    except Exception as e:
        print(f"  Failed to read xlsx: {e}")
        raise

    dfs = []
    for sheet_name, sheet_df in sheets.items():
        print(f"    Sheet '{sheet_name}': {len(sheet_df):,} rows")
        dfs.append(sheet_df)

    df = pd.concat(dfs, ignore_index=True)
    print(f"  Total raw rows: {len(df):,}")

    # Online Retail II ships with slightly different column names
    # than the original Online Retail; normalize.
    column_mapping = {
        "Invoice": "InvoiceNo",
        "Customer ID": "CustomerID",
        "Price": "UnitPrice",
    }
    df = df.rename(columns=column_mapping)

    required = [
        "InvoiceNo", "StockCode", "Description", "Quantity",
        "InvoiceDate", "UnitPrice", "CustomerID",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}. Got: {list(df.columns)}"
        )

    # ── Drop null CustomerID (guest checkouts — can't analyse) ──
    before = len(df)
    df = df.dropna(subset=["CustomerID"])
    print(f"  After dropping null CustomerID:   {len(df):>10,}  ({before - len(df):,} dropped)")

    # ── Drop cancellations (Invoice starting with 'C') ──
    before = len(df)
    df = df[~df["InvoiceNo"].astype(str).str.startswith("C")]
    print(f"  After dropping cancellations:     {len(df):>10,}  ({before - len(df):,} dropped)")

    # ── Drop non-positive quantity ──
    before = len(df)
    df = df[df["Quantity"] > 0]
    print(f"  After dropping Quantity<=0:       {len(df):>10,}  ({before - len(df):,} dropped)")

    # ── Drop non-positive price ──
    before = len(df)
    df = df[df["UnitPrice"] > 0]
    print(f"  After dropping UnitPrice<=0:      {len(df):>10,}  ({before - len(df):,} dropped)")

    # ── Drop non-product stock codes (POST, BANK CHARGES, M, DOT, etc.) ──
    # Real product codes start with a digit (e.g. 85123A, 22423).
    before = len(df)
    df = df[df["StockCode"].astype(str).str.match(r"^\d", na=False)]
    print(f"  After dropping special StockCodes:{len(df):>10,}  ({before - len(df):,} dropped)")

    # ── Drop null descriptions ──
    before = len(df)
    df = df.dropna(subset=["Description"])
    print(f"  After dropping null Description:  {len(df):>10,}  ({before - len(df):,} dropped)")

    # ── Type normalisation ──
    df["CustomerID"] = df["CustomerID"].astype(int).astype(str)
    df["Description"] = df["Description"].astype(str).str.strip()
    df["StockCode"] = df["StockCode"].astype(str).str.strip()
    df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()
    df["Quantity"] = df["Quantity"].astype(int)
    df["UnitPrice"] = df["UnitPrice"].astype(float)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["TotalAmount"] = df["Quantity"] * df["UnitPrice"]

    # ── Sampling (optional) ──
    # Prefer customer-based sampling: picks N random customers and keeps ALL
    # their transactions. Preserves full date span + per-customer history,
    # so cohort retention has multiple months and BG/NBD fit converges.
    if sample_customers and sample_customers < df["CustomerID"].nunique():
        unique_ids = df["CustomerID"].drop_duplicates()
        picked = unique_ids.sample(n=sample_customers, random_state=42).tolist()
        before = len(df)
        df = df[df["CustomerID"].isin(picked)].reset_index(drop=True)
        print(
            f"  Sampled {sample_customers:,} random customers "
            f"({before:,} -> {len(df):,} rows, full date span preserved)"
        )
    elif sample and sample < len(df):
        print(f"  Sampling first {sample:,} rows (chronological order)...")
        df = df.sort_values("InvoiceDate").head(sample).reset_index(drop=True)

    print()
    print(f"  Final cleaned rows:  {len(df):,}")
    print(f"  Unique customers:    {df['CustomerID'].nunique():,}")
    print(f"  Unique products:     {df['StockCode'].nunique():,}")
    print(f"  Unique invoices:     {df['InvoiceNo'].nunique():,}")
    print(f"  Date range:          {df['InvoiceDate'].min()} to {df['InvoiceDate'].max()}")
    print(f"  Total revenue:       £{df['TotalAmount'].sum():,.2f}")

    return df


# ══════════════════════════════════════════════════════════════════
#  INGEST
# ══════════════════════════════════════════════════════════════════

def ingest_to_db(
    df: pd.DataFrame,
    org_id: int,
    force: bool = False,
    store_name: str = DEFAULT_STORE_NAME,
    sku_prefix: str = DEFAULT_SKU_PREFIX,
):
    """Upsert Store, Products, Customers, and SalesTransactions."""
    db = SessionLocal()

    try:
        # ── 1. Get or create store ──
        store = db.query(Store).filter_by(
            organization_id=org_id,
            name=store_name,
        ).first()

        if store and not force:
            existing = db.query(SalesTransaction).join(Product).filter(
                Product.store_id == store.id
            ).count()
            if existing > 0:
                print(
                    f"\n  [!] Store '{store_name}' already has "
                    f"{existing:,} transactions."
                )
                print("  [!] Pass --force to wipe and re-ingest, or use a different --store-name.")
                return

        if not store:
            store = Store(
                organization_id=org_id,
                name=store_name,
                platform="Online Retail II (UCI)",
            )
            db.add(store)
            db.commit()
            db.refresh(store)
            print(f"  Created store: '{store.name}' (id={store.id})")
        else:
            print(f"  Using existing store: '{store.name}' (id={store.id})")

        # ── Clear previous data if force ──
        if force and store:
            print("  [force] Clearing existing Online Retail II data for this store...")
            # Delete transactions first (FK constraint)
            product_ids = [p.id for p in db.query(Product.id).filter_by(store_id=store.id).all()]
            if product_ids:
                db.query(SalesTransaction).filter(
                    SalesTransaction.product_id.in_(product_ids)
                ).delete(synchronize_session=False)
            db.query(Customer).filter_by(store_id=store.id).delete(synchronize_session=False)
            db.query(Product).filter_by(store_id=store.id).delete(synchronize_session=False)
            db.commit()

        # ── 2. Upsert products ──
        print("\n  [1/3] Upserting products...")
        unique_products = df.groupby("StockCode").agg({
            "Description": "first",
            "UnitPrice":   "mean",
        }).reset_index()

        product_id_map: dict[str, int] = {}
        new_products = 0

        for _, row in unique_products.iterrows():
            sku = f"{sku_prefix}{row['StockCode']}"
            existing = db.query(Product).filter_by(sku=sku).first()
            if existing:
                product_id_map[row["StockCode"]] = existing.id
                continue

            prod = Product(
                store_id=store.id,
                name=str(row["Description"])[:255],
                sku=sku,
                current_stock=100,   # synthetic default — Online Retail II has no inventory data
                reorder_point=20,
                price=float(row["UnitPrice"]),
            )
            db.add(prod)
            new_products += 1

        db.commit()
        print(f"    Created {new_products:,} new products")

        # Re-fetch any we missed from the map
        for _, row in unique_products.iterrows():
            if row["StockCode"] not in product_id_map:
                sku = f"{sku_prefix}{row['StockCode']}"
                p = db.query(Product).filter_by(sku=sku).first()
                if p:
                    product_id_map[row["StockCode"]] = p.id

        # ── 3. Upsert customers ──
        print("\n  [2/3] Upserting customers...")
        unique_customers = df.groupby("CustomerID").agg({
            "Country":     "first",
            "InvoiceDate": "min",
        }).reset_index()

        customer_id_map: dict[str, int] = {}
        new_customers = 0

        for _, row in unique_customers.iterrows():
            existing = db.query(Customer).filter_by(
                store_id=store.id,
                external_id=row["CustomerID"],
            ).first()
            if existing:
                customer_id_map[row["CustomerID"]] = existing.id
                continue

            cust = Customer(
                store_id=store.id,
                external_id=row["CustomerID"],
                country=str(row["Country"])[:100] if pd.notna(row["Country"]) else None,
                first_purchase_date=row["InvoiceDate"].to_pydatetime(),
            )
            db.add(cust)
            new_customers += 1

        db.commit()
        print(f"    Created {new_customers:,} new customers")

        # Re-fetch for map completeness
        for _, row in unique_customers.iterrows():
            if row["CustomerID"] not in customer_id_map:
                c = db.query(Customer).filter_by(
                    store_id=store.id,
                    external_id=row["CustomerID"],
                ).first()
                if c:
                    customer_id_map[row["CustomerID"]] = c.id

        # ── 4. Bulk-insert transactions ──
        print(f"\n  [3/3] Inserting sales transactions in batches of {BATCH_SIZE:,}...")

        total_rows = len(df)
        inserted = 0
        batch: list[dict] = []

        for row in df.itertuples(index=False):
            pid = product_id_map.get(row.StockCode)
            cid = customer_id_map.get(row.CustomerID)
            if pid is None:
                continue

            batch.append({
                "product_id":   pid,
                "customer_id":  cid,
                "invoice_no":   row.InvoiceNo,
                "quantity":     int(row.Quantity),
                "sale_date":    row.InvoiceDate.to_pydatetime(),
                "total_amount": float(row.TotalAmount),
            })

            if len(batch) >= BATCH_SIZE:
                db.bulk_insert_mappings(SalesTransaction, batch)
                db.commit()
                inserted += len(batch)
                pct = (inserted / total_rows) * 100
                print(f"    Inserted {inserted:>8,} / {total_rows:,} ({pct:.1f}%)")
                batch = []

        if batch:
            db.bulk_insert_mappings(SalesTransaction, batch)
            db.commit()
            inserted += len(batch)

        print(f"    Total inserted: {inserted:,} transactions")

        # ── 5. Final stats ──
        print()
        print("  " + "=" * 56)
        print("  INGESTION COMPLETE")
        print("  " + "=" * 56)
        print(f"  Organization id:  {org_id}")
        print(f"  Store:            '{store.name}' (id={store.id})")
        print(f"  Customers:        {db.query(Customer).filter_by(store_id=store.id).count():,}")
        print(f"  Products:         {db.query(Product).filter_by(store_id=store.id).count():,}")
        txn_count = db.query(SalesTransaction).join(Product).filter(
            Product.store_id == store.id
        ).count()
        print(f"  Transactions:     {txn_count:,}")
        print("  " + "=" * 56)

    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Ingest Online Retail II dataset from UCI ML Repository",
    )
    parser.add_argument(
        "--file", type=str, default="data/online_retail_II.xlsx",
        help="Path to xlsx file (relative to project root)",
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Download from UCI if file doesn't exist",
    )
    parser.add_argument(
        "--org-id", type=int, required=True,
        help="Organization id to attach the store to",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Clear existing Online Retail II data for this store before re-ingesting",
    )
    parser.add_argument(
        "--sample", type=int, default=None,
        help="Ingest first N cleaned rows chronologically (narrow time window). "
             "Use --sample-customers instead for demo stores.",
    )
    parser.add_argument(
        "--sample-customers", type=int, default=None,
        help="Pick N random customers and keep all their transactions. "
             "Preserves full date span and purchase histories — recommended for demo stores.",
    )
    parser.add_argument(
        "--store-name", type=str, default=DEFAULT_STORE_NAME,
        help=f"Name for the created store (default: '{DEFAULT_STORE_NAME}'). "
             "Use a different name to create a second OR-II store alongside the default.",
    )
    parser.add_argument(
        "--sku-prefix", type=str, default=DEFAULT_SKU_PREFIX,
        help=f"SKU prefix for products (default: '{DEFAULT_SKU_PREFIX}'). "
             "Must be unique per store to avoid global SKU collisions.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    file_path = project_root / args.file

    print("=" * 60)
    print("  ONLINE RETAIL II INGESTION")
    print("  Source:   UCI Machine Learning Repository")
    print("  Citation: Chen, Sain & Guo (2012)")
    print("=" * 60)
    print()

    # ── Step 1: Ensure file exists ──
    print("[STEP 1] Locating dataset file...")
    if not file_path.exists():
        if args.download:
            if not download_dataset(file_path):
                sys.exit(1)
        else:
            print(f"  File not found: {file_path}")
            print("  Options:")
            print(f"    1. Download manually and place at: {file_path}")
            print("    2. Re-run with --download to fetch automatically")
            print("    3. Pass a different path with --file")
            sys.exit(1)
    print(f"  Found: {file_path}")
    print()

    # ── Step 2: DB schema ──
    print("[STEP 2] Initializing database schema...")
    init_db()
    print("  Schema ready")
    print()

    # ── Step 3: Load + clean ──
    print("[STEP 3] Loading and cleaning dataset...")
    df = load_and_clean(
        file_path,
        sample=args.sample,
        sample_customers=args.sample_customers,
    )
    print()

    # ── Step 4: Ingest ──
    print("[STEP 4] Ingesting to database...")
    ingest_to_db(
        df,
        args.org_id,
        force=args.force,
        store_name=args.store_name,
        sku_prefix=args.sku_prefix,
    )


if __name__ == "__main__":
    main()
