"""
Test script to verify personas endpoint is working
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# First, login to get a token
def login_and_test():
    # Try to login (you'll need valid credentials)
    print("🔐 Attempting to login...")
    
    # Login as admin (adjust credentials as needed)
    login_data = {
        'username': 'admin@gmail.com',  # Existing admin user
        'password': 'password123'  # Try common password
    }
    
    try:
        # Login
        response = requests.post(
            f"{BASE_URL}/auth/login",
            data=login_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if response.status_code == 200:
            token_data = response.json()
            token = token_data.get('access_token')
            print(f"✅ Login successful! Token: {token[:20]}...")
            
            # Now test personas endpoint
            print("\n📋 Fetching personas...")
            personas_response = requests.get(
                f"{BASE_URL}/roleplay/personas",
                headers={'Authorization': f'Bearer {token}'}
            )
            
            if personas_response.status_code == 200:
                personas_data = personas_response.json()
                personas = personas_data.get('personas', [])
                print(f"✅ Personas fetched successfully!")
                print(f"📊 Found {len(personas)} personas:")
                for p in personas:
                    print(f"   • {p['name']} ({p['difficulty']}) - {p['description'][:50]}...")
            else:
                print(f"❌ Failed to fetch personas: {personas_response.status_code}")
                print(f"Response: {personas_response.text}")
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"Response: {response.text}")
            print("\n💡 Make sure you have a valid admin user created.")
            print("   You may need to check the database or create a user first.")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend server!")
        print("   Make sure the server is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    login_and_test()
