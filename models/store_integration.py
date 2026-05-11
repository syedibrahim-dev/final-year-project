"""
Store Integration Model
========================

Tracks a connected ecommerce platform (Fake Store API, Swell, Shopify,
WooCommerce, etc.) per Store. One Store = at most one integration.

Credential fields are stored as opaque strings — encryption/decryption
is handled by the services/integrations layer so the model stays simple.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from utils.database import Base


class StoreIntegration(Base):
    __tablename__ = "store_integrations"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(
        Integer,
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # one integration per store
        index=True,
    )

    # Platform identifier used to look up the integration class
    # (e.g., "fakestore", "swell", "shopify", "woocommerce")
    platform = Column(String(50), nullable=False)

    # Credentials — nullable because some platforms (Fake Store API) need no auth.
    # For production, these should be Fernet-encrypted at the service layer.
    api_key_encrypted = Column(Text, nullable=True)
    api_secret_encrypted = Column(Text, nullable=True)

    # For self-hosted platforms (e.g., Medusa) or custom endpoints
    base_url = Column(String(500), nullable=True)

    # Sync state
    last_synced_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(50), nullable=True)   # "never", "in_progress", "success", "failed"
    last_sync_error = Column(Text, nullable=True)
    last_sync_summary = Column(Text, nullable=True)        # JSON: {"products": N, "customers": N, "transactions": N}

    created_at = Column(DateTime, default=datetime.utcnow)

    store = relationship("Store", backref="integration", uselist=False)
