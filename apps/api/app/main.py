"""CareerForge Pro API entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8001
Interactive docs: http://localhost:8001/docs
"""
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.v1 import (
    consents,
    cvs,
    documents,
    followups,
    gmail,
    health,
    interview,
    jobs,
    portfolio,
    profiles,
    recruiters,
    references,
    skills,
    studio,
)
from .config import APP_VERSION, get_settings
from .db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Normal case: schema is ready immediately. If the DB is unreachable at
    # startup (first deploy, DB lagging the service), keep the app up and
    # retry in the background - the health endpoint reports DB state.
    def _post_init() -> None:
        """Classify any pre-existing jobs' language (idempotent)."""
        try:
            from .db import SessionLocal
            from .jobs import service as jobs_service

            with SessionLocal() as db:
                jobs_service.backfill_languages(db)
        except Exception:
            pass  # non-fatal; the next sync will retry

    try:
        init_db()
        _post_init()
    except Exception:
        def _init_with_retry() -> None:
            for attempt in range(20):
                try:
                    init_db()
                    _post_init()
                    return
                except Exception:
                    time.sleep(min(30, 2 * (attempt + 1)))

        threading.Thread(target=_init_with_retry, daemon=True).start()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CareerForge Pro API",
        description="CV-first career acceleration for South African remote work. "
        "Human-supervised: sensitive actions require explicit consent.",
        version=APP_VERSION,
        lifespan=lifespan,
    )
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("careerforge")

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        # Full traceback goes to the service logs (Render > Logs); the
        # client gets a short, actionable message instead of a bare 500.
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Server error ({type(exc).__name__}): {str(exc)[:160]}",
                }
            },
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api = APIRouter(prefix="/api/v1")
    api.include_router(health.router)
    api.include_router(profiles.router)
    api.include_router(consents.router)
    api.include_router(cvs.router)
    api.include_router(documents.router)
    api.include_router(studio.router)
    api.include_router(gmail.router)
    api.include_router(jobs.router)
    api.include_router(recruiters.router)
    api.include_router(references.router)
    api.include_router(followups.router)
    api.include_router(interview.router)
    api.include_router(skills.router)
    api.include_router(portfolio.router)
    app.include_router(api)
    return app


app = create_app()
