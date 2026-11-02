"""Migrations run against temporary SQLite files, never the dev DB.
PostgreSQL is not covered by these tests."""
from sqlalchemy import create_engine, inspect, text

from app.database import Base
from app.migrations import ADDED_COLUMNS, run_migrations

# Schema of the dev DB before the vision columns (copied from the
# committed crowdsense.db at 91e2981).
OLD_SCHEMA = [
    """CREATE TABLE users (id UUID NOT NULL, email VARCHAR NOT NULL,
        hashed_password VARCHAR NOT NULL, role VARCHAR(8) NOT NULL,
        created_at DATETIME, PRIMARY KEY (id))""",
    """CREATE TABLE incidents (id UUID NOT NULL, disaster_type VARCHAR,
        centroid GEOMETRY, confidence FLOAT, severity FLOAT, has_contradiction BOOLEAN,
        status VARCHAR(11), verified_by_id UUID, created_at DATETIME, updated_at DATETIME,
        PRIMARY KEY (id), FOREIGN KEY(verified_by_id) REFERENCES users (id))""",
    """CREATE TABLE reports (id UUID NOT NULL, reporter_id UUID, text TEXT,
        media_url VARCHAR, source VARCHAR, location GEOMETRY, reported_at DATETIME,
        disaster_type VARCHAR, sentiment VARCHAR, embedding VARCHAR,
        source_reliability FLOAT, incident_id UUID, PRIMARY KEY (id),
        FOREIGN KEY(reporter_id) REFERENCES users (id),
        FOREIGN KEY(incident_id) REFERENCES incidents (id))""",
    "INSERT INTO reports (id, text, source) VALUES ('r1', 'old report', 'citizen')",
]

ALL_ADDED = {f"{t}.{c}" for t, cols in ADDED_COLUMNS.items() for c, _ in cols}


def _columns(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def test_old_schema_gets_new_columns_and_keeps_data(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        for stmt in OLD_SCHEMA:
            conn.execute(text(stmt))

    assert set(run_migrations(engine)) == ALL_ADDED
    for table, cols in ADDED_COLUMNS.items():
        assert {c for c, _ in cols} <= _columns(engine, table)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT text, image_model FROM reports WHERE id = 'r1'")).one()
    assert row == ("old report", None)


def test_migration_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        for stmt in OLD_SCHEMA:
            conn.execute(text(stmt))
    run_migrations(engine)
    assert run_migrations(engine) == []


def test_fresh_database_needs_no_migration(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    Base.metadata.create_all(bind=engine)
    assert run_migrations(engine) == []


def test_models_and_migration_list_agree():
    """Every column in ADDED_COLUMNS exists on the ORM model, so fresh and
    migrated databases end up with the same columns."""
    for table, cols in ADDED_COLUMNS.items():
        model_cols = set(Base.metadata.tables[table].columns.keys())
        assert {c for c, _ in cols} <= model_cols
