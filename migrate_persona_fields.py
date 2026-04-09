"""
Migration: Add scenario_brief and trigger_topics columns to roleplay_personas table.
Uses sqlite3 directly — no sqlalchemy dependency needed.
Safe to run multiple times.
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "sales_training.db"
DB_PATH_ALT = Path(__file__).parent / "training_platform.db"

def migrate(db_path):
    if not db_path.exists():
        print(f"⏭️  DB not found: {db_path}")
        return

    print(f"\n📁 Migrating: {db_path.name}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if roleplay_personas table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='roleplay_personas'")
    if not cursor.fetchone():
        print("   ⏭️  Table roleplay_personas not found — skipping.")
        conn.close()
        return

    # Get existing columns
    cursor.execute("PRAGMA table_info(roleplay_personas)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    print(f"   Existing columns: {', '.join(sorted(existing_columns))}")

    added = 0
    if "scenario_brief" not in existing_columns:
        cursor.execute("ALTER TABLE roleplay_personas ADD COLUMN scenario_brief TEXT")
        print("   ✅ Added: scenario_brief")
        added += 1
    else:
        print("   ⏭️  scenario_brief already exists")

    if "trigger_topics" not in existing_columns:
        cursor.execute("ALTER TABLE roleplay_personas ADD COLUMN trigger_topics JSON")
        print("   ✅ Added: trigger_topics")
        added += 1
    else:
        print("   ⏭️  trigger_topics already exists")

    conn.commit()
    conn.close()
    print(f"   ✅ Done — {added} column(s) added.")

if __name__ == "__main__":
    print("="*60)
    print("MIGRATION: Add persona columns")
    print("="*60)
    migrate(DB_PATH)
    migrate(DB_PATH_ALT)
    print("\n✅ All migrations complete.")
