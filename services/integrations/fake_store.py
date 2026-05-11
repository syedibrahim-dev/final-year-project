"""
Fake Store API Integration
===========================

Public ecommerce demo API at fakestoreapi.com. No authentication required.
Useful as a zero-friction backup demo when real platform credentials
aren't available.

Dataset: ~20 products, 10 users, 20 carts. Good for proving the
integration pattern works end-to-end without any account setup.

API endpoints used:
  GET /products           → list all products
  GET /users              → list all users (→ Customer)
  GET /carts              → list all carts (→ SalesTransaction)

Docs: fakestoreapi.com
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from .base import BaseIntegration

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://fakestoreapi.com"
SKU_PREFIX = "FAKE_"
REQUEST_TIMEOUT = 15


class FakeStoreIntegration(BaseIntegration):
    platform_name = "fakestore"
    display_name = "Fake Store API"
    requires_api_key = False
    description = (
        "Public demo ecommerce API. ~20 sample products, 10 users, 20 carts. "
        "Zero authentication — perfect backup demo when real store credentials "
        "aren't available."
    )

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        super().__init__(
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url or DEFAULT_BASE_URL,
        )

    # ── HTTP helper ─────────────────────────────────────────────────

    def _get(self, path: str) -> Any:
        url = f"{self.base_url.rstrip('/')}{path}"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    # ── Interface implementation ────────────────────────────────────

    def test_connection(self) -> Dict[str, Any]:
        try:
            data = self._get("/products?limit=1")
            if not isinstance(data, list):
                return {
                    "ok": False,
                    "message": "Unexpected response shape from /products",
                    "info": {},
                }
            return {
                "ok": True,
                "message": f"Connected to {self.base_url}",
                "info": {
                    "endpoint": self.base_url,
                    "sample_product_count": len(data),
                },
            }
        except requests.exceptions.RequestException as e:
            return {
                "ok": False,
                "message": f"Network error: {e}",
                "info": {},
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"Unexpected error: {e}",
                "info": {},
            }

    def fetch_products(self) -> List[Dict[str, Any]]:
        raw = self._get("/products")
        products: List[Dict[str, Any]] = []
        for p in raw:
            pid = p.get("id")
            if pid is None:
                continue
            products.append({
                "external_id": str(pid),
                "name": str(p.get("title", f"Product {pid}"))[:255],
                "sku": f"{SKU_PREFIX}{pid}",
                "price": float(p.get("price") or 0.0),
            })
        logger.info(f"FakeStore: fetched {len(products)} products")
        return products

    def fetch_customers(self) -> List[Dict[str, Any]]:
        raw = self._get("/users")
        customers: List[Dict[str, Any]] = []
        for u in raw:
            uid = u.get("id")
            if uid is None:
                continue
            # Fake Store API users have an 'address' with city but no country.
            # Use a placeholder so analytics don't crash.
            addr = u.get("address") or {}
            city = addr.get("city") or ""
            customers.append({
                "external_id": str(uid),
                "email": u.get("email"),
                # We'll expose the city as "country" field since it's the closest geo attribute.
                "country": city[:100] if city else None,
                # first_purchase_date is derived later from cart data during sync.
                "first_purchase_date": None,
            })
        logger.info(f"FakeStore: fetched {len(customers)} customers")
        return customers

    def fetch_transactions(
        self, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        # Build product price map so we can compute total_amount
        products_raw = self._get("/products")
        price_map: Dict[int, float] = {
            int(p["id"]): float(p.get("price") or 0.0)
            for p in products_raw
            if p.get("id") is not None
        }

        carts = self._get("/carts")
        transactions: List[Dict[str, Any]] = []

        for cart in carts:
            cart_id = cart.get("id")
            user_id = cart.get("userId")
            date_str = cart.get("date")
            if cart_id is None or user_id is None or date_str is None:
                continue

            # Fake Store returns dates like "2020-03-02T00:00:00.000Z"
            try:
                cart_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                # Strip tzinfo so we can compare with the naive `sale_date` column.
                cart_date = cart_date.replace(tzinfo=None)
            except Exception:
                logger.warning(f"FakeStore: could not parse date '{date_str}' for cart {cart_id}")
                continue

            if since is not None and cart_date < since:
                continue

            items = cart.get("products") or []
            for item in items:
                pid = item.get("productId")
                qty = item.get("quantity")
                if pid is None or qty is None:
                    continue

                unit_price = price_map.get(int(pid), 0.0)
                total = float(qty) * unit_price

                transactions.append({
                    "invoice_no": str(cart_id),
                    "customer_external_id": str(user_id),
                    "product_external_id": str(pid),
                    "quantity": int(qty),
                    "unit_price": unit_price,
                    "total_amount": total,
                    "sale_date": cart_date,
                })

        logger.info(f"FakeStore: fetched {len(transactions)} transactions from {len(carts)} carts")
        return transactions
