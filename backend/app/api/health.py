"""Health check endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    service: str
    database: str | None = None
    details: dict | None = None


@router.get("/live", response_model=HealthResponse)
async def health_live() -> HealthResponse:
    """Liveness check - indicates the service is running."""
    return HealthResponse(
        status="healthy",
        service="legal-doc-analyzer-api",
    )


@router.get("/ready", response_model=HealthResponse)
async def health_ready(session: AsyncSession = Depends(get_session)) -> HealthResponse:
    """Readiness check - indicates the service is ready to handle requests."""
    try:
        # Test database connection
        from sqlalchemy import text
        await session.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception as e:
        database_status = f"error: {str(e)}"

    return HealthResponse(
        status="ready" if database_status == "connected" else "not_ready",
        service="legal-doc-analyzer-api",
        database=database_status,
    )
