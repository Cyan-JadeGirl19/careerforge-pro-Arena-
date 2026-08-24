"""Schema-drift regression tests.

Guards against the class of bug where a dev database created before a
schema change crashes the app (create_all does not add columns).
"""
import pathlib

import pytest
from sqlalchemy import create_engine, text


def _old_schema_db(tmp_path: pathlib.Path):
    """A database shaped like an older release (missing new columns)."""
    from app.db import Base
    from app import models  # noqa: F401

    path = tmp_path / "old.db"
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name == "cv_records":
                continue
            table.create(conn, checkfirst=True)
        conn.execute(
            text(
                """CREATE TABLE cv_records (
                    id VARCHAR(36) PRIMARY KEY,
                    profile_id VARCHAR(36) NOT NULL,
                    version INTEGER DEFAULT 1,
                    title VARCHAR(200),
                    text TEXT,
                    source_type VARCHAR(20),
                    created_at DATETIME
                )"""
            )
        )
        conn.execute(
            text(
                "INSERT INTO profiles (id, timezone, work_authority, status, "
                "created_at, updated_at) VALUES "
                "('p1', 'Africa/Johannesburg', 'sa_remote_eligible', 'active', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO cv_records (id, profile_id, title, text, source_type) "
                "VALUES ('c1', 'p1', 'Old CV', 'old content', 'paste')"
            )
        )
    return eng


@pytest.fixture()
def old_engine(tmp_path):
    eng = _old_schema_db(tmp_path)
    yield eng
    eng.dispose()


def test_ensure_schema_adds_missing_column_preserving_data(old_engine):
    from app.db import ensure_schema

    ensure_schema(old_engine)
    with old_engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(cv_records)"))]
        assert "parsed_json" in cols
        row = conn.execute(text("SELECT id, title, text FROM cv_records")).first()
        assert row == ("c1", "Old CV", "old content")


def test_ensure_schema_is_idempotent(old_engine):
    from app.db import ensure_schema

    ensure_schema(old_engine)
    ensure_schema(old_engine)  # second run must not fail
    with old_engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(cv_records)"))]
        assert cols.count("parsed_json") == 1
