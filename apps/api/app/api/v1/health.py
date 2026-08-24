"""Health endpoint for uptime monitors and release validation."""
from fastapi import APIRouter
from sqlalchemy import text

from ...config import APP_VERSION, get_settings
from ...db import engine
from ...schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    settings = get_settings()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_state = "up"
    except Exception:
        db_state = "down"
    return HealthOut(
        version=APP_VERSION, environment=settings.environment, database=db_state
    )
