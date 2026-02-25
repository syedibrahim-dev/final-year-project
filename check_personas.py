"""Quick script to check personas in database"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from utils.database import SessionLocal
    from models.roleplay import RoleplayPersona
    
    db = SessionLocal()
    
    personas = db.query(RoleplayPersona).all()
    
    print(f"\n{'='*60}")
    print(f"TOTAL PERSONAS IN DATABASE: {len(personas)}")
    print(f"{'='*60}\n")
    
    if personas:
        for p in personas:
            print(f"ID: {p.id}")
            print(f"Name: {p.name}")
            print(f"Difficulty: {p.difficulty}")
            print(f"Predefined: {p.is_predefined}")
            print(f"Organization ID: {p.organization_id}")
            print("-" * 40)
    else:
        print("❌ NO PERSONAS FOUND IN DATABASE")
        print("\nTo seed personas, run:")
        print("  python seed_personas.py")
    
    db.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
