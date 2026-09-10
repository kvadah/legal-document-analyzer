"""Comparison pipeline worker (07-feature-spec-comparison-search.md §1).

Loads both documents' clauses and chunks, runs the pure diff engine, and
stores the structured diff result on the comparisons row.

Status lifecycle: pending → processing → completed | error.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.models import Comparison, Document
from app.pipelines.compare.diff_engine import align_clauses, diff_other_changes
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.chunk_repo import ChunkRepository

logger = logging.getLogger(__name__)

# Only pending jobs run; completed comparisons are never silently recomputed.
RUNNABLE_STATUSES = {"pending"}


async def run_comparison_pipeline(comparison_id: str) -> None:
    async with AsyncSessionLocal() as session:
        comparison = await _load_comparison(session, UUID(comparison_id))
        if comparison is None:
            logger.error("comparison_pipeline.not_found", extra={"comparison_id": comparison_id})
            return
        if comparison.status not in RUNNABLE_STATUSES:
            logger.info(
                "comparison_pipeline.skipped_not_pending",
                extra={"comparison_id": comparison_id, "status": comparison.status},
            )
            return

        doc_a, doc_b = await _load_documents(session, comparison)
        if doc_a is None or doc_b is None:
            logger.error(
                "comparison_pipeline.document_missing",
                extra={"comparison_id": comparison_id},
            )
            comparison.status = "error"
            comparison.result = {"error": "One of the compared documents no longer exists."}
            await session.commit()
            return

        comparison.status = "processing"
        await session.commit()

        try:
            analysis_repo = AnalysisRepository(session, doc_a.organization_id)
            chunk_repo = ChunkRepository(session)
            clauses_a = await analysis_repo.list_clauses(doc_a.id)
            clauses_b = await analysis_repo.list_clauses(doc_b.id)
            chunks_a = await chunk_repo.list_for_document(doc_a.id)
            chunks_b = await chunk_repo.list_for_document(doc_b.id)

            clause_entries = align_clauses(clauses_a, clauses_b)
            other_entries = diff_other_changes(chunks_a, chunks_b, clauses_a, clauses_b)
            counts = {
                "added": sum(1 for e in clause_entries if e["status"] == "added"),
                "removed": sum(1 for e in clause_entries if e["status"] == "removed"),
                "modified": sum(1 for e in clause_entries if e["status"] == "modified"),
                "unchanged": sum(1 for e in clause_entries if e["status"] == "unchanged"),
                "other_changes": len(other_entries),
            }

            comparison.result = {
                "clauses": clause_entries,
                "other_changes": other_entries,
                "counts": counts,
            }
            comparison.status = "completed"
            await session.commit()
            logger.info(
                "comparison_pipeline.completed",
                extra={"comparison_id": comparison_id, "counts": counts},
            )
        except Exception as exc:
            logger.exception("comparison_pipeline.failed", extra={"comparison_id": comparison_id})
            comparison.status = "error"
            comparison.result = {"error": f"Comparison failed: {exc}"}
            await session.commit()


async def _load_comparison(session: AsyncSession, comparison_id: UUID) -> Comparison | None:
    """Load a comparison by ID without org scoping.

    Worker context is trusted: rows are only created after the API layer
    verified both documents belong to the caller's org.
    """
    result = await session.execute(select(Comparison).where(Comparison.id == comparison_id))
    return result.scalar_one_or_none()


async def _load_documents(
    session: AsyncSession, comparison: Comparison
) -> tuple[Document | None, Document | None]:
    result = await session.execute(
        select(Document).where(
            Document.id.in_([comparison.document_id_a, comparison.document_id_b])
        )
    )
    documents = {doc.id: doc for doc in result.scalars().all()}
    return (
        documents.get(comparison.document_id_a),
        documents.get(comparison.document_id_b),
    )
