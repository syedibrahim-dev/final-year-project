"""
Check database for users and organizations
"""
from sqlalchemy import create_engine, text
from config.settings import settings

engine = create_engine(settings.DATABASE_URL)

print("🔍 Checking database for users and organizations...\n")

with engine.connect() as conn:
    # Check organizations
    orgs = conn.execute(text("SELECT id, name, created_at FROM organizations")).fetchall()
    print(f"📊 Organizations: {len(orgs)}")
    for org in orgs:
        print(f"   • ID: {org[0]}, Name: {org[1]}, Created: {org[2]}")
    
    print()
    
    # Check users
    users = conn.execute(text("SELECT id, email, role, organization_id, created_at FROM users")).fetchall()
    print(f"👥 Users: {len(users)}")
    for user in users:
        print(f"   • ID: {user[0]}, Email: {user[1]}, Role: {user[2]}, Org ID: {user[3]}, Created: {user[4]}")
    
    print()
    
    # Check personas
    personas = conn.execute(text("SELECT id, name, difficulty, is_predefined FROM roleplay_personas")).fetchall()
    print(f"🎭 Personas: {len(personas)}")
    for persona in personas:
        print(f"   • ID: {persona[0]}, Name: {persona[1]}, Difficulty: {persona[2]}, Predefined: {persona[3]}")

print("\n✅ Database check complete!")
