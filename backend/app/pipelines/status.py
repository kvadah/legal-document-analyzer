"""Document status transitions and Redis pub/sub events."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.models.models import DocumentStatus
from app.repositories.document_repo import DocumentRepository


def status_channel(document_id: str | UUID) -> str:
    return f"doc_status:{document_id}"


async def publish_document_status(
    document_id: str | UUID,
    status: DocumentStatus | str,
    *,
    status_detail: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "document_id": str(document_id),
        "status": status.value if isinstance(status, DocumentStatus) else status,
        "status_detail": status_detail,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    redis = await get_redis()
    await redis.publish(status_channel(document_id), json.dumps(payload))


async def transition_document_status(
    session: AsyncSession,
    *,
    organization_id: UUID,
    document_id: UUID,
    status: DocumentStatus,
    status_detail: str | None = None,
    page_count: int | None = None,
    language: str | None = None,
    document_type: str | None = None,
    ocr_text_storage_path: str | None = None,
) -> None:
    repo = DocumentRepository(session, organization_id)
    await repo.update_status(
        document_id,
        status,
        status_detail=status_detail,
        page_count=page_count,
        language=language,
        document_type=document_type,
        ocr_text_storage_path=ocr_text_storage_path,
    )
    await session.commit()
    await publish_document_status(document_id, status, status_detail=status_detail)
