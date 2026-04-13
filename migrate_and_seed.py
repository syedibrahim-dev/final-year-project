"""
Migration + Seed runner.
- Adds scenario_brief and trigger_topics columns to roleplay_personas (MySQL)
- Then re-seeds all 8 personas from data/personas.json
Safe to run multiple times (checks before altering).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.database import engine, SessionLocal
from sqlalchemy import text, inspect
from models.roleplay import RoleplayPersona


def run_migration():
    print("\n" + "="*60)
    print("STEP 1: DATABASE MIGRATION")
    print("="*60)

    with engine.connect() as conn:
        inspector = inspect(engine)
        existing = {col["name"] for col in inspector.get_columns("roleplay_personas")}
        print(f"Existing columns: {', '.join(sorted(existing))}")

        added = 0
        if "scenario_brief" not in existing:
            conn.execute(text("ALTER TABLE roleplay_personas ADD COLUMN scenario_brief TEXT"))
            conn.commit()
            print("✅ Added: scenario_brief")
            added += 1
        else:
            print("⏭️  Already exists: scenario_brief")

        if "trigger_topics" not in existing:
            conn.execute(text("ALTER TABLE roleplay_personas ADD COLUMN trigger_topics JSON"))
            conn.commit()
            print("✅ Added: trigger_topics")
            added += 1
        else:
            print("⏭️  Already exists: trigger_topics")

        print(f"Migration done — {added} column(s) added.\n")


def run_seed():
    print("="*60)
    print("STEP 2: SEEDING PERSONAS")
    print("="*60)

    personas_file = Path(__file__).parent / "data" / "personas.json"
    if not personas_file.exists():
        print(f"❌ File not found: {personas_file}")
        return False

    with open(personas_file, 'r') as f:
        personas_data = json.load(f)

    print(f"Loaded {len(personas_data)} personas from JSON")

    db = SessionLocal()
    try:
        existing = db.query(RoleplayPersona).filter_by(is_predefined=True).count()
        if existing > 0:
            print(f"Deleting {existing} existing predefined personas (disabling FK checks)...")
            # Disable FK checks so we can delete personas even if sessions reference them
            db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            db.query(RoleplayPersona).filter_by(is_predefined=True).delete()
            db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            db.commit()

        for pd in personas_data:
            p = RoleplayPersona(
                name=pd["name"],
                description=pd["description"],
                scenario_brief=pd.get("scenario_brief"),
                personality_traits=pd["personality_traits"],
                trigger_topics=pd.get("trigger_topics"),
                common_objections=pd["common_objections"],
                tone=pd["tone"],
                difficulty=pd["difficulty"],
                is_predefined=True,
                created_by=None,
                organization_id=None,
            )
            db.add(p)
            rag = pd["personality_traits"].get("rag_probing_style", "N/A")
            print(f"  + {pd['name']} ({pd['difficulty']}) [RAG: {rag}]")

        db.commit()
        print(f"\n✅ Seeded {len(personas_data)} personas successfully.")
        return True

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
    run_seed()
    print("\n" + "="*60)
    print("ALL DONE — run python check_personas.py to verify")
    print("="*60)
