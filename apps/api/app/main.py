"""CareerForge Pro API entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8001
Interactive docs: http://localhost:8001/docs
"""
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import consents, cvs, documents, health, profiles, studio
from .config import APP_VERSION, get_settings
from .db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
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
    app.include_router(api)
    return app


app = create_app()
