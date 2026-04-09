"""
Idempotent migration: add target_channels + publish_log to marketing_posts.

Safe to run multiple times — checks for column existence before adding.
Run with:  python migrate_marketing_channels.py
"""
import sys
import compat_patch  # noqa
from sqlalchemy import text
from utils.database import engine, SessionLocal


def column_exists(conn, table: str, column: str) -> bool:
    """Check if a column exists on a table (works for MySQL + SQLite)."""
    dialect = engine.dialect.name
    if dialect == "mysql":
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ), {"t": table, "c": column})
        return result.scalar() > 0
    elif dialect == "sqlite":
        result = conn.execute(text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in result)
    else:
        raise RuntimeError(f"Unsupported dialect: {dialect}")


def add_column(conn, table: str, column: str, ddl: str):
    if column_exists(conn, table, column):
        print(f"  ⊘ {table}.{column} already exists — skipping")
        return False
    print(f"  + Adding {table}.{column} ...")
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    return True


def main():
    print("=" * 60)
    print("MIGRATION: marketing_posts publishing channels")
    print("=" * 60)

    with engine.begin() as conn:
        added = 0
        if add_column(conn, "marketing_posts", "target_channels", "JSON NULL"):
            added += 1
        if add_column(conn, "marketing_posts", "publish_log", "JSON NULL"):
            added += 1
        print(f"\n  {'✓' if added else '⊘'} {added} column(s) added")

    print("\nDone.")


if __name__ == "__main__":
    main()
