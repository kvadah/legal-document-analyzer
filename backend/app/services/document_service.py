"""Document upload and query business logic."""
from __future__ import annotations

import hashlib
import mimetypes
import uuid
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser
from app.models.models import Document, DocumentStatus, DocumentVersion
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.document_repo import DocumentRepository
from app.schemas.document import (
    DocumentOut,
    DocumentPage,
    DocumentTextResponse,
    DocumentVersionListResponse,
    DocumentVersionOut,
    PageBlock,
    UploadDocumentResult,
)
from app.services.storage_service import build_document_storage_key, get_storage
from app.workers.pool import enqueue_ingestion

# Statuses at which chunked text exists and is queryable.
TEXT_READY_STATUSES = {
    DocumentStatus.INGESTION_READY,
    DocumentStatus.AI_PIPELINE_PROCESSING,
    DocumentStatus.ANALYSIS_READY,
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".rtf"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "application/rtf",
    "text/rtf",
}


def _document_to_out(doc: Document, *, possible_duplicate_of: str | None = None) -> DocumentOut:
    return DocumentOut(
        id=str(doc.id),
        filename=doc.filename,
        file_type=doc.file_type,
        file_size_bytes=doc.file_size_bytes,
        document_type=doc.document_type.value,
        status=doc.status.value,
        status_detail=doc.status_detail,
        page_count=doc.page_count,
        language=doc.language,
        file_hash=doc.file_hash,
        possible_duplicate_of=possible_duplicate_of,
        contract_score=(
            float(doc.contract_score) if doc.contract_score is not None else None
        ),
        ai_confidence_score=(
            float(doc.ai_confidence_score) if doc.ai_confidence_score is not None else None
        ),
        parent_document_id=str(doc.parent_document_id) if doc.parent_document_id else None,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _validate_upload(filename: str, content_type: str | None, size: int) -> str:
    if size > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "validation_error",
                "message": f"File exceeds maximum size of {settings.max_upload_mb}MB",
            },
        )

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "message": "Unsupported file type. Allowed: PDF, DOCX, DOC, TXT, RTF",
            },
        )

    guessed = content_type or mimetypes.guess_type(filename)[0]
    if guessed and guessed not in ALLOWED_MIME_TYPES and not guessed.startswith("text/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "message": f"Unsupported MIME type: {guessed}"},
        )
    return ext.lstrip(".")


def _scan_content(data: bytes, ext: str) -> None:
    """Basic content validation (magic-byte sniffing when available)."""
    try:
        import magic

        detected = magic.from_buffer(data, mime=True)
        if detected and detected not in ALLOWED_MIME_TYPES and not detected.startswith("text/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "validation_error", "message": "File content does not match allowed types"},
            )
    except ImportError:
        if ext == "pdf" and not data.startswith(b"%PDF"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "validation_error", "message": "Invalid PDF file"},
            )


async def upload_documents(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    files: list[UploadFile],
    allow_duplicate: bool = False,
) -> list[UploadDocumentResult]:
    org_id = UUID(current_user.org_id)
    user_id = UUID(current_user.id)
    repo = DocumentRepository(session, org_id)
    storage = get_storage()
    results: list[UploadDocumentResult] = []

    for upload in files:
        data = await upload.read()
        filename = upload.filename or "upload.bin"
        file_type = _validate_upload(filename, upload.content_type, len(data))
        _scan_content(data, file_type)

        file_hash = hashlib.sha256(data).hexdigest()
        duplicate = await repo.find_by_hash(file_hash)
        if duplicate and not allow_duplicate:
            results.append(
                UploadDocumentResult(
                    document_id=str(duplicate.id),
                    filename=filename,
                    status=duplicate.status.value,
                    possible_duplicate_of=str(duplicate.id),
                )
            )
            continue

        document_id = uuid.uuid4()
        storage_key = build_document_storage_key(
            current_user.org_id,
            str(document_id),
            f"original.{file_type}",
        )
        await storage.put_bytes(storage_key, data, upload.content_type or "application/octet-stream")

        doc = await repo.create_document(
            uploaded_by=user_id,
            filename=filename,
            file_type=file_type,
            file_size_bytes=len(data),
            storage_path=storage_key,
            file_hash=file_hash,
            document_id=document_id,
        )

        await session.commit()
        await enqueue_ingestion(str(doc.id))
        results.append(
            UploadDocumentResult(
                document_id=str(doc.id),
                filename=filename,
                status=doc.status.value,
            )
        )
    return results


async def get_document(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    document_id: UUID,
) -> DocumentOut:
    repo = DocumentRepository(session, UUID(current_user.org_id))
    doc = await repo.get_by_id(document_id)
    return _document_to_out(doc)


def _root_of(doc: Document) -> UUID:
    """Root of a version chain: the doc itself, or its linked root."""
    return doc.parent_document_id or doc.id


async def _chain_documents(
    session: AsyncSession, org_id: UUID, root_id: UUID
) -> list[Document]:
    stmt = select(Document).where(
        Document.organization_id == org_id,
        (Document.id == root_id) | (Document.parent_document_id == root_id),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _version_rows(
    session: AsyncSession, document_ids: list[UUID]
) -> dict[UUID, DocumentVersion]:
    if not document_ids:
        return {}
    stmt = select(DocumentVersion).where(DocumentVersion.document_id.in_(document_ids))
    result = await session.execute(stmt)
    return {row.document_id: row for row in result.scalars().all()}


async def upload_document_version(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    parent_document_id: UUID,
    file: UploadFile,
    change_note: str | None = None,
) -> UploadDocumentResult:
    """Upload a new version of an existing document (08 §4).

    The new version is a distinct Document (own pipeline run and analysis)
    linked to the chain's root via parent_document_id; prior versions are
    never overwritten. The content-dedup check is intentionally skipped —
    the user has explicitly declared this a new version.
    """
    org_id = UUID(current_user.org_id)
    user_id = UUID(current_user.id)
    repo = DocumentRepository(session, org_id)
    parent = await repo.get_by_id(parent_document_id)
    root_id = _root_of(parent)

    data = await file.read()
    filename = file.filename or "upload.bin"
    file_type = _validate_upload(filename, file.content_type, len(data))
    _scan_content(data, file_type)

    chain = await _chain_documents(session, org_id, root_id)
    rows = await _version_rows(session, [doc.id for doc in chain])
    if root_id not in rows:
        root_doc = next(doc for doc in chain if doc.id == root_id)
        session.add(
            DocumentVersion(
                id=uuid.uuid4(),
                document_id=root_id,
                version_number=1,
                storage_path=root_doc.storage_path,
                uploaded_by=root_doc.uploaded_by,
                change_note=None,
            )
        )
    # The root counts as v1 even when its row was only just synthesized.
    next_number = 1 + max([row.version_number for row in rows.values()] + [1])

    document_id = uuid.uuid4()
    storage_key = build_document_storage_key(
        current_user.org_id, str(document_id), f"original.{file_type}"
    )
    await get_storage().put_bytes(
        storage_key, data, file.content_type or "application/octet-stream"
    )

    doc = await repo.create_document(
        uploaded_by=user_id,
        filename=filename,
        file_type=file_type,
        file_size_bytes=len(data),
        storage_path=storage_key,
        file_hash=hashlib.sha256(data).hexdigest(),
        document_id=document_id,
    )
    doc.parent_document_id = root_id

    session.add(
        DocumentVersion(
            id=uuid.uuid4(),
            document_id=doc.id,
            version_number=next_number,
            storage_path=storage_key,
            uploaded_by=user_id,
            change_note=change_note,
        )
    )
    await session.commit()
    await enqueue_ingestion(str(doc.id))
    return UploadDocumentResult(
        document_id=str(doc.id),
        filename=filename,
        status=doc.status.value,
    )


async def list_document_versions(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    document_id: UUID,
) -> DocumentVersionListResponse:
    repo = DocumentRepository(session, UUID(current_user.org_id))
    doc = await repo.get_by_id(document_id)
    root_id = _root_of(doc)

    chain = await _chain_documents(session, UUID(current_user.org_id), root_id)
    rows = await _version_rows(session, [d.id for d in chain])
    known_numbers = [row.version_number for row in rows.values()]
    fallback_number = max(known_numbers) + 1 if known_numbers else 1

    versions = []
    for chain_doc in chain:
        row = rows.get(chain_doc.id)
        if row is not None:
            number = row.version_number
            change_note = row.change_note
        elif chain_doc.id == root_id:
            number, change_note = 1, None
        else:
            number, change_note = fallback_number, None
        versions.append(
            DocumentVersionOut(
                document_id=str(chain_doc.id),
                version_number=number,
                filename=chain_doc.filename,
                status=chain_doc.status.value,
                document_type=chain_doc.document_type.value,
                change_note=change_note,
                created_at=chain_doc.created_at,
                is_current=chain_doc.id == document_id,
            )
        )
    versions.sort(key=lambda v: (v.version_number, v.created_at))
    return DocumentVersionListResponse(
        document_id=str(document_id),
        root_document_id=str(root_id),
        versions=versions,
    )


async def get_document_text(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    document_id: UUID,
) -> DocumentTextResponse:
    doc_out = await get_document(session, current_user=current_user, document_id=document_id)
    if DocumentStatus(doc_out.status) not in TEXT_READY_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_not_ready",
                "message": (
                    "Document text is not available yet "
                    f"(status: {doc_out.status})."
                ),
            },
        )

    chunks = await ChunkRepository(session).list_for_document(document_id)
    pages: dict[int, list[PageBlock]] = {}
    for chunk in chunks:
        pages.setdefault(chunk.page_number, []).append(
            PageBlock(
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                section_heading=chunk.section_heading,
            )
        )
    return DocumentTextResponse(
        document_id=str(document_id),
        page_count=doc_out.page_count or (max(pages) if pages else 0),
        pages=[
            DocumentPage(page_number=page_number, blocks=blocks)
            for page_number, blocks in sorted(pages.items())
        ],
    )


async def list_documents(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
    search: str | None = None,
) -> tuple[list[DocumentOut], int]:

    repo = DocumentRepository(session, UUID(current_user.org_id))
    filters = []
    if status_filter:
        from app.models.models import DocumentStatus

        filters.append(Document.status == DocumentStatus(status_filter))
    if search:
        filters.append(Document.filename.ilike(f"%{search}%"))

    items, total = await repo.list(limit=limit, offset=offset, extra_filters=filters)
    return [_document_to_out(doc) for doc in items], total
