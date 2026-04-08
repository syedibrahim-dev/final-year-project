import random
from datetime import datetime, timedelta
from utils.database import SessionLocal, init_db
from models.inventory import Store, Product, SalesTransaction, InventoryForecast, StockAlert
from models.organization import Organization

def seed_inventory_data():
    init_db()
    db = SessionLocal()
    
    print("🌱 Seeding inventory data...")
    try:
        # Get first active organization or create one
        org_id = 1 # Assuming Org 1 exists from previous testing
        org = db.query(Organization).filter(Organization.id == org_id).first()
        
        if not org:
            print("❌ Organization 1 not found. Please ensure users are seeded first.")
            return

        # 1. Create a Store
        store = db.query(Store).filter(Store.organization_id == org.id).first()
        if not store:
            store = Store(
                organization_id=org.id,
                name="SalesForge Demo Store",
                platform="Shopify"
            )
            db.add(store)
            db.commit()
            db.refresh(store)
            print(f"✅ Created Store: {store.name}")
        else:
            print(f"✅ Using existing Store: {store.name}")

        # 2. Create Products
        products_to_seed = [
            {
                "name": "Wireless Noise-Canceling Headphones",
                "sku": "HEADPH-001",
                "current_stock": 45,
                "reorder_point": 10,
                "price": 199.99,
                "days_history": 60, # Fits Prophet
                "velocity": 2.5
            },
            {
                "name": "Ergonomic Office Chair",
                "sku": "FURN-CHAIR-X",
                "current_stock": 5,
                "reorder_point": 10,
                "price": 249.00,
                "days_history": 80, # Fits Prophet, Low stock
                "velocity": 0.8
            },
            {
                "name": "Smart Fitness Watch",
                "sku": "WEAR-FW-22",
                "current_stock": 120,
                "reorder_point": 20,
                "price": 129.50,
                "days_history": 20, # Fits EWMA (Under 35)
                "velocity": 1.2
            },
            {
                "name": "Mechanical Gaming Keyboard",
                "sku": "KB-MECH-RGB",
                "current_stock": 0,
                "reorder_point": 15,
                "price": 89.99,
                "days_history": 45, # Out of stock
                "velocity": 3.0
            }
        ]

        # Clean existing data to avoid duplicates over multiple runs
        db.query(Product).filter(Product.store_id == store.id).delete()
        db.commit()

        for p_data in products_to_seed:
            product = Product(
                store_id=store.id,
                name=p_data["name"],
                sku=p_data["sku"],
                current_stock=p_data["current_stock"],
                reorder_point=p_data["reorder_point"],
                price=p_data["price"]
            )
            db.add(product)
            db.commit()
            db.refresh(product)
            print(f"  - Created Product: {product.name} (ID: {product.id})")

            # 3. Create historical sales transactions
            print(f"    - Generating {p_data['days_history']} days of history...")
            end_date = datetime.utcnow()
            transactions = []
            
            for days_back in range(p_data['days_history'], 0, -1):
                sale_date = end_date - timedelta(days=days_back)
                
                # Add some randomness and seasonality
                base_qty = p_data["velocity"]
                
                # Weekend bump
                if sale_date.weekday() >= 5:
                    base_qty *= 1.5
                    
                # Strict randomness
                qty = max(0, int(random.gauss(base_qty, base_qty * 0.4)))
                
                if qty > 0:
                    t = SalesTransaction(
                        product_id=product.id,
                        quantity=qty,
                        sale_date=sale_date,
                        total_amount=qty * p_data["price"]
                    )
                    transactions.append(t)
            
            db.bulk_save_objects(transactions)
            db.commit()
            
            # Immediately generate an alert if needed
            if product.current_stock <= 0:
                alert = StockAlert(
                    product_id=product.id,
                    alert_type="OUT_OF_STOCK",
                    message=f"Product {product.name} is out of stock!"
                )
                db.add(alert)
            elif product.current_stock <= product.reorder_point:
                alert = StockAlert(
                    product_id=product.id,
                    alert_type="LOW_STOCK",
                    message=f"Product {product.name} has reached reorder point ({product.current_stock} remaining)."
                )
                db.add(alert)
                
            db.commit()

        print("✅ Seeding complete!")
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_inventory_data()
