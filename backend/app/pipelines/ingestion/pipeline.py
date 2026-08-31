"""Ingestion pipeline orchestrator."""
from __future__ import annotations

import json
import logging
import uuid
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.models import Chunk, Document, DocumentStatus
from app.pipelines.ingestion.chunker import chunk_paragraphs
from app.pipelines.ingestion.metadata import extract_metadata
from app.pipelines.ingestion.ocr import run_ocr
from app.pipelines.ingestion.parser import flatten_paragraphs, parse_document
from app.pipelines.status import transition_document_status
from app.providers.embeddings import VECTOR_SIZE, get_embedding_provider
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.document_repo import DocumentRepository
from app.services.storage_service import build_document_storage_key, get_storage

logger = logging.getLogger(__name__)


async def run_ingestion_pipeline(document_id: str) -> None:
    async with AsyncSessionLocal() as session:
        doc = await _load_document(session, UUID(document_id))
        if doc is None:
            logger.error("ingestion.document_not_found", extra={"document_id": document_id})
            return
        try:
            await _run_stages(session, doc)
        except Exception as exc:
            logger.exception("ingestion.failed", extra={"document_id": document_id})
            await transition_document_status(
                session,
                organization_id=doc.organization_id,
                document_id=doc.id,
                status=DocumentStatus.ERROR,
                status_detail=str(exc),
            )


async def _load_document(session: AsyncSession, document_id: UUID) -> Document | None:
    stmt = select(Document).where(Document.id == document_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _run_stages(session: AsyncSession, doc: Document) -> None:
    storage = get_storage()
    org_id = doc.organization_id
    doc_id = doc.id
    org_id_str = str(org_id)
    doc_id_str = str(doc_id)

    file_bytes = await storage.get_bytes(doc.storage_path)
    file_type = doc.file_type
    document_type_value = doc.document_type.value

    await transition_document_status(
        session,
        organization_id=org_id,
        document_id=doc_id,
        status=DocumentStatus.OCR_PROCESSING,
    )
    ocr_result = run_ocr(file_bytes, file_type)
    ocr_key = build_document_storage_key(org_id_str, doc_id_str, "ocr_output.json")
    await storage.put_bytes(ocr_key, json.dumps(ocr_result.to_json()).encode("utf-8"), "application/json")

    status_detail = ocr_result.low_quality_warning
    await transition_document_status(
        session,
        organization_id=org_id,
        document_id=doc_id,
        status=DocumentStatus.OCR_COMPLETE,
        status_detail=status_detail,
        page_count=ocr_result.page_count,
        ocr_text_storage_path=ocr_key,
    )

    await transition_document_status(
        session,
        organization_id=org_id,
        document_id=doc_id,
        status=DocumentStatus.PARSING,
    )
    parsed = parse_document(ocr_result)
    parsed_key = build_document_storage_key(org_id_str, doc_id_str, "parsed_document.json")
    await storage.put_bytes(parsed_key, json.dumps(parsed.to_json()).encode("utf-8"), "application/json")
    paragraph_blocks = flatten_paragraphs(parsed)
    full_text = "\n\n".join(block.text for block in paragraph_blocks)

    await transition_document_status(
        session,
        organization_id=org_id,
        document_id=doc_id,
        status=DocumentStatus.CHUNKING,
    )
    chunk_drafts = chunk_paragraphs(paragraph_blocks)
    if not chunk_drafts:
        chunk_drafts = chunk_paragraphs(
            [block for page in ocr_result.pages for block in page if block.text.strip()]
        )

    await transition_document_status(
        session,
        organization_id=org_id,
        document_id=doc_id,
        status=DocumentStatus.EMBEDDING,
    )
    chunk_repo = ChunkRepository(session)
    await chunk_repo.delete_for_document(doc_id)

    provider = get_embedding_provider()
    texts = [draft.text for draft in chunk_drafts]
    vectors = await provider.embed_texts(texts) if texts else []

    chunk_models: list[Chunk] = []
    qdrant_points: list[PointStruct] = []
    for draft, vector in zip(chunk_drafts, vectors, strict=False):
        chunk_id = uuid.uuid4()
        chunk_models.append(
            Chunk(
                id=chunk_id,
                document_id=doc_id,
                chunk_index=draft.chunk_index,
                text=draft.text,
                page_number=draft.page_number,
                paragraph_index=draft.paragraph_index,
                section_heading=draft.section_heading,
                token_count=draft.token_count,
                embedding_vector_id=str(chunk_id),
            )
        )
        qdrant_points.append(
            PointStruct(
                id=str(chunk_id),
                vector=vector,
                payload={
                    "document_id": doc_id_str,
                    "organization_id": org_id_str,
                    "chunk_id": str(chunk_id),
                    "page_number": draft.page_number,
                    "document_type": document_type_value,
                    "text": draft.text,
                },
            )
        )

    if chunk_models:
        await chunk_repo.create_chunks(chunk_models)
        await _upsert_qdrant_points(qdrant_points)

    await transition_document_status(
        session,
        organization_id=org_id,
        document_id=doc_id,
        status=DocumentStatus.METADATA_EXTRACTION,
    )
    metadata = extract_metadata(full_text, page_count=ocr_result.page_count)
    repo = DocumentRepository(session, org_id)
    await repo.update_status(
        doc_id,
        DocumentStatus.INGESTION_READY,
        language=metadata.language,
        document_type=metadata.document_type.value,
        page_count=ocr_result.page_count,
        status_detail=status_detail,
    )
    await session.commit()
    from app.pipelines.status import publish_document_status

    await publish_document_status(doc_id, DocumentStatus.INGESTION_READY, status_detail=status_detail)


async def _upsert_qdrant_points(points: list[PointStruct]) -> None:
    if not points:
        return

    def _write() -> None:
        client = QdrantClient(url=settings.qdrant_url)
        client.upsert(collection_name=settings.qdrant_collection_name, points=points)

    import asyncio

    await asyncio.to_thread(_write)
