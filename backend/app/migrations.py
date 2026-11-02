"""
Idempotent schema migrations (no Alembic yet).

`Base.metadata.create_all` creates missing tables but never alters existing
ones, so columns added to models.py after a database was created must be
added here as well. Each column is added only if it is missing, using plain
`ALTER TABLE ... ADD COLUMN`, which works on SQLite and PostgreSQL (no
`IF NOT EXISTS`, which SQLite does not support).

Runs automatically at app startup; can also be run by hand:

    python -m app.migrations
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("crowdsense.migrations")

# table -> [(column, SQL type)]; keep in sync with models.py
ADDED_COLUMNS: Dict[str, List[Tuple[str, str]]] = {
    "reports": [
        ("image_model", "VARCHAR"),
        ("image_label", "VARCHAR"),
        ("image_scores", "TEXT"),
        ("image_embedding", "TEXT"),
        ("image_text_consistency", "FLOAT"),
        ("image_conflict", "BOOLEAN"),
        ("image_phash", "VARCHAR"),
        ("image_duplicate_of", "VARCHAR"),
    ],
    "incidents": [
        ("fusion_explanation", "TEXT"),
    ],
}


def run_migrations(engine: Engine) -> List[str]:
    """Add any missing columns. Returns the "table.column" names added."""
    inspector = inspect(engine)
    added: List[str] = []
    with engine.begin() as conn:
        for table, columns in ADDED_COLUMNS.items():
            if not inspector.has_table(table):
                continue  # create_all builds it with every column
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, sql_type in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))
                    added.append(f"{table}.{name}")
    if added:
        logger.info("Migrations added columns: %s", ", ".join(added))
    return added


if __name__ == "__main__":
    from app.database import engine

    result = run_migrations(engine)
    print("added: " + (", ".join(result) if result else "nothing (schema up to date)"))
