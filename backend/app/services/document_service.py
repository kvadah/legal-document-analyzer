"""Document upload and query business logic."""
from __future__ import annotations

import hashlib
import mimetypes
import uuid
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser
from app.models.models import Document
from app.repositories.document_repo import DocumentRepository
from app.schemas.document import DocumentOut, UploadDocumentResult
from app.services.storage_service import build_document_storage_key, get_storage
from app.workers.pool import enqueue_ingestion

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
