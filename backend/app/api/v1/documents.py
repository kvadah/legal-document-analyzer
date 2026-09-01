"""Document API endpoints."""
from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.deps import CurrentUser, get_current_user
from app.db.redis import get_redis
from app.db.session import get_session
from app.pipelines.status import status_channel
from app.repositories.document_repo import DocumentRepository
from app.schemas.document import DocumentListResponse, DocumentOut, UploadResponse
from app.services import document_service
from app.workers.pool import enqueue_ingestion

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_documents(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    files: list[UploadFile] = File(...),
    allow_duplicate: bool = False,
) -> UploadResponse:
    results = await document_service.upload_documents(
        session,
        current_user=current_user,
        files=files,
        allow_duplicate=allow_duplicate,
    )
    return UploadResponse(documents=results)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    search: str | None = None,
) -> DocumentListResponse:
    items, total = await document_service.list_documents(
        session,
        current_user=current_user,
        limit=limit,
        offset=offset,
        status_filter=status,
        search=search,
    )
    return DocumentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentOut:
    return await document_service.get_document(
        session,
        current_user=current_user,
        document_id=document_id,
    )


@router.get("/{document_id}/status/stream")
async def stream_document_status(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventSourceResponse:
    # Org-scoped access check
    await document_service.get_document(session, current_user=current_user, document_id=document_id)

    async def event_generator():
        redis = await get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(status_channel(document_id))
        try:
            repo = DocumentRepository(session, UUID(current_user.org_id))
            doc = await repo.get_by_id(document_id)
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "document_id": str(document_id),
                        "status": doc.status.value,
                        "status_detail": doc.status_detail,
                    }
                ),
            }
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                yield {"event": "status", "data": message["data"]}
        finally:
            await pubsub.unsubscribe(status_channel(document_id))
            await pubsub.aclose()

    return EventSourceResponse(event_generator())


@router.post("/{document_id}/retry", status_code=202)
async def retry_document_processing(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    await document_service.get_document(session, current_user=current_user, document_id=document_id)
    await enqueue_ingestion(str(document_id))
    return {"message": "Ingestion re-enqueued", "document_id": str(document_id)}
