"""Environment configuration with validation.

Settings are read from environment variables prefixed with ``CF_``
(e.g. ``CF_DATABASE_URL``) or a local ``.env`` file. Production
environments must point at PostgreSQL; development and tests may use
SQLite for zero-setup local runs.
"""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.2.0"

ALLOWED_ENVIRONMENTS = {"development", "staging", "production", "test"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CF_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./careerforge.db"
    cors_origins: list[str] = ["http://localhost:3000"]
    debug: bool = True
    # Job sources are feature-flagged; a broken source can be disabled
    # without taking the app down. (Comma-separated list.)
    job_sources: list[str] = ["wwr", "remoteok", "remotive"]
    job_sync_ttl_hours: int = 6
    # Adzuna (optional) - the candidate's own free API key, best for SA listings.
    adzuna_app_id: str | None = None
    adzuna_api_key: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        if self.environment not in ALLOWED_ENVIRONMENTS:
            raise ValueError(
                f"CF_ENVIRONMENT must be one of {sorted(ALLOWED_ENVIRONMENTS)}"
            )
        if self.environment in {"production", "staging"} and not self.database_url.startswith(
            ("postgres://", "postgresql://", "postgresql+psycopg://")
        ):
            raise ValueError(
                "CF_DATABASE_URL must point at PostgreSQL in staging/production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
