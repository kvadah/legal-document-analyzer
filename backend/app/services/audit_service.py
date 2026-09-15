"""Audit logging service (11-security-compliance.md §6).

Every security-relevant action — authentication events, document access,
risk-status changes, admin actions — is recorded here. The log is
append-only: application code inserts, never updates or deletes (pruning
past the retention window is done exclusively by the retention job).

`record()` deliberately never raises: an audit failure must not break the
user-facing operation (the row simply won't appear in the trail).
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditLog
from app.repositories.audit_repo import AuditRepository

logger = logging.getLogger(__name__)


class AuditAction:
    """Stable action identifiers stored in audit_logs.action."""

    # Authentication
    AUTH_REGISTER = "auth.register"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_LOGOUT = "auth.logout"
    AUTH_INVITE_SENT = "auth.invite_sent"
    AUTH_INVITE_ACCEPTED = "auth.invite_accepted"

    # Admin / user management
    USER_ROLE_CHANGED = "user.role_changed"
    USER_STATUS_CHANGED = "user.status_changed"
    USER_REMOVED = "user.removed"

    # Documents
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_VIEWED = "document.viewed"
    DOCUMENT_EXPORTED = "document.exported"
    DOCUMENT_DOWNLOADED = "document.downloaded"
    DOCUMENT_DELETED = "document.deleted"
    DOCUMENT_RESTORED = "document.restored"
    DOCUMENT_PURGED = "document.purged"

    # Analysis
    RISK_STATUS_CHANGED = "risk.status_changed"

    # Reports
    REPORT_GENERATED = "report.generated"
    REPORT_DOWNLOADED = "report.downloaded"

    # Org-level
    ORG_SETTINGS_UPDATED = "org.settings_updated"
    ORG_EXPORTED = "org.exported"
    ORG_DELETION_SCHEDULED = "org.deletion_scheduled"
    ORG_DELETION_CANCELLED = "org.deletion_cancelled"


async def record(
    session: AsyncSession,
    *,
    organization_id: UUID | str,
    user_id: UUID | str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: UUID | str | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Append one audit entry. Best-effort: logs on failure, never raises."""
    try:
        entry = AuditLog(
            organization_id=UUID(str(organization_id)),
            user_id=UUID(str(user_id)) if user_id else None,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            ip_address=ip_address,
            details=details,
        )
        session.add(entry)
        await session.flush()
    except Exception:  # noqa: BLE001 — audit must never break the request
        logger.exception("audit.record_failed", extra={"action": action})


async def record_and_commit(
    session: AsyncSession,
    *,
    organization_id: UUID | str,
    user_id: UUID | str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: UUID | str | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Record an entry and commit immediately.

    For failure paths (e.g. failed login) where the surrounding request
    raises before its own commit — the audit row must outlive the
    rolled-back transaction.
    """
    await record(
        session,
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        details=details,
    )
    try:
        await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("audit.commit_failed", extra={"action": action})


__all__ = ["AuditAction", "record", "record_and_commit", "AuditRepository"]
