"""
Seed script to populate roleplay_personas table with pre-defined personas.
Run this after database tables are created or updated.
Handles: scenario_brief, trigger_topics, rag_probing_style (stored in personality_traits)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.database import SessionLocal
from models.roleplay import RoleplayPersona


def seed_personas():
    """Load personas from JSON and insert into database"""

    print("\n" + "="*60)
    print("SEEDING ROLEPLAY PERSONAS")
    print("="*60)

    personas_file = Path(__file__).parent / "data" / "personas.json"

    if not personas_file.exists():
        print(f"Error: {personas_file} not found")
        return False

    with open(personas_file, 'r') as f:
        personas_data = json.load(f)

    print(f"Loaded {len(personas_data)} personas from JSON")

    db = SessionLocal()

    try:
        existing_count = db.query(RoleplayPersona).filter_by(is_predefined=True).count()

        if existing_count > 0:
            print(f"Warning: Found {existing_count} existing predefined personas")
            response = input("Do you want to replace them? (y/n): ")
            if response.lower() != 'y':
                print("Seeding cancelled")
                return False

            db.query(RoleplayPersona).filter_by(is_predefined=True).delete()
            db.commit()
            print("Deleted existing predefined personas")

        inserted = 0
        for persona_data in personas_data:
            persona = RoleplayPersona(
                name=persona_data['name'],
                description=persona_data['description'],
                scenario_brief=persona_data.get('scenario_brief'),
                personality_traits=persona_data['personality_traits'],   # includes rag_probing_style
                trigger_topics=persona_data.get('trigger_topics'),
                company_context=persona_data.get('company_context'),
                common_objections=persona_data['common_objections'],
                tone=persona_data['tone'],
                difficulty=persona_data['difficulty'],
                scenario_type=persona_data.get('scenario_type', 'acquisition'),
                is_predefined=True,
                created_by=None,
                organization_id=None
            )
            db.add(persona)
            inserted += 1
            rag_style = persona_data['personality_traits'].get('rag_probing_style', 'N/A')
            print(f"  + Added: {persona_data['name']} ({persona_data['difficulty']}) [RAG: {rag_style}]")

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
