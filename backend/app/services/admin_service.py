"""Admin service: usage stats, org settings, user removal, audit query,
org data export, and org-deletion scheduling (09-api-spec.md §9,
11-security-compliance.md §6–7).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser
from app.models.models import (
    Annotation,
    Comment,
    Document,
    DocumentStatus,
    LLMUsageLog,
    Organization,
    User,
)
from app.repositories.audit_repo import AuditRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.org_repo import OrgRepository
from app.schemas.admin import (
    AuditLogListResponse,
    AuditLogOut,
    OrgSettingsOut,
    UsageDocumentStats,
    UsageLLMStageStats,
    UsageLLMStats,
    UsageResponse,
    UsageUserStats,
)
from app.services import analysis_service, audit_service
from app.services.export_service import DISCLAIMER

_PROCESSING_STATUSES = {
    DocumentStatus.UPLOADED,
    DocumentStatus.OCR_PROCESSING,
    DocumentStatus.OCR_COMPLETE,
    DocumentStatus.PARSING,
    DocumentStatus.CHUNKING,
    DocumentStatus.EMBEDDING,
    DocumentStatus.METADATA_EXTRACTION,
    DocumentStatus.INGESTION_READY,
    DocumentStatus.AI_PIPELINE_PROCESSING,
}


def _org_settings_out(org: Organization) -> OrgSettingsOut:
    return OrgSettingsOut(
        id=str(org.id),
        name=org.name,
        plan=org.plan,
        retention_days=org.retention_days,
        audit_retention_days=org.audit_retention_days,
        llm_provider=org.llm_provider,
        scheduled_deletion_at=org.scheduled_deletion_at,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


async def _get_org(session: AsyncSession, org_id: UUID) -> Organization:
    org = await OrgRepository(session).get_by_id(org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Organization not found"},
        )
    return org


# ── Usage dashboard ───────────────────────────────────────────────────────────


async def get_usage(session: AsyncSession, *, current_user: CurrentUser) -> UsageResponse:
    org_id = UUID(current_user.org_id)

    docs = (
        await session.execute(select(Document).where(Document.organization_id == org_id))
    ).scalars().all()
    document_stats = UsageDocumentStats(
        total=len(docs),
        analyzed=sum(1 for d in docs if d.status == DocumentStatus.ANALYSIS_READY),
        processing=sum(1 for d in docs if d.status in _PROCESSING_STATUSES),
        errored=sum(1 for d in docs if d.status == DocumentStatus.ERROR),
        deleted=sum(1 for d in docs if d.deleted_at is not None),
    )
    # Soft-deleted files still occupy storage until the retention job purges
    # them, so storage usage intentionally counts every row.
    storage_bytes = sum(d.file_size_bytes for d in docs)

    rows = (
        await session.execute(
            select(
                LLMUsageLog.stage,
                func.count(),
                func.coalesce(func.sum(LLMUsageLog.input_tokens), 0),
                func.coalesce(func.sum(LLMUsageLog.output_tokens), 0),
            )
            .where(LLMUsageLog.organization_id == org_id)
            .group_by(LLMUsageLog.stage)
        )
    ).all()
    by_stage = [
        UsageLLMStageStats(
            stage=stage, calls=calls, input_tokens=inp, output_tokens=outp
        )
        for stage, calls, inp, outp in rows
    ]
    llm = UsageLLMStats(
        calls=sum(s.calls for s in by_stage),
        input_tokens=sum(s.input_tokens for s in by_stage),
        output_tokens=sum(s.output_tokens for s in by_stage),
        by_stage=by_stage,
    )

    user_rows = (
        await session.execute(
            select(
                func.count(),
                # SUM over a Boolean column is not portable (SQLite coerces
                # the result through the boolean type, Postgres rejects it),
                # so count the active rows explicitly.
                func.count().filter(User.is_active.is_(True)),
            ).where(User.organization_id == org_id)
        )
    ).one()
    users = UsageUserStats(total=user_rows[0] or 0, active=int(user_rows[1] or 0))

    return UsageResponse(
        documents=document_stats,
        storage_bytes=storage_bytes,
        llm=llm,
        users=users,
    )


# ── Org settings ──────────────────────────────────────────────────────────────


async def get_org_settings(
    session: AsyncSession, *, current_user: CurrentUser
) -> OrgSettingsOut:
    org = await _get_org(session, UUID(current_user.org_id))
    return _org_settings_out(org)


async def update_org_settings(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    name: str | None = None,
    retention_days: int | None = None,
    audit_retention_days: int | None = None,
    llm_provider: str | None = None,
    ip_address: str | None = None,
) -> OrgSettingsOut:
    org = await _get_org(session, UUID(current_user.org_id))
    changes: dict[str, Any] = {}
    if name is not None and name != org.name:
        org.name = name
        changes["name"] = name
    if retention_days is not None and retention_days != org.retention_days:
        org.retention_days = retention_days
        changes["retention_days"] = retention_days
    if audit_retention_days is not None and audit_retention_days != org.audit_retention_days:
        org.audit_retention_days = audit_retention_days
        changes["audit_retention_days"] = audit_retention_days
    if llm_provider is not None and llm_provider != org.llm_provider:
        org.llm_provider = llm_provider
        changes["llm_provider"] = llm_provider

    if changes:
        await session.flush()
        await audit_service.record(
            session,
            organization_id=org.id,
            user_id=current_user.id,
            action=audit_service.AuditAction.ORG_SETTINGS_UPDATED,
            resource_type="organization",
            resource_id=org.id,
            ip_address=ip_address,
            details=changes,
        )
        await session.commit()
        await session.refresh(org)
    return _org_settings_out(org)


# ── User removal ──────────────────────────────────────────────────────────────


async def remove_user(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    user_id: UUID,
    ip_address: str | None = None,
) -> None:
    """Remove a member from the org (admin only, 09-api-spec.md §9).

    Guards: cannot remove yourself; cannot remove the last active admin
    (would lock the org out of administration); cannot remove a member who
    has uploaded documents (their uploads' provenance would dangle —
    deactivate instead).
    """
    org_id = UUID(current_user.org_id)
    if user_id == UUID(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "cannot_modify_self",
                "message": "You cannot remove your own account.",
            },
        )

    repo_result = await session.execute(
        select(User).where(User.id == user_id, User.organization_id == org_id)
    )
    user = repo_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "User not found"},
        )

    active_admins = (
        await session.execute(
            select(func.count()).where(
                User.organization_id == org_id,
                User.role == "admin",
                User.is_active.is_(True),
            )
        )
    ).scalar_one()
    if user.role == "admin" and user.is_active and active_admins <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "last_admin",
                "message": "Cannot remove the last active admin of the organization.",
            },
        )

    upload_count = (
        await session.execute(
            select(func.count()).where(
                Document.organization_id == org_id, Document.uploaded_by == user_id
            )
        )
    ).scalar_one()
    if upload_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "user_has_uploads",
                "message": (
                    "This member has uploaded documents and cannot be removed. "
                    "Deactivate their account instead."
                ),
            },
        )

    email = user.email
    # Comments/annotations authored by the user are removed with the account.
    await session.execute(delete(Comment).where(Comment.user_id == user_id))
    await session.execute(delete(Annotation).where(Annotation.user_id == user_id))
    await session.delete(user)
    await audit_service.record(
        session,
        organization_id=org_id,
        user_id=current_user.id,
        action=audit_service.AuditAction.USER_REMOVED,
        resource_type="user",
        resource_id=user_id,
        ip_address=ip_address,
        details={"removed_email": email},
    )
    await session.commit()


# ── Audit log query ───────────────────────────────────────────────────────────


async def list_audit_logs(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
    user_id: UUID | None = None,
    resource_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditLogListResponse:
    repo = AuditRepository(session, UUID(current_user.org_id))
    entries, total = await repo.list_entries(
        limit=limit,
        offset=offset,
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
    )
    emails = await repo.user_emails([e.user_id for e in entries if e.user_id])
    return AuditLogListResponse(
        items=[
            AuditLogOut(
                id=str(e.id),
                user_id=str(e.user_id) if e.user_id else None,
                user_email=emails.get(e.user_id) if e.user_id else None,
                action=e.action,
                resource_type=e.resource_type,
                resource_id=e.resource_id,
                ip_address=e.ip_address,
                details=e.details,
                created_at=e.created_at,
            )
            for e in entries
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── Org data export (portability, 11-security-compliance.md §7) ───────────────


async def export_org_data(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Machine-readable export of every document + analysis in the org."""
    org_id = UUID(current_user.org_id)
    repo = DocumentRepository(session, org_id)
    documents, _total = await repo.list(limit=10000)

    payload_documents: list[dict[str, Any]] = []
    for doc in documents:
        entry: dict[str, Any] = {
            "id": str(doc.id),
            "filename": doc.filename,
            "document_type": doc.document_type,
            "status": doc.status.value if isinstance(doc.status, DocumentStatus) else doc.status,
            "page_count": doc.page_count,
            "uploaded_at": doc.created_at.isoformat(),
            "contract_score": float(doc.contract_score) if doc.contract_score is not None else None,
            "ai_confidence_score": (
                float(doc.ai_confidence_score) if doc.ai_confidence_score is not None else None
            ),
            "parent_document_id": str(doc.parent_document_id) if doc.parent_document_id else None,
        }
        if doc.status == DocumentStatus.ANALYSIS_READY:
            summary = await analysis_service.get_summary(session, current_user, doc.id)
            clauses = await analysis_service.list_clauses(session, current_user, doc.id)
            risks = await analysis_service.list_risks(session, current_user, doc.id)
            entities = await analysis_service.list_entities(session, current_user, doc.id)
            obligations = await analysis_service.list_obligations(
                session, current_user, doc.id
            )
            entry["summary"] = summary.model_dump(mode="json")
            entry["clauses"] = clauses.model_dump(mode="json")
            entry["risks"] = risks.model_dump(mode="json")
            entry["entities"] = entities.model_dump(mode="json")
            entry["obligations"] = obligations.model_dump(mode="json")
        payload_documents.append(entry)

    await audit_service.record(
        session,
        organization_id=org_id,
        user_id=current_user.id,
        action=audit_service.AuditAction.ORG_EXPORTED,
        resource_type="organization",
        resource_id=org_id,
        ip_address=ip_address,
        details={"document_count": len(payload_documents)},
    )
    await session.commit()

    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "organization_id": str(org_id),
        "documents": payload_documents,
        "disclaimer": DISCLAIMER,
    }


# ── Org deletion scheduling (11-security-compliance.md §7) ────────────────────


async def schedule_org_deletion(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    confirm: bool,
    ip_address: str | None = None,
) -> OrgSettingsOut:
    """Schedule a full org deletion after the mandatory waiting period."""
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "message": "Deletion must be explicitly confirmed (confirm: true).",
            },
        )
    org = await _get_org(session, UUID(current_user.org_id))
    if org.scheduled_deletion_at is None:
        org.scheduled_deletion_at = datetime.now(UTC) + timedelta(
            days=settings.org_deletion_wait_days
        )
        await session.flush()
        await audit_service.record(
            session,
            organization_id=org.id,
            user_id=current_user.id,
            action=audit_service.AuditAction.ORG_DELETION_SCHEDULED,
            resource_type="organization",
            resource_id=org.id,
            ip_address=ip_address,
            details={"scheduled_deletion_at": org.scheduled_deletion_at.isoformat()},
        )
        await session.commit()
        await session.refresh(org)
    return _org_settings_out(org)


async def cancel_org_deletion(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    ip_address: str | None = None,
) -> OrgSettingsOut:
    """Cancel a scheduled org deletion (allowed until the waiting period ends)."""
    org = await _get_org(session, UUID(current_user.org_id))
    if org.scheduled_deletion_at is not None:
        org.scheduled_deletion_at = None
        await session.flush()
        await audit_service.record(
            session,
            organization_id=org.id,
            user_id=current_user.id,
            action=audit_service.AuditAction.ORG_DELETION_CANCELLED,
            resource_type="organization",
            resource_id=org.id,
            ip_address=ip_address,
        )
        await session.commit()
        await session.refresh(org)
    return _org_settings_out(org)


__all__ = [
    "get_usage",
    "get_org_settings",
    "update_org_settings",
    "remove_user",
    "list_audit_logs",
    "export_org_data",
    "schedule_org_deletion",
    "cancel_org_deletion",
]
