"""Main FastAPI application factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1 import v1_router
from app.core.config import settings
from app.db.qdrant_init import init_qdrant
from app.db.redis import close_redis
from app.db.session import close_db, init_db
from app.services.storage_service import get_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    await init_db()
    await get_storage().ensure_bucket()
    init_qdrant()
    yield
    # Shutdown
    await close_db()
    await close_redis()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    # CORS middleware
    # allow_credentials=True is required for httpOnly cookie auth.
    # In production, replace "*" with the frontend origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(health_router)
    app.include_router(v1_router)

    return app


app = create_app()
