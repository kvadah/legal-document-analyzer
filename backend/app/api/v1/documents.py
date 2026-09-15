"""Document API endpoints."""
from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.deps import CurrentUser, get_current_user, require_role
from app.core.rate_limit import upload_rate_limit
from app.db.redis import get_redis
from app.db.session import get_session
from app.pipelines.status import status_channel
from app.repositories.document_repo import DocumentRepository
from app.schemas.document import (
    DocumentListResponse,
    DocumentOut,
    DocumentTextResponse,
    DocumentVersionListResponse,
    UploadDocumentResult,
    UploadResponse,
)
from app.services import audit_service, document_service
from app.utils.sse import sse_error_guard
from app.workers.pool import enqueue_ingestion

router = APIRouter(prefix="/documents", tags=["documents"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=202,
    dependencies=[Depends(upload_rate_limit())],
)
async def upload_documents(
    current_user: Annotated[CurrentUser, Depends(require_role("reviewer", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    files: list[UploadFile] = File(...),
    allow_duplicate: bool = False,
) -> UploadResponse:
    """Upload is a reviewer-level permission (11-security-compliance.md §2)."""
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


@router.get("/deleted", response_model=DocumentListResponse)
async def list_deleted_documents(
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> DocumentListResponse:
    """Soft-deleted documents (admin trash view) with their purge dates."""
    items, total = await document_service.list_deleted_documents(
        session, current_user=current_user, limit=limit, offset=offset
    )
    return DocumentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentOut:
    return await document_service.get_document(
        session, current_user=current_user, document_id=document_id,
    )


@router.post("/{document_id}/versions", response_model=UploadDocumentResult, status_code=202)
async def upload_document_version(
    document_id: UUID,
    # Version upload is a reviewer-level permission
    # (08-feature-spec-collaboration.md §8).
    current_user: Annotated[CurrentUser, Depends(require_role("reviewer", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    file: UploadFile = File(...),
    change_note: str | None = Form(default=None),
) -> UploadDocumentResult:
    """Upload a new version of an existing document (08 §4)."""
    return await document_service.upload_document_version(
        session,
        current_user=current_user,
        parent_document_id=document_id,
        file=file,
        change_note=change_note,
    )


@router.get("/{document_id}/versions", response_model=DocumentVersionListResponse)
async def list_document_versions(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentVersionListResponse:
    return await document_service.list_document_versions(
        session, current_user=current_user, document_id=document_id,
    )


@router.get("/{document_id}/text", response_model=DocumentTextResponse)
async def get_document_text(
    document_id: UUID,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentTextResponse:
    """Extracted/OCR'd text with page position metadata (09-api-spec.md §2)."""
    result = await document_service.get_document_text(
        session,
        current_user=current_user,
        document_id=document_id,
    )
    await audit_service.record(
        session,
        organization_id=current_user.org_id,
        user_id=current_user.id,
        action=audit_service.AuditAction.DOCUMENT_VIEWED,
        resource_type="document",
        resource_id=document_id,
        ip_address=_client_ip(request),
    )
    await session.commit()
    return result


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

    return EventSourceResponse(sse_error_guard(event_generator()))


@router.post("/{document_id}/retry", status_code=202)
async def retry_document_processing(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_role("reviewer", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    await document_service.get_document(session, current_user=current_user, document_id=document_id)
    await enqueue_ingestion(str(document_id))
    return {"message": "Ingestion re-enqueued", "document_id": str(document_id)}


@router.delete("/{document_id}", response_model=DocumentOut)
async def delete_document(
    document_id: UUID,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_role("reviewer", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentOut:
    """Soft-delete: recoverable by an admin until the retention job purges it
    (11-security-compliance.md §7)."""
    doc = await document_service.soft_delete_document(
        session, current_user=current_user, document_id=document_id
    )
    await audit_service.record(
        session,
        organization_id=current_user.org_id,
        user_id=current_user.id,
        action=audit_service.AuditAction.DOCUMENT_DELETED,
        resource_type="document",
        resource_id=document_id,
        ip_address=_client_ip(request),
        details={"filename": doc.filename},
    )
    await session.commit()
    return doc


@router.post("/{document_id}/restore", response_model=DocumentOut)
async def restore_document(
    document_id: UUID,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentOut:
    """Restore a soft-deleted document within the grace period (admin only)."""
    doc = await document_service.restore_document(
        session, current_user=current_user, document_id=document_id
    )
    await audit_service.record(
        session,
        organization_id=current_user.org_id,
        user_id=current_user.id,
        action=audit_service.AuditAction.DOCUMENT_RESTORED,
        resource_type="document",
        resource_id=document_id,
        ip_address=_client_ip(request),
        details={"filename": doc.filename},
    )
    await session.commit()
    return doc
