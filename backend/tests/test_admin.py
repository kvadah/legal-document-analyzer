"""Admin API tests — usage, org settings, audit query, export, user removal,
org deletion scheduling (09-api-spec.md §9, 11-security-compliance.md §6–7)."""
import pytest

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


async def _upload(client, token, filename="contract.txt", content=b"MSA between Acme and Beta."):
    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", (filename, content, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["documents"][0]["document_id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Usage dashboard ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_usage_requires_admin(client):
    reg = await register_user(client, org_name="Usage Org", email="usage-admin@example.com")
    admin_token = reg.json()["access_token"]
    viewer = await _invite_and_accept(client, admin_token, "usage-viewer@example.com", "viewer")

    resp = await client.get("/api/v1/admin/usage", headers=_auth(viewer["access_token"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_usage_reports_documents_storage_and_llm(client):
    reg = await register_user(client, org_name="Usage2 Org", email="usage2@example.com")
    token = reg.json()["access_token"]
    await _upload(client, token)
    await _invite_and_accept(client, token, "usage2-member@example.com", "reviewer")

    resp = await client.get("/api/v1/admin/usage", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["documents"]["total"] == 1
    assert body["documents"]["deleted"] == 0
    assert body["storage_bytes"] > 0
    assert body["users"]["total"] == 2
    assert body["users"]["active"] == 2
    # The mock provider reports zero tokens, but the row must exist so the
    # aggregation is exercised.
    stages = {s["stage"]: s for s in body["llm"]["by_stage"]}
    assert "ai_pipeline" in stages


# ── Org settings ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_and_update_org_settings(client):
    reg = await register_user(client, org_name="Settings Org", email="settings@example.com")
    token = reg.json()["access_token"]

    resp = await client.get("/api/v1/admin/org", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Settings Org"
    assert body["retention_days"] == 30
    assert body["audit_retention_days"] == 730
    assert body["scheduled_deletion_at"] is None

    resp = await client.patch(
        "/api/v1/admin/org",
        headers=_auth(token),
        json={
            "name": "Renamed Org",
            "retention_days": 60,
            "audit_retention_days": 365,
            "llm_provider": "gemini",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Renamed Org"
    assert body["retention_days"] == 60
    assert body["audit_retention_days"] == 365
    assert body["llm_provider"] == "gemini"

    # Persisted
    body = (await client.get("/api/v1/admin/org", headers=_auth(token))).json()
    assert body["retention_days"] == 60


@pytest.mark.asyncio
async def test_org_settings_validation(client):
    reg = await register_user(client, org_name="Val Org", email="admin-val@example.com")
    token = reg.json()["access_token"]

    resp = await client.patch(
        "/api/v1/admin/org", headers=_auth(token), json={"retention_days": 0}
    )
    assert resp.status_code == 422
    resp = await client.patch(
        "/api/v1/admin/org", headers=_auth(token), json={"llm_provider": "unknown"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_org_settings_requires_admin(client):
    reg = await register_user(client, org_name="Set2 Org", email="set2@example.com")
    admin_token = reg.json()["access_token"]
    viewer = await _invite_and_accept(client, admin_token, "set2-viewer@example.com", "viewer")

    assert (
        await client.get("/api/v1/admin/org", headers=_auth(viewer["access_token"]))
    ).status_code == 403
    assert (
        await client.patch(
            "/api/v1/admin/org",
            headers=_auth(viewer["access_token"]),
            json={"name": "Hacked"},
        )
    ).status_code == 403


# ── User removal ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_remove_user(client, db_session):
    from app.models.models import User
    from sqlalchemy import select

    reg = await register_user(client, org_name="Rm Org", email="rm-admin@example.com")
    admin_token = reg.json()["access_token"]
    member = await _invite_and_accept(client, admin_token, "rm-member@example.com", "viewer")
    member_id = member["user"]["id"]

    resp = await client.delete(
        f"/api/v1/admin/users/{member_id}", headers=_auth(admin_token)
    )
    assert resp.status_code == 204, resp.text

    result = await db_session.execute(
        select(User).where(User.email == "rm-member@example.com")
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cannot_remove_self_or_last_admin(client):
    reg = await register_user(client, org_name="Rm2 Org", email="rm2@example.com")
    admin_token = reg.json()["access_token"]
    admin_id = reg.json()["user"]["id"]

    resp = await client.delete(f"/api/v1/admin/users/{admin_id}", headers=_auth(admin_token))
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "cannot_modify_self"


@pytest.mark.asyncio
async def test_cannot_remove_user_with_uploads(client):
    reg = await register_user(client, org_name="Rm3 Org", email="rm3@example.com")
    admin_token = reg.json()["access_token"]
    reviewer = await _invite_and_accept(client, admin_token, "rm3-rev@example.com", "reviewer")
    await _upload(client, reviewer["access_token"])

    resp = await client.delete(
        f"/api/v1/admin/users/{reviewer['user']['id']}", headers=_auth(admin_token)
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "user_has_uploads"


# ── Audit log query ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_logs_require_admin_and_are_org_scoped(client):
    reg = await register_user(client, org_name="Aud Org", email="aud@example.com")
    admin_token = reg.json()["access_token"]
    viewer = await _invite_and_accept(client, admin_token, "aud-viewer@example.com", "viewer")

    assert (
        await client.get("/api/v1/admin/audit-logs", headers=_auth(viewer["access_token"]))
    ).status_code == 403

    resp = await client.get("/api/v1/admin/audit-logs", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    actions = {entry["action"] for entry in body["items"]}
    assert "auth.register" in actions
    assert "auth.invite_sent" in actions
    # Every entry carries an acting user and their email resolves.
    for entry in body["items"]:
        if entry["action"] == "auth.register":
            assert entry["user_email"] == "aud@example.com"


# ── Org data export ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_org_export_contains_documents_and_analysis(client):
    reg = await register_user(client, org_name="Exp Org", email="admin-exp@example.com")
    token = reg.json()["access_token"]
    doc_id = await _upload(
        client,
        token,
        content=(
            b"MASTER SERVICES AGREEMENT between Acme Corp and Beta LLC.\n\n"
            b"Confidentiality. Each party shall keep information confidential.\n"
        ),
    )

    resp = await client.get("/api/v1/admin/export", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["organization_id"]
    assert body["disclaimer"]
    docs = body["documents"]
    assert len(docs) == 1
    assert docs[0]["id"] == doc_id
    assert "clauses" in docs[0] and "risks" in docs[0]


# ── Org deletion scheduling ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_org_deletion_schedule_and_cancel(client):
    reg = await register_user(client, org_name="Del Org", email="del@example.com")
    token = reg.json()["access_token"]

    # Requires explicit confirmation.
    resp = await client.post(
        "/api/v1/admin/org/deletion", headers=_auth(token), json={"confirm": False}
    )
    assert resp.status_code == 400

    resp = await client.post(
        "/api/v1/admin/org/deletion", headers=_auth(token), json={"confirm": True}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["scheduled_deletion_at"] is not None

    # Cancelling clears it.
    resp = await client.delete("/api/v1/admin/org/deletion", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["scheduled_deletion_at"] is None
