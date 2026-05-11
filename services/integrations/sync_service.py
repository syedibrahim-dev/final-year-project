"""
Sync Service — orchestrates pulling data from a connected platform
and upserting into the SalesForge database.

Design notes:
  - One entry point: `sync_integration(db, integration)`
  - Platform-specific logic lives in the integration class (inherits BaseIntegration)
  - This file is responsible ONLY for the DB upsert + idempotency layer
  - Idempotency: transactions are deduped via (invoice_no, product_id) pairs
    so calling sync() multiple times is safe
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from sqlalchemy.orm import Session

from models.inventory import Store, Product, Customer, SalesTransaction
from models.store_integration import StoreIntegration

from .base import BaseIntegration
from .fake_store import FakeStoreIntegration

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  PLATFORM REGISTRY
# ══════════════════════════════════════════════════════════════════

INTEGRATION_REGISTRY: Dict[str, Type[BaseIntegration]] = {
    FakeStoreIntegration.platform_name: FakeStoreIntegration,
    # Future integrations register here:
    # SwellIntegration.platform_name:   SwellIntegration,
    # ShopifyIntegration.platform_name: ShopifyIntegration,
}


def get_integration_class(platform: str) -> Optional[Type[BaseIntegration]]:
    """Look up an integration class by platform name."""
    return INTEGRATION_REGISTRY.get((platform or "").lower())


def list_supported_platforms() -> List[Dict[str, Any]]:
    """Return metadata for the frontend platform picker."""
    return [
        {
            "platform": cls.platform_name,
            "display_name": cls.display_name,
            "description": cls.description,
            "requires_api_key": cls.requires_api_key,
        }
        for cls in INTEGRATION_REGISTRY.values()
    ]


# ══════════════════════════════════════════════════════════════════
#  SYNC ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════

def _instantiate_client(integration: StoreIntegration) -> Optional[BaseIntegration]:
    """Build a platform client from a StoreIntegration record."""
    cls = get_integration_class(integration.platform)
    if cls is None:
        logger.error(f"Unknown platform '{integration.platform}' for integration {integration.id}")
        return None

    # TODO: Fernet-decrypt these fields when encryption is wired up.
    api_key = integration.api_key_encrypted
    api_secret = integration.api_secret_encrypted

    return cls(
        api_key=api_key,
        api_secret=api_secret,
        base_url=integration.base_url,
    )


def _upsert_products(
    db: Session,
    store: Store,
    products_data: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Upsert products by SKU, return {external_id: product_id}."""
    external_to_id: Dict[str, int] = {}
    created = 0
    updated = 0

    for p in products_data:
        sku = p["sku"]
        existing = db.query(Product).filter_by(sku=sku).first()

        if existing:
            existing.name = p["name"]
            existing.price = p["price"]
            if existing.store_id != store.id:
                # SKU collided across stores — this shouldn't happen if prefixes
                # are used, but log and skip to avoid cross-store contamination.
                logger.warning(
                    f"Product SKU '{sku}' already exists in store "
                    f"{existing.store_id}, skipping for store {store.id}"
                )
                continue
            external_to_id[p["external_id"]] = existing.id
            updated += 1
        else:
            prod = Product(
                store_id=store.id,
                name=p["name"],
                sku=sku,
                current_stock=100,       # synthetic default
                reorder_point=20,
                price=p["price"],
            )
            db.add(prod)
            db.flush()                    # assign id before commit
            external_to_id[p["external_id"]] = prod.id
            created += 1

    db.commit()
    logger.info(f"Products: {created} created, {updated} updated")
    return external_to_id


def _upsert_customers(
    db: Session,
    store: Store,
    customers_data: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Upsert customers by (store_id, external_id), return {external_id: customer_id}."""
    external_to_id: Dict[str, int] = {}
    created = 0
    updated = 0

    for c in customers_data:
        external_id = c["external_id"]
        existing = db.query(Customer).filter_by(
            store_id=store.id,
            external_id=external_id,
        ).first()

        if existing:
            if c.get("email"):
                existing.email = c["email"]
            if c.get("country"):
                existing.country = c["country"]
            external_to_id[external_id] = existing.id
            updated += 1
        else:
            cust = Customer(
                store_id=store.id,
                external_id=external_id,
                email=c.get("email"),
                country=c.get("country"),
                first_purchase_date=c.get("first_purchase_date"),
            )
            db.add(cust)
            db.flush()
            external_to_id[external_id] = cust.id
            created += 1

    db.commit()
    logger.info(f"Customers: {created} created, {updated} updated")
    return external_to_id


def _upsert_transactions(
    db: Session,
    transactions_data: List[Dict[str, Any]],
    product_id_map: Dict[str, int],
    customer_id_map: Dict[str, int],
) -> Dict[str, int]:
    """
    Insert new SalesTransactions.

    Dedup strategy: (invoice_no, product_id) — a transaction with the same
    invoice+product is considered already recorded. This keeps sync idempotent
    without requiring the platform to expose a globally unique txn id.
    """
    if not transactions_data:
        return {"inserted": 0, "skipped_missing_ref": 0, "skipped_duplicate": 0}

    # Pre-fetch existing (invoice_no, product_id) pairs for this batch
    invoice_nos = list({t["invoice_no"] for t in transactions_data if t.get("invoice_no")})
    existing_keys: set = set()
    if invoice_nos:
        existing = (
            db.query(SalesTransaction.invoice_no, SalesTransaction.product_id)
            .filter(SalesTransaction.invoice_no.in_(invoice_nos))
            .all()
        )
        existing_keys = {(row[0], row[1]) for row in existing}

    to_insert: List[Dict[str, Any]] = []
    skipped_missing_ref = 0
    skipped_duplicate = 0

    for t in transactions_data:
        pid = product_id_map.get(t["product_external_id"])
        cid = customer_id_map.get(t["customer_external_id"])

        if pid is None:
            skipped_missing_ref += 1
            continue

        key = (t["invoice_no"], pid)
        if key in existing_keys:
            skipped_duplicate += 1
            continue

        to_insert.append({
            "product_id":   pid,
            "customer_id":  cid,
            "invoice_no":   t["invoice_no"],
            "quantity":     int(t["quantity"]),
            "sale_date":    t["sale_date"],
            "total_amount": float(t["total_amount"]),
        })
        existing_keys.add(key)   # dedupe within the current batch too

    if to_insert:
        db.bulk_insert_mappings(SalesTransaction, to_insert)
        db.commit()

    logger.info(
        f"Transactions: {len(to_insert)} inserted, "
        f"{skipped_duplicate} duplicate, {skipped_missing_ref} missing product ref"
    )
    return {
        "inserted": len(to_insert),
        "skipped_duplicate": skipped_duplicate,
        "skipped_missing_ref": skipped_missing_ref,
    }


def _refresh_first_purchase_dates(db: Session, store: Store) -> int:
    """
    After inserting transactions, backfill Customer.first_purchase_date
    for any customer whose value is still NULL. One UPDATE per customer —
    small store so fine; for huge syncs we'd do this in a single SQL query.
    """
    customers = (
        db.query(Customer)
        .filter(Customer.store_id == store.id, Customer.first_purchase_date.is_(None))
        .all()
    )
    updated = 0
    for cust in customers:
        earliest = (
            db.query(SalesTransaction.sale_date)
            .filter(SalesTransaction.customer_id == cust.id)
            .order_by(SalesTransaction.sale_date.asc())
            .first()
        )
        if earliest and earliest[0]:
            cust.first_purchase_date = earliest[0]
            updated += 1
    if updated:
        db.commit()
    return updated


def sync_integration(
    db: Session,
    integration: StoreIntegration,
) -> Dict[str, Any]:
    """
    Main entry point. Pull all data from the integration's platform and
    upsert it into the database. Updates the integration's sync state.

    Returns:
        {"ok": bool, "summary": {...}, "error": str | None}
    """
    client = _instantiate_client(integration)
    if client is None:
        return {"ok": False, "error": f"Unknown platform: {integration.platform}"}

    store = db.query(Store).filter_by(id=integration.store_id).first()
    if store is None:
        return {"ok": False, "error": "Store not found"}

    # Mark sync in progress
    integration.last_sync_status = "in_progress"
    integration.last_sync_error = None
    db.commit()

    try:
        # ── 1. Fetch from platform ──
        logger.info(f"[{integration.platform}] Fetching products...")
        products_data = client.fetch_products()

        logger.info(f"[{integration.platform}] Fetching customers...")
        customers_data = client.fetch_customers()

        logger.info(f"[{integration.platform}] Fetching transactions...")
        transactions_data = client.fetch_transactions()

        # ── 2. Upsert ──
        product_id_map = _upsert_products(db, store, products_data)
        customer_id_map = _upsert_customers(db, store, customers_data)
        txn_stats = _upsert_transactions(
            db, transactions_data, product_id_map, customer_id_map
        )

        # ── 3. Backfill first_purchase_date on customers ──
        fpd_updated = _refresh_first_purchase_dates(db, store)

        # ── 4. Write summary ──
        summary = {
            "products_fetched":      len(products_data),
            "customers_fetched":     len(customers_data),
            "transactions_fetched":  len(transactions_data),
            "transactions_inserted": txn_stats["inserted"],
            "transactions_duplicate": txn_stats["skipped_duplicate"],
            "transactions_missing_product": txn_stats["skipped_missing_ref"],
            "customers_backfilled_first_purchase": fpd_updated,
        }

        integration.last_sync_status = "success"
        integration.last_sync_error = None
        integration.last_sync_summary = json.dumps(summary)
        integration.last_synced_at = datetime.utcnow()
        db.commit()

        return {"ok": True, "summary": summary}

    except Exception as e:
        logger.error(f"[{integration.platform}] Sync failed: {e}")
        import traceback
        traceback.print_exc()

        integration.last_sync_status = "failed"
        integration.last_sync_error = str(e)[:1000]
        db.commit()

        return {"ok": False, "error": str(e)}
