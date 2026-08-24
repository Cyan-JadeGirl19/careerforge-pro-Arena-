"""Database engine and session management."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

_settings = get_settings()

_connect_args = (
    {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(_settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables for dev/test. Production should use migrations."""
    from . import models  # noqa: F401  (registers mappers)

    Base.metadata.create_all(engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
