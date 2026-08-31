"""FastAPI application factory for SIH 26189 backend."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router, startup
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Criminal Network Analysis API",
        version="1.0.0",
        description=(
            "Investigator-assistance API for entity extraction, relationship "
            "extraction, entity resolution, and network analysis. "
            "This system does not determine guilt or assign criminal labels."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
    allow_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
    # Do not use wildcard with credentials — resolve to explicit origins
    if "*" in allow_origins and len(allow_origins) == 1:
        allow_origins = ["http://localhost:3000", "http://localhost:8000", "http://localhost:8001"]
    # Support Vercel deployments: allow any *.vercel.app via regex if no explicit wildcard handling
    # If CORS_ORIGINS contains vercel.app placeholder, regex will cover preview deployments.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    try:
        from app.ai_router import router as ai_router

        app.include_router(ai_router)
    except Exception:
        pass  # AI routes optional if module missing

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level,
    )