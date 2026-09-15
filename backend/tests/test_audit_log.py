"""Audit logging tests — the action types from 11-security-compliance.md §6
must be captured with user, org, resource, and (where available) IP."""
from uuid import UUID

import pytest
from app.models.models import AuditLog
from sqlalchemy import select

from tests.conftest import register_user


async def _invite_and_accept(client, admin_token, email, role="viewer"):
    invite = await client.post(
        "/api/v1/auth/invite",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": email, "role": role},
    )
    assert invite.status_code == 201, invite.text
    accept = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": invite.json()["token"], "password": "password123"},
    )
    assert accept.status_code == 201, accept.text
    return accept.json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _entries(db_session, org_id):
    # org_id arrives as a string from API responses; UUID columns need
    # real UUID objects when bound on SQLite.
    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.organization_id == UUID(org_id))
        .order_by(AuditLog.created_at)
    )
    return result.scalars().all()


@pytest.mark.asyncio
async def test_auth_events_audited(client, db_session):
    reg = await register_user(client, org_name="A1 Org", email="a1@example.com")
    org_id = reg.json()["user"]["org_id"]

    await client.post(
        "/api/v1/auth/login",
        json={"email": "a1@example.com", "password": "password123"},
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "a1@example.com", "password": "wrong-password"},
    )

    entries = await _entries(db_session, org_id)
    actions = [e.action for e in entries]
    assert "auth.register" in actions
    assert "auth.login" in actions
    assert "auth.login_failed" in actions

    login = next(e for e in entries if e.action == "auth.login")
    assert login.ip_address == "127.0.0.1"  # ASGI test client host


@pytest.mark.asyncio
async def test_document_lifecycle_audited(client, db_session, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, org_name="A2 Org", email="a2@example.com")
    token = reg.json()["access_token"]
    org_id = reg.json()["user"]["org_id"]

    upload = await client.post(
        "/api/v1/documents/upload",
        headers=_auth(token),
        files=[("files", ("msa.txt", b"MSA between Acme and Beta.", "text/plain"))],
    )
    doc_id = upload.json()["documents"][0]["document_id"]

    await client.get(f"/api/v1/documents/{doc_id}/text", headers=_auth(token))
    await client.get(f"/api/v1/documents/{doc_id}/export", headers=_auth(token))
    await client.delete(f"/api/v1/documents/{doc_id}", headers=_auth(token))
    await client.post(f"/api/v1/documents/{doc_id}/restore", headers=_auth(token))

    entries = await _entries(db_session, org_id)
    by_resource = [e for e in entries if e.resource_id == doc_id]
    actions = {e.action for e in by_resource}
    assert "document.uploaded" in actions
    assert "document.viewed" in actions
    assert "document.exported" in actions
    assert "document.deleted" in actions
    assert "document.restored" in actions


@pytest.mark.asyncio
async def test_risk_status_change_audited(client, db_session, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, org_name="A3 Org", email="a3@example.com")
    token = reg.json()["access_token"]
    org_id = reg.json()["user"]["org_id"]

    upload = await client.post(
        "/api/v1/documents/upload",
        headers=_auth(token),
        files=[
            (
                "files",
                (
                    "msa.txt",
                    b"MASTER SERVICES AGREEMENT\nLiability. Each party is liable.\n"
                    b"This agreement shall be unlimited in scope.\n",
                    "text/plain",
                ),
            )
        ],
    )
    doc_id = upload.json()["documents"][0]["document_id"]

    risks = await client.get(f"/api/v1/documents/{doc_id}/risks", headers=_auth(token))
    risk_id = risks.json()["items"][0]["id"]

    patch = await client.patch(
        f"/api/v1/documents/{doc_id}/risks/{risk_id}",
        headers=_auth(token),
        json={"status": "acknowledged"},
    )
    assert patch.status_code == 200

    entries = await _entries(db_session, org_id)
    risk_events = [e for e in entries if e.action == "risk.status_changed"]
    assert risk_events, "risk status change must be audited"
    assert risk_events[0].resource_id == risk_id
    assert risk_events[0].details["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_admin_actions_audited(client, db_session):
    reg = await register_user(client, org_name="A4 Org", email="a4@example.com")
    admin_token = reg.json()["access_token"]
    org_id = reg.json()["user"]["org_id"]

    member = await _invite_and_accept(client, admin_token, "a4-member@example.com", "viewer")
    member_id = member["user"]["id"]

    await client.patch(
        f"/api/v1/admin/users/{member_id}",
        headers=_auth(admin_token),
        json={"role": "reviewer"},
    )
    await client.patch(
        f"/api/v1/admin/users/{member_id}",
        headers=_auth(admin_token),
        json={"is_active": False},
    )
    await client.patch(
        "/api/v1/admin/org",
        headers=_auth(admin_token),
        json={"retention_days": 45},
    )
    await client.delete(f"/api/v1/admin/users/{member_id}", headers=_auth(admin_token))

    entries = await _entries(db_session, org_id)
    actions = {e.action for e in entries}
    assert "auth.invite_sent" in actions
    assert "user.role_changed" in actions
    assert "user.status_changed" in actions
    assert "org.settings_updated" in actions
    assert "user.removed" in actions

    role_change = next(e for e in entries if e.action == "user.role_changed")
    assert role_change.details == {
        "email": "a4-member@example.com",
        "from": "viewer",
        "to": "reviewer",
    }


@pytest.mark.asyncio
async def test_audit_logs_are_org_scoped(client, db_session):
    reg_a = await register_user(client, org_name="A5 Org A", email="a5a@example.com")
    reg_b = await register_user(client, org_name="A5 Org B", email="a5b@example.com")
    token_a = reg_a.json()["access_token"]
    org_b = reg_b.json()["user"]["org_id"]

    # Org B acts; org A must never see those entries.
    await client.post(
        "/api/v1/auth/login", json={"email": "a5b@example.com", "password": "password123"}
    )

    resp = await client.get("/api/v1/admin/audit-logs", headers=_auth(token_a))
    assert resp.status_code == 200
    for entry in resp.json()["items"]:
        assert entry["action"] != "auth.login" or entry["user_email"] == "a5a@example.com"

    entries_b = await _entries(db_session, org_b)
    assert any(e.action == "auth.login" for e in entries_b)
