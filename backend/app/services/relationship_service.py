"""Document relationship business logic (08-feature-spec-collaboration.md §2).

Relationship semantics: document_id_a is the subject — "A is an amendment of
B", "A supersedes B", "A is an exhibit to B"; related_agreement is the
symmetric fallback.

System-inferred relationships are created with created_by=null and surface as
suggestions requiring user confirmation — they are never auto-confirmed.
"""
from __future__ import annotations

import logging
import re
import uuid
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models.models import (
    Chunk,
    Document,
    DocumentRelationship,
    RelationshipType,
)
from app.repositories.document_repo import DocumentRepository
from app.repositories.relationship_repo import RelationshipRepository
from app.schemas.relationship import (
    RelatedDocumentOut,
    RelationshipCreateRequest,
    RelationshipListResponse,
)

logger = logging.getLogger(__name__)

_MAX_SUGGESTIONS_PER_PASS = 5
_MIN_TITLE_LENGTH = 3


def _normalize_title(filename: str) -> str:
    """Filename → matchable title: strip extension, unify separators."""
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    stem = re.sub(r"[_\-]+", " ", stem).strip()
    return stem


def _word_boundaries(text: str, phrase: str) -> bool:
    """Case-insensitive phrase match on word boundaries."""
    if not phrase:
        return False
    pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE)
    return pattern.search(text) is not None


def _looks_like_amendment(doc: Document) -> bool:
    return "amendment" in doc.filename.lower() or "amendment" in (doc.storage_path or "").lower()


async def create_relationship(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    document_id: UUID,
    request: RelationshipCreateRequest,
) -> RelatedDocumentOut:
    org_id = UUID(current_user.org_id)
    doc_repo = DocumentRepository(session, org_id)
    source = await doc_repo.get_by_id(document_id)
    try:
        related_id = UUID(request.related_document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "message": "Invalid document id"},
        ) from None
    if related_id == document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "message": "A document cannot be related to itself",
            },
        )
    related = await doc_repo.get_by_id(related_id)

    repo = RelationshipRepository(session, org_id)
    existing = await repo.find_any_between(document_id, related_id)
    if any(rel.created_by is not None for rel in existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "relationship_exists",
                "message": "These documents are already linked",
            },
        )
    # An explicit user-created link supersedes any unconfirmed suggestion
    # between the same pair.
    for suggestion in existing:
        if suggestion.created_by is None:
            await repo.delete(suggestion)

    relationship = await repo.save(
        DocumentRelationship(
            id=uuid.uuid4(),
            document_id_a=document_id,
            document_id_b=related_id,
            relationship_type=RelationshipType(request.relationship_type),
            created_by=UUID(current_user.id),
        )
    )
    await session.commit()
    return _to_out(relationship, source=source, other=related)


async def list_relationships(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    document_id: UUID,
) -> RelationshipListResponse:
    org_id = UUID(current_user.org_id)
    doc_repo = DocumentRepository(session, org_id)
    doc = await doc_repo.get_by_id(document_id)

    repo = RelationshipRepository(session, org_id)
    relationships = await repo.list_for_document(document_id)

    other_ids = {
        rel.document_id_b if rel.document_id_a == document_id else rel.document_id_a
        for rel in relationships
    }
    others: dict[UUID, Document] = {}
    if other_ids:
        stmt = select(Document).where(
            Document.id.in_(other_ids), Document.organization_id == org_id
        )
        others = {d.id: d for d in (await session.execute(stmt)).scalars().all()}

    entries = [
        _to_out(rel, source=doc, other=others[_other_id(rel, document_id)])
        for rel in relationships
        if _other_id(rel, document_id) in others
    ]
    entries.sort(key=lambda e: (e.suggested, e.created_at))
    return RelationshipListResponse(document_id=str(document_id), relationships=entries)


async def confirm_relationship(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    relationship_id: UUID,
) -> None:
    repo = RelationshipRepository(session, UUID(current_user.org_id))
    rel = await repo.get_by_id(relationship_id)
    if rel is None:
        raise _not_found()
    if rel.created_by is None:
        rel.created_by = UUID(current_user.id)
        await session.commit()


async def delete_relationship(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    relationship_id: UUID,
) -> None:
    repo = RelationshipRepository(session, UUID(current_user.org_id))
    rel = await repo.get_by_id(relationship_id)
    if rel is None:
        raise _not_found()
    await repo.delete(rel)
    await session.commit()


def _other_id(rel: DocumentRelationship, document_id: UUID) -> UUID:
    return rel.document_id_b if rel.document_id_a == document_id else rel.document_id_a


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": "Relationship not found"},
    )


def _to_out(
    rel: DocumentRelationship, *, source: Document, other: Document
) -> RelatedDocumentOut:
    return RelatedDocumentOut(
        relationship_id=str(rel.id),
        direction="outgoing" if rel.document_id_a == source.id else "incoming",
        relationship_type=rel.relationship_type.value,
        other_document_id=str(other.id),
        other_filename=other.filename,
        other_document_type=other.document_type.value,
        other_status=other.status.value,
        suggested=rel.created_by is None,
        created_at=rel.created_at,
    )


async def infer_relationship_suggestions(session: AsyncSession, doc: Document) -> int:
    """Best-effort system-inferred relationship suggestions (08 §2).

    Matches other org documents' titles against this document's text (and
    this document's title against other documents' chunks). Every match
    becomes an unconfirmed suggestion (created_by=null) — never a silent
    link. Returns the number of suggestions created.

    Callers must keep this failure-tolerant: inference must never break the
    AI pipeline.
    """
    try:
        return await _infer(session, doc)
    except Exception:
        logger.warning("relationships.inference_failed", exc_info=True)
        return 0


async def _infer(session: AsyncSession, doc: Document) -> int:
    org_id = doc.organization_id
    root_id = doc.parent_document_id or doc.id

    others = (
        (
            await session.execute(
                select(Document).where(
                    Document.organization_id == org_id,
                    Document.id != doc.id,
                    Document.parent_document_id.is_(None)
                    | (Document.parent_document_id != root_id),
                )
            )
        )
        .scalars()
        .all()
    )
    others = [d for d in others if d.id != root_id]
    if not others:
        return 0

    doc_chunks = (
        await session.execute(select(Chunk).where(Chunk.document_id == doc.id))
    ).scalars().all()
    doc_text = "\n".join(chunk.text or "" for chunk in doc_chunks)

    repo = RelationshipRepository(session, org_id)
    created = 0
    for other in others:
        if created >= _MAX_SUGGESTIONS_PER_PASS:
            break
        if await repo.find_any_between(doc.id, other.id):
            continue

        other_title = _normalize_title(other.filename)
        forward = len(other_title) >= _MIN_TITLE_LENGTH and _word_boundaries(
            doc_text, other_title
        )
        if not forward:
            continue

        rel_type = (
            RelationshipType.AMENDMENT
            if _looks_like_amendment(doc)
            else RelationshipType.RELATED_AGREEMENT
        )
        session.add(
            DocumentRelationship(
                id=uuid.uuid4(),
                document_id_a=doc.id,
                document_id_b=other.id,
                relationship_type=rel_type,
                created_by=None,
            )
        )
        created += 1

    if created:
        await session.commit()
    return created
