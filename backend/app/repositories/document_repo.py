"""Document repository with org-scoped access and soft-delete awareness.

Soft-deleted documents (deleted_at set) are invisible to every normal
query — get, list, hash-dedup — per 11-security-compliance.md §7. Only
the retention job and the admin trash/restore flows opt in to seeing them.
"""
import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select

from app.models.models import Document, DocumentStatus
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def get_by_id(
        self, resource_id: UUID, *, include_deleted: bool = False
    ) -> Document:
        """Fetch a document by ID, scoped to this org.

        Raises HTTP 404 if not found, in another org, or soft-deleted
        (unless ``include_deleted`` — used by restore, the retention job,
        and in-flight pipeline status updates).
        """
        stmt = (
            select(Document)
            .where(Document.id == resource_id)
            .where(self._org_filter())
        )
        if not include_deleted:
            stmt = stmt.where(Document.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise self._not_found(resource_id)
        return doc

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        extra_filters: list | None = None,
        include_deleted: bool = False,
        deleted_only: bool = False,
    ) -> tuple[list[Document], int]:
        """Paginated documents for this org.

        Normal listing excludes soft-deleted rows; ``deleted_only`` returns
        only the soft-deleted ones (admin trash view).
        """
        filters = [self._org_filter()]
        if deleted_only:
            filters.append(Document.deleted_at.is_not(None))
        elif not include_deleted:
            filters.append(Document.deleted_at.is_(None))
        if extra_filters:
            filters.extend(extra_filters)

        total: int = (
            await self.session.execute(
                select(func.count()).select_from(Document).where(*filters)
            )
        ).scalar_one()
        stmt = (
            select(Document)
            .where(*filters)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def find_by_hash(self, file_hash: str) -> Document | None:
        """Find a non-deleted document in this org with the same content hash."""
        stmt = (
            select(Document)
            .where(self._org_filter())
            .where(Document.file_hash == file_hash)
            .where(Document.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete(self, document_id: UUID) -> Document:
        """Mark a document deleted (recoverable until the retention job purges it)."""
        doc = await self.get_by_id(document_id)
        doc.deleted_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def restore(self, document_id: UUID) -> Document:
        """Recover a soft-deleted document (admin, within the grace period)."""
        doc = await self.get_by_id(document_id, include_deleted=True)
        if doc.deleted_at is None:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "validation_error",
                    "message": "Document is not deleted",
                },
            )
        doc.deleted_at = None
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def create_document(
        self,
        *,
        uploaded_by: UUID,
        filename: str,
        file_type: str,
        file_size_bytes: int,
        storage_path: str,
        file_hash: str | None = None,
        document_id: UUID | None = None,
    ) -> Document:
        doc = Document(
            id=document_id or uuid.uuid4(),
            organization_id=self.organization_id,
            uploaded_by=uploaded_by,
            filename=filename,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            storage_path=storage_path,
            file_hash=file_hash,
            status=DocumentStatus.UPLOADED,
        )
        return await self.save(doc)

    async def update_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        *,
        status_detail: str | None = None,
        page_count: int | None = None,
        language: str | None = None,
        document_type: str | None = None,
        ocr_text_storage_path: str | None = None,
    ) -> Document:
        # include_deleted: an in-flight pipeline should finish (or fail)
        # gracefully even if the document was soft-deleted mid-run — the
        # retention job will purge the row and its artifacts later.
        doc = await self.get_by_id(document_id, include_deleted=True)
        doc.status = status
        if status_detail is not None:
            doc.status_detail = status_detail
        elif status == DocumentStatus.ANALYSIS_READY:
            # Terminal success: drop any stale error detail from a previous
            # failed run (e.g. a 429 that was later retried successfully).
            doc.status_detail = None
        if page_count is not None:
            doc.page_count = page_count
        if language is not None:
            doc.language = language
        if ocr_text_storage_path is not None:
            doc.ocr_text_storage_path = ocr_text_storage_path
        if document_type is not None:
            from app.models.models import DocumentType

            doc.document_type = DocumentType(document_type)
        await self.session.flush()
        await self.session.refresh(doc)
        return doc
