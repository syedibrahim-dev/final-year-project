from utils.database import SessionLocal
from services.inventory_service import generate_forecast
from models.inventory import Product, Store
from models.organization import Organization

def test_forecasts():
    db = SessionLocal()
    try:
        org_id = 1
        store = db.query(Store).filter(Store.organization_id == org_id).first()
        if not store:
            print("No store found!")
            return
            
        products = db.query(Product).filter(Product.store_id == store.id).all()
        for p in products:
            print(f"\n--- Testing Forecast for {p.name} (ID: {p.id}) ---")
            try:
                res = generate_forecast(db, org_id, p.id)
                print("Result:", res)
            except Exception as e:
                print(f"Error forecasting {p.name}: {e}")
                
    finally:
        db.close()

if __name__ == "__main__":
    test_forecasts()
