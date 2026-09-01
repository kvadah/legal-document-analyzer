"""Document repository with org-scoped access."""
import uuid
from uuid import UUID

from sqlalchemy import select

from app.models.models import Document, DocumentStatus
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def find_by_hash(self, file_hash: str) -> Document | None:
        """Find an existing document in this org with the same content hash."""
        stmt = (
            select(Document)
            .where(self._org_filter())
            .where(Document.file_hash == file_hash)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

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
        doc = await self.get_by_id(document_id)
        doc.status = status
        if status_detail is not None:
            doc.status_detail = status_detail
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
