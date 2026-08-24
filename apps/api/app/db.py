"""Database engine and session management."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

_settings = get_settings()

if _settings.database_url.startswith("sqlite"):
    _engine_kwargs: dict = {"connect_args": {"check_same_thread": False}}
else:
    # Fail fast (10s) when the DB is unreachable - also keeps the health
    # endpoint from hanging on a dead database.
    _engine_kwargs = {"pool_pre_ping": True, "connect_args": {"connect_timeout": 10}}
engine = create_engine(_settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables for dev/test, then apply safe additive migrations.

    ``create_all`` creates missing tables but never adds columns to
    existing ones, so a dev database created before a schema change
    would crash the app. ``ensure_schema`` closes that gap by adding
    any missing (nullable) columns — non-destructive, preserves data.
    Production will use a proper migration tool (Alembic) before launch.
    """
    from . import models  # noqa: F401  (registers mappers)

    Base.metadata.create_all(engine)
    ensure_schema()


def ensure_schema(target_engine=None) -> None:
    """Add any columns missing from existing tables (SQLite/Postgres).

    Only additive ``ADD COLUMN`` statements are used, and only for
    columns declared nullable or with a default, so existing rows are
    never altered or lost.
    """
    from sqlalchemy import inspect, text

    target_engine = target_engine or engine
    inspector = inspect(target_engine)
    is_sqlite = target_engine.dialect.name == "sqlite"
    with target_engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                if not col.nullable and col.default is None:
                    # Never add a NOT NULL column without a default.
                    continue
                col_type = col.type.compile(target_engine.dialect)
                if is_sqlite:
                    conn.execute(
                        text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type} NULL')
                    )
                else:
                    conn.execute(
                        text(
                            f'ALTER TABLE "{table.name}" ADD COLUMN IF NOT EXISTS '
                            f'"{col.name}" {col_type} NULL'
                        )
                    )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
