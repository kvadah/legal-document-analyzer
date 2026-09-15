"""Data retention & deletion jobs (11-security-compliance.md §7).

Runs as a scheduled arq job (daily) and is directly invocable for tests:

1. **Document purge** — soft-deleted documents past the org's grace period
   (``retention_days``) are hard-deleted: object-storage files (original,
   OCR text, version artifacts), Qdrant vectors, and every DB row that
   hangs off the document.
2. **Audit pruning** — audit entries older than the org's
   ``audit_retention_days`` (default 2 years) are removed. This is the
   only code path allowed to delete audit rows.
3. **Org deletion** — orgs with a ``scheduled_deletion_at`` in the past
   are fully cascaded: every document (with artifacts), report, user,
   audit entry, and the org row itself.

All artifact deletions are best-effort per item: a storage blip must not
abort the pass, and the DB rows are the source of truth for what still
needs purging on the next run.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.models import (
    Annotation,
    AuditLog,
    Chunk,
    Clause,
    Comment,
    Comparison,
    Document,
    DocumentRelationship,
    DocumentSummary,
    DocumentVersion,
    Entity,
    LLMUsageLog,
    Obligation,
    Organization,
    Report,
    Risk,
    User,
)
from app.repositories.audit_repo import AuditRepository
from app.services import audit_service
from app.services.storage_service import get_storage
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)


async def purge_document(session: AsyncSession, doc: Document) -> None:
    """Hard-delete one document and every artifact tied to it.

    Assumes the caller has already decided this document is due for purge.
    """
    document_id = doc.id

    # 1. Vector embeddings (best-effort).
    try:
        result = await session.execute(
            select(Chunk.embedding_vector_id).where(
                Chunk.document_id == document_id,
                Chunk.embedding_vector_id.is_not(None),
            )
        )
        vector_ids = [row[0] for row in result.all() if row[0]]
        if vector_ids:
            await get_vector_store().delete(vector_ids)
    except Exception:  # noqa: BLE001
        logger.exception("retention.vector_delete_failed", extra={"document_id": str(document_id)})

    # 2. Object-storage files (best-effort): original, OCR text, versions.
    storage = get_storage()
    paths = {doc.storage_path, doc.ocr_text_storage_path} - {None}
    version_rows = (
        await session.execute(
            select(DocumentVersion.storage_path).where(DocumentVersion.document_id == document_id)
        )
    ).all()
    paths.update(row[0] for row in version_rows if row[0])
    for key in paths:
        try:
            await storage.delete(key)
        except Exception:  # noqa: BLE001
            logger.warning(
                "retention.storage_delete_failed",
                extra={"document_id": str(document_id), "key": key},
            )

    # 3. DB rows. Children first, then join tables without ORM cascades.
    for table in (
        Annotation,
        Comment,
        DocumentSummary,
        Obligation,
        Entity,
        Risk,
        Clause,
        Chunk,
        DocumentVersion,
    ):
        await session.execute(delete(table).where(table.document_id == document_id))

    await session.execute(
        delete(Comparison).where(
            (Comparison.document_id_a == document_id) | (Comparison.document_id_b == document_id)
        )
    )
    await session.execute(
        delete(DocumentRelationship).where(
            (DocumentRelationship.document_id_a == document_id)
            | (DocumentRelationship.document_id_b == document_id)
        )
    )
    # Detach version-chain children (parent row is going away).
    await session.execute(
        update(Document)
        .where(Document.parent_document_id == document_id)
        .values(parent_document_id=None)
    )
    # Preserve usage aggregates; drop the FK reference.
    await session.execute(
        update(LLMUsageLog).where(LLMUsageLog.document_id == document_id).values(document_id=None)
    )
    await session.delete(doc)
    await session.flush()


async def _purge_due_documents(session: AsyncSession, org: Organization, now: datetime) -> int:
    cutoff = now - timedelta(days=org.retention_days)
    result = await session.execute(
        select(Document).where(
            Document.organization_id == org.id,
            Document.deleted_at.is_not(None),
            Document.deleted_at < cutoff,
        )
    )
    purged = 0
    for doc in result.scalars().all():
        await purge_document(session, doc)
        # System audit entry (no acting user) — the purge itself is a
        # compliance-relevant event.
        session.add(
            AuditLog(
                organization_id=org.id,
                user_id=None,
                action=audit_service.AuditAction.DOCUMENT_PURGED,
                resource_type="document",
                resource_id=str(doc.id),
                details={"filename": doc.filename},
            )
        )
        purged += 1
    return purged


async def _prune_audit_logs(session: AsyncSession, org: Organization, now: datetime) -> int:
    cutoff = now - timedelta(days=org.audit_retention_days)
    return await AuditRepository(session, org.id).prune_before(cutoff)


async def _delete_org(session: AsyncSession, org: Organization) -> None:
    """Full cascade org deletion (11-security-compliance.md §7)."""
    # Documents (with storage/vector artifacts) via the shared purge path.
    docs = (
        await session.execute(select(Document).where(Document.organization_id == org.id))
    ).scalars().all()
    for doc in docs:
        await purge_document(session, doc)

    # Report artifacts + rows.
    storage = get_storage()
    reports = (
        await session.execute(select(Report).where(Report.organization_id == org.id))
    ).scalars().all()
    for report in reports:
        if report.storage_path:
            try:
                await storage.delete(report.storage_path)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "retention.report_storage_delete_failed",
                    extra={"report_id": str(report.id)},
                )
    await session.execute(delete(Report).where(Report.organization_id == org.id))

    await session.execute(delete(LLMUsageLog).where(LLMUsageLog.organization_id == org.id))
    await session.execute(delete(AuditLog).where(AuditLog.organization_id == org.id))
    await session.execute(delete(User).where(User.organization_id == org.id))
    await session.delete(org)
    await session.flush()


async def run_retention_pass(*, now: datetime | None = None) -> dict[str, int]:
    """One full retention sweep. Returns counters for logging/tests."""
    now = now or datetime.now(UTC)
    stats = {"documents_purged": 0, "audit_entries_pruned": 0, "orgs_deleted": 0}

    async with AsyncSessionLocal() as session:
        # 1. Orgs whose deletion waiting period has elapsed.
        due_orgs = (
            await session.execute(
                select(Organization).where(
                    Organization.scheduled_deletion_at.is_not(None),
                    Organization.scheduled_deletion_at <= now,
                )
            )
        ).scalars().all()
        for org in due_orgs:
            await _delete_org(session, org)
            stats["orgs_deleted"] += 1

        # 2. Per-org document purge + audit pruning.
        orgs = (await session.execute(select(Organization))).scalars().all()
        for org in orgs:
            stats["documents_purged"] += await _purge_due_documents(session, org, now)
            stats["audit_entries_pruned"] += await _prune_audit_logs(session, org, now)

        await session.commit()

    if any(stats.values()):
        logger.info("retention.pass_complete", extra=stats)
    return stats


def purge_date_for(deleted_at: datetime, retention_days: int) -> datetime:
    """When a soft-deleted document will be hard-deleted (UI display)."""
    return deleted_at + timedelta(days=retention_days)


__all__ = ["purge_document", "run_retention_pass", "purge_date_for"]
