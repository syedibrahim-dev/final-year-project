"""
Base Integration — abstract interface every platform adapter implements.

The design keeps adapters stateless: you instantiate with credentials,
then call fetch_* methods which return uniform dict payloads. The sync
service then upserts those payloads into the SalesForge DB.

Uniform payload shapes (all keys required unless marked optional):

  Product:
    {
      "external_id":  str,   # platform's product id
      "name":         str,
      "sku":          str,   # MUST be unique across integrations (use prefix)
      "price":        float,
    }

  Customer:
    {
      "external_id":         str,
      "email":               str | None,
      "country":             str | None,
      "first_purchase_date": datetime | None,
    }

  Transaction:
    {
      "invoice_no":             str,   # order id from platform
      "customer_external_id":   str,
      "product_external_id":    str,
      "quantity":               int,
      "unit_price":             float,
      "total_amount":           float,
      "sale_date":              datetime,
    }
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class BaseIntegration(ABC):
    """Abstract base for all platform adapters."""

    # Override in subclass
    platform_name: str = "base"
    display_name: str = "Base Integration"
    requires_api_key: bool = True
    description: str = ""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url

    # ── Required interface ──────────────────────────────────────────

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """
        Return {"ok": bool, "message": str, "info": dict}.
        Called by the /integrations/connect route before saving credentials.
        """
        ...

    @abstractmethod
    def fetch_products(self) -> List[Dict[str, Any]]:
        """Return a list of product dicts (see module docstring for shape)."""
        ...

    @abstractmethod
    def fetch_customers(self) -> List[Dict[str, Any]]:
        """Return a list of customer dicts."""
        ...

    @abstractmethod
    def fetch_transactions(
        self, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Return a list of transaction dicts.
        If `since` is provided, only include transactions after that time
        (for incremental sync). Platforms without timestamp filters can
        return all and the sync layer will dedupe on invoice_no.
        """
        ...
