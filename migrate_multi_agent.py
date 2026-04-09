"""
Migration: Add multi-agent columns to roleplay tables.
Adds:
  - roleplay_sessions.agent_cache (JSON)
  - roleplay_messages.stage_snapshot (JSON)

Uses information_schema to check if columns already exist (MySQL-compatible).
"""
from sqlalchemy import text
from utils.database import engine


COLUMNS_TO_ADD = [
    {
        "table": "roleplay_sessions",
        "column": "agent_cache",
        "sql": "ALTER TABLE roleplay_sessions ADD COLUMN agent_cache JSON DEFAULT NULL",
    },
    {
        "table": "roleplay_messages",
        "column": "stage_snapshot",
        "sql": "ALTER TABLE roleplay_messages ADD COLUMN stage_snapshot JSON DEFAULT NULL",
    },
]


def column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() "
        "AND TABLE_NAME = :table AND COLUMN_NAME = :column"
    ), {"table": table, "column": column})
    return result.scalar() > 0


def run():
    print("🔄 Running multi-agent migration...")
    with engine.connect() as conn:
        for item in COLUMNS_TO_ADD:
            if column_exists(conn, item["table"], item["column"]):
                print(f"  ⏭️  {item['table']}.{item['column']} already exists, skipping")
            else:
                conn.execute(text(item["sql"]))
                conn.commit()
                print(f"  ✅ Added {item['table']}.{item['column']}")
    print("✅ Multi-agent migration complete!")


if __name__ == "__main__":
    run()
