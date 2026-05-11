from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from utils.database import Base

class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    platform = Column(String(100), nullable=True) # e.g., Shopify, WooCommerce
    created_at = Column(DateTime, default=datetime.utcnow)
    
    products = relationship("Product", back_populates="store", cascade="all, delete-orphan")
    organization = relationship("Organization", backref="stores")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    sku = Column(String(100), unique=True, index=True)
    current_stock = Column(Integer, default=0)
    reorder_point = Column(Integer, default=10) # Level at which to trigger alert
    price = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    store = relationship("Store", back_populates="products")
    transactions = relationship("SalesTransaction", back_populates="product", cascade="all, delete-orphan")
    forecasts = relationship("InventoryForecast", back_populates="product", cascade="all, delete-orphan")
    alerts = relationship("StockAlert", back_populates="product", cascade="all, delete-orphan")

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id = Column(String(100), nullable=True, index=True)  # Shopify / Online Retail customer id
    email = Column(String(255), nullable=True)
    country = Column(String(100), nullable=True)
    first_purchase_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    store = relationship("Store", backref="customers")
    transactions = relationship("SalesTransaction", back_populates="customer")


class SalesTransaction(Base):
    __tablename__ = "sales_transactions"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_no = Column(String(50), nullable=True, index=True)   # groups transactions into orders (Shopify order id / Online Retail invoice)
    quantity = Column(Integer, nullable=False)
    sale_date = Column(DateTime, default=datetime.utcnow, index=True)
    total_amount = Column(Float, nullable=True)

    product = relationship("Product", back_populates="transactions")
    customer = relationship("Customer", back_populates="transactions")

class InventoryForecast(Base):
    __tablename__ = "inventory_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    forecast_date = Column(DateTime, default=datetime.utcnow) # When the forecast was made
    predicted_depletion_date = Column(DateTime, nullable=True) # When stock hits 0
    model_used = Column(String(50)) # 'prophet' or 'ewma'
    confidence_score = Column(Float, nullable=True) # e.g., 0 to 1
    
    product = relationship("Product", back_populates="forecasts")

class StockAlert(Base):
    __tablename__ = "stock_alerts"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    alert_type = Column(String(50)) # e.g., 'LOW_STOCK', 'DEPLETION_WARNING'
    message = Column(String(500))
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    product = relationship("Product", back_populates="alerts")
