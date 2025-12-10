"""
Seed script to populate roleplay_personas table with pre-defined personas
Run this after database tables are created
"""
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.database import SessionLocal
from models.roleplay import RoleplayPersona

def seed_personas():
    """Load personas from JSON and insert into database"""
    
    print("\n" + "="*60)
    print("SEEDING ROLEPLAY PERSONAS")
    print("="*60)
    
    # Load personas from JSON
    personas_file = Path(__file__).parent / "data" / "personas.json"
    
    if not personas_file.exists():
        print(f"Error: {personas_file} not found")
        return False
    
    with open(personas_file, 'r') as f:
        personas_data = json.load(f)
    
    print(f"Loaded {len(personas_data)} personas from JSON")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Check if personas already exist
        existing_count = db.query(RoleplayPersona).filter_by(is_predefined=True).count()
        
        if existing_count > 0:
            print(f"Warning: Found {existing_count} existing predefined personas")
            response = input("Do you want to replace them? (y/n): ")
            if response.lower() != 'y':
                print("Seeding cancelled")
                return False
            
            # Delete existing predefined personas
            db.query(RoleplayPersona).filter_by(is_predefined=True).delete()
            db.commit()
            print("Deleted existing predefined personas")
        
        # Insert new personas
        inserted = 0
        for persona_data in personas_data:
            persona = RoleplayPersona(
                name=persona_data['name'],
                description=persona_data['description'],
                personality_traits=persona_data['personality_traits'],
                common_objections=persona_data['common_objections'],
                tone=persona_data['tone'],
                difficulty=persona_data['difficulty'],
                is_predefined=True,
                created_by=None,  # System personas have no creator
                organization_id=None  # Available to all organizations
            )
            db.add(persona)
            inserted += 1
            print(f"  + Added: {persona.name}")
        
        db.commit()
        
        print(f"\nSuccessfully seeded {inserted} personas")
        print("="*60 + "\n")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"\nError seeding personas: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()

if __name__ == "__main__":
    success = seed_personas()
    sys.exit(0 if success else 1)
