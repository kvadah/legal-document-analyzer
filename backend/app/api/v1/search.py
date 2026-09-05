"""Search & RAG Q&A API endpoints (09-api-spec.md §4)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.deps import CurrentUser, get_current_user
from app.db.session import get_session
from app.schemas.search import AskRequest, SearchRequest, SearchResponse
from app.services import qa_service, search_service
from app.services.document_service import get_document

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SearchResponse:
    return await search_service.search(session, current_user=current_user, request=body)


@router.post("/documents/{document_id}/ask")
async def ask_document(
    document_id: UUID,
    body: AskRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventSourceResponse:
    """Single-document grounded RAG Q&A, streamed over SSE."""
    # Pre-check access/status before streaming starts so org-scoping and
    # not-ready errors surface as proper 4xx JSON instead of a broken stream.
    doc = await get_document(session, current_user=current_user, document_id=document_id)
    await qa_service.verify_askable(doc.status)

    generator = qa_service.ask(
        session,
        current_user=current_user,
        document_id=document_id,
        question=body.question,
        conversation_id=body.conversation_id,
    )
    return EventSourceResponse(generator)
