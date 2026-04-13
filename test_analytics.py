import sys
sys.path.append('.')

from utils.database import SessionLocal
from services.analytics_service import get_store_kpis, get_sales_trends, get_top_products, detect_sales_anomalies

def test_analytics():
    print("Testing Analytics Services...\n")
    db = SessionLocal()
    org_id = 1 # Assuming seeded data is on org 1
    
    try:
        print("--- KPIs ---")
        kpis = get_store_kpis(db, org_id)
        print("Revenue:", kpis['revenue'])
        print("Orders:", kpis['orders'])
        print("AOV:", kpis['aov'])
        
        print("\n--- Sales Trends (7 days) ---")
        trends = get_sales_trends(db, org_id, days=7)
        for t in trends:
            print(t)
            
        print("\n--- Top Products ---")
        top = get_top_products(db, org_id, limit=3)
        for item in top:
            print(item)
            
        print("\n--- Anomalies ---")
        anomalies = detect_sales_anomalies(db, org_id, days=60)
        print(f"Found {len(anomalies)} anomalies")
        for a in anomalies[:5]:
            print(a)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("\n🚨 Test Failed:", e)
    finally:
        db.close()

if __name__ == "__main__":
    test_analytics()
