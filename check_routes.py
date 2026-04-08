import requests
try:
    info = requests.get('http://localhost:8000/info').json()
    print("Registered Endpoints:")
    for k, v in info.get("endpoints", {}).items():
        print(f"- {k}: {v}")
    
    # Check directly
    r = requests.get('http://localhost:8000/inventory/products', headers={"Authorization": "Bearer fake"})
    print("\nInventory endpoint status:", r.status_code)
except Exception as e:
    print("Failed request:", e)
