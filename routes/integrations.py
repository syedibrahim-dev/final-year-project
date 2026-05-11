"""
Integrations API
================

Endpoints for connecting external ecommerce platforms, syncing their
data into SalesForge, and managing connected stores.

Routes:
  GET    /integrations/platforms          — list supported platforms
  POST   /integrations/connect            — test creds + save integration
  GET    /integrations                    — list org's connected stores
  POST   /integrations/{id}/sync          — pull latest data from platform
  DELETE /integrations/{id}               — disconnect (keeps synced data)
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from utils.database import get_db
from utils.dependencies import get_current_user
from models.user import User
from models.inventory import Store
from models.store_integration import StoreIntegration

from services.integrations.sync_service import (
    sync_integration,
    list_supported_platforms,
    get_integration_class,
)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


# ══════════════════════════════════════════════════════════════════
#  Schemas
# ══════════════════════════════════════════════════════════════════

class ConnectRequest(BaseModel):
    platform: str = Field(..., description="Platform identifier (e.g., 'fakestore')")
    store_name: str = Field(..., description="Display name for this connected store")
    api_key: Optional[str] = Field(None, description="Platform API key (if required)")
    api_secret: Optional[str] = Field(None, description="Platform API secret (if required)")
    base_url: Optional[str] = Field(None, description="Custom base URL (for self-hosted platforms)")


# ══════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════

def _verify_ownership(
    db: Session, integration_id: int, user: User
) -> tuple[StoreIntegration, Store]:
    integration = db.query(StoreIntegration).filter_by(id=integration_id).first()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    store = db.query(Store).filter_by(id=integration.store_id).first()
    if not store or store.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this integration",
        )
    return integration, store


def _serialize_integration(integration: StoreIntegration, store: Store) -> dict:
    summary = None
    if integration.last_sync_summary:
        try:
            summary = json.loads(integration.last_sync_summary)
        except json.JSONDecodeError:
            summary = None

    return {
        "id": integration.id,
        "store_id": integration.store_id,
        "store_name": store.name if store else None,
        "platform": integration.platform,
        "base_url": integration.base_url,
        "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
        "last_sync_status": integration.last_sync_status,
        "last_sync_error": integration.last_sync_error,
        "last_sync_summary": summary,
        "created_at": integration.created_at.isoformat() if integration.created_at else None,
    }


# ══════════════════════════════════════════════════════════════════
#  Routes
# ══════════════════════════════════════════════════════════════════

@router.get("/platforms")
def list_platforms(current_user: User = Depends(get_current_user)):
    """List supported integration platforms with metadata."""
    return {"platforms": list_supported_platforms()}


@router.post("/connect")
def connect_store(
    req: ConnectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Test platform credentials and save a new StoreIntegration.
    On success, returns the new integration id + store id so the frontend
    can immediately trigger a sync.
    """
    cls = get_integration_class(req.platform)
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown platform: {req.platform}",
        )

    # Test connection BEFORE writing to DB
    client = cls(api_key=req.api_key, api_secret=req.api_secret, base_url=req.base_url)
    test = client.test_connection()
    if not test.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection test failed: {test.get('message', 'unknown error')}",
        )

    # Create Store
    store = Store(
        organization_id=current_user.organization_id,
        name=req.store_name,
        platform=req.platform,
    )
    db.add(store)
    db.commit()
    db.refresh(store)

    # Save integration
    integration = StoreIntegration(
        store_id=store.id,
        platform=req.platform,
        api_key_encrypted=req.api_key,         # TODO: Fernet encryption
        api_secret_encrypted=req.api_secret,   # TODO: Fernet encryption
        base_url=req.base_url,
        last_sync_status="never",
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)

    return {
        "id": integration.id,
        "store_id": store.id,
        "store_name": store.name,
        "platform": integration.platform,
        "connection_test": test,
    }


@router.get("")
def list_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all connected integrations for the current user's organisation."""
    rows = (
        db.query(StoreIntegration, Store)
        .join(Store, Store.id == StoreIntegration.store_id)
        .filter(Store.organization_id == current_user.organization_id)
        .all()
    )
    return {
        "integrations": [_serialize_integration(i, s) for i, s in rows],
    }


@router.get("/{integration_id}")
def get_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get details of a single integration."""
    integration, store = _verify_ownership(db, integration_id, current_user)
    return _serialize_integration(integration, store)


@router.post("/{integration_id}/sync")
def sync_store(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pull latest products/customers/transactions from the platform."""
    integration, _ = _verify_ownership(db, integration_id, current_user)

    result = sync_integration(db, integration)
    if not result.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {result.get('error', 'unknown error')}",
        )

    return {
        "ok": True,
        "integration_id": integration.id,
        "summary": result.get("summary"),
        "synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
    }


@router.delete("/{integration_id}")
def disconnect_store(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove an integration. Keeps synced data (Products, Customers, Transactions)."""
    integration, _ = _verify_ownership(db, integration_id, current_user)

    db.delete(integration)
    db.commit()
    return {"ok": True, "message": "Integration removed"}
