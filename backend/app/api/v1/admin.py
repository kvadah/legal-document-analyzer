"""Admin API endpoints (09-api-spec.md §9) — admin role only.

User management, usage dashboard, org settings, audit-log query, org data
export, and org-deletion scheduling. All endpoints enforce the admin role
via dependency injection and are org-scoped through the repositories.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role
from app.db.session import get_session
from app.schemas.admin import (
    AuditLogListResponse,
    OrgDeletionRequest,
    OrgSettingsOut,
    OrgSettingsUpdateRequest,
    UsageResponse,
)
from app.schemas.auth import UserListResponse, UserOut, UserUpdateRequest
from app.services import admin_service, auth_service

router = APIRouter(prefix="/admin", tags=["admin"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("/users", response_model=UserListResponse)
async def list_users(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
) -> UserListResponse:
    """List all members of the org."""
    return await auth_service.list_users(session, org_id=UUID(current_user.org_id))


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    body: UserUpdateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
) -> UserOut:
    """Change a member's role and/or activation status."""
    return await auth_service.update_user(
        session,
        admin_user_id=current_user.id,
        org_id=UUID(current_user.org_id),
        user_id=user_id,
        role=body.role,
        is_active=body.is_active,
        ip_address=_client_ip(request),
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    user_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
) -> None:
    """Remove a member from the org (deletion is blocked for the last active
    admin and for members who have uploaded documents — deactivate instead)."""
    await admin_service.remove_user(
        session, current_user=current_user, user_id=user_id, ip_address=_client_ip(request)
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
) -> UsageResponse:
    """Document counts, storage usage, and LLM token usage summary."""
    return await admin_service.get_usage(session, current_user=current_user)


@router.get("/org", response_model=OrgSettingsOut)
async def get_org_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
) -> OrgSettingsOut:
    """Current org settings."""
    return await admin_service.get_org_settings(session, current_user=current_user)


@router.patch("/org", response_model=OrgSettingsOut)
async def update_org_settings(
    body: OrgSettingsUpdateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
) -> OrgSettingsOut:
    """Update org settings: name, retention policy, LLM provider preference."""
    return await admin_service.update_org_settings(
        session,
        current_user=current_user,
        name=body.name,
        retention_days=body.retention_days,
        audit_retention_days=body.audit_retention_days,
        llm_provider=body.llm_provider,
        ip_address=_client_ip(request),
    )


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = None,
    user_id: UUID | None = None,
    resource_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditLogListResponse:
    """Query the org's audit trail for compliance purposes (11 §6)."""
    return await admin_service.list_audit_logs(
        session,
        current_user=current_user,
        limit=limit,
        offset=offset,
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/export")
async def export_org_data(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
) -> JSONResponse:
    """Machine-readable export of all org documents + analysis (11 §7)."""
    payload = await admin_service.export_org_data(
        session, current_user=current_user, ip_address=_client_ip(request)
    )
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": 'attachment; filename="org-export.json"',
        },
    )


@router.post("/org/deletion", response_model=OrgSettingsOut)
async def schedule_org_deletion(
    body: OrgDeletionRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
) -> OrgSettingsOut:
    """Schedule full org deletion after the mandatory waiting period
    (7 days by default). Cancellable until the retention job executes it."""
    return await admin_service.schedule_org_deletion(
        session, current_user=current_user, confirm=body.confirm,
        ip_address=_client_ip(request),
    )


@router.delete("/org/deletion", response_model=OrgSettingsOut)
async def cancel_org_deletion(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
) -> OrgSettingsOut:
    """Cancel a scheduled org deletion."""
    return await admin_service.cancel_org_deletion(
        session, current_user=current_user, ip_address=_client_ip(request)
    )
