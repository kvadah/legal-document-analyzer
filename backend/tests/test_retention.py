"""Data retention tests — soft delete, recovery, hard-delete purge, audit
pruning, and scheduled org deletion (11-security-compliance.md §7)."""
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from app.core.config import settings
from app.models.models import AuditLog, Chunk, Document, Organization, User
from app.services.retention_service import run_retention_pass
from sqlalchemy import select

from tests.conftest import register_user


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _upload(client, token, filename="msa.txt", content=b"MSA between Acme and Beta."):
    resp = await client.post(
        "/api/v1/documents/upload",
        headers=_auth(token),
        files=[("files", (filename, content, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["documents"][0]["document_id"]


async def _get_doc(db_session, doc_id):
    # doc_id arrives as a string from API responses; UUID columns need
    # real UUID objects when bound on SQLite.
    result = await db_session.execute(
        select(Document).where(Document.id == UUID(doc_id))
    )
    return result.scalar_one()


# ── Soft delete ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_soft_delete_hides_document_everywhere(client, db_session, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, org_name="SD Org", email="sd@example.com")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    resp = await client.delete(f"/api/v1/documents/{doc_id}", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted_at"] is not None

    # Hidden from the normal list, detail, and text endpoints.
    listing = await client.get("/api/v1/documents", headers=_auth(token))
    assert listing.json()["total"] == 0
    assert (
        await client.get(f"/api/v1/documents/{doc_id}", headers=_auth(token))
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/documents/{doc_id}/text", headers=_auth(token))
    ).status_code == 404

    # Search no longer returns it.
    search = await client.post(
        "/api/v1/search", headers=_auth(token), json={"query": "MSA", "mode": "keyword"}
    )
    assert search.status_code == 200
    assert all(g["document"]["id"] != doc_id for g in search.json()["groups"])

    # Still a 404 for another org's admin (not a 403 leak).
    other = await register_user(client, org_name="SD Other", email="sd-other@example.com")
    other_token = other.json()["access_token"]
    resp = await client.delete(f"/api/v1/documents/{doc_id}", headers=_auth(other_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_requires_reviewer(client):
    reg = await register_user(client, org_name="SD2 Org", email="sd2@example.com")
    admin_token = reg.json()["access_token"]
    doc_id = await _upload(client, admin_token)

    invite = await client.post(
        "/api/v1/auth/invite",
        headers=_auth(admin_token),
        json={"email": "sd2-viewer@example.com", "role": "viewer"},
    )
    accept = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": invite.json()["token"], "password": "password123"},
    )
    viewer_token = accept.json()["access_token"]

    resp = await client.delete(f"/api/v1/documents/{doc_id}", headers=_auth(viewer_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_trash_listing_and_restore(client, db_session, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, org_name="SD3 Org", email="sd3@example.com")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)
    await client.delete(f"/api/v1/documents/{doc_id}", headers=_auth(token))

    # Trash: admin-only, shows the deleted doc with a purge date.
    assert (
        await client.get("/api/v1/documents/deleted", headers=_auth(token))
    ).status_code == 200
    trash = (
        await client.get("/api/v1/documents/deleted", headers=_auth(token))
    ).json()
    assert trash["total"] == 1
    assert trash["items"][0]["id"] == doc_id
    assert trash["items"][0]["purges_at"] is not None

    # Restore within the grace period.
    resp = await client.post(f"/api/v1/documents/{doc_id}/restore", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted_at"] is None

    # Back in the normal list.
    listing = await client.get("/api/v1/documents", headers=_auth(token))
    assert listing.json()["total"] == 1

    # Restoring a not-deleted document is a 409.
    assert (
        await client.post(f"/api/v1/documents/{doc_id}/restore", headers=_auth(token))
    ).status_code == 409


# ── Hard-delete purge ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_purge_after_grace_period(client, db_session, monkeypatch, tmp_path):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, org_name="P1 Org", email="p1@example.com")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token, filename="purge-me.txt")

    doc = await _get_doc(db_session, doc_id)
    storage_file = Path(settings.local_storage_path) / doc.storage_path
    assert storage_file.exists()

    await client.delete(f"/api/v1/documents/{doc_id}", headers=_auth(token))

    # Simulate the grace period passing.
    doc = await _get_doc(db_session, doc_id)
    doc.deleted_at = datetime.now(UTC) - timedelta(days=31)
    await db_session.commit()

    stats = await run_retention_pass()
    assert stats["documents_purged"] == 1

    db_session.expire_all()
    result = await db_session.execute(
        select(Document).where(Document.id == UUID(doc_id))
    )
    assert result.scalar_one_or_none() is None
    # Chunks went with it.
    chunks = await db_session.execute(
        select(Chunk).where(Chunk.document_id == UUID(doc_id))
    )
    assert chunks.scalars().all() == []
    # Storage file removed.
    assert not storage_file.exists()
    # The purge itself was audited (system entry, no user).
    purge_entries = await db_session.execute(
        select(AuditLog).where(
            AuditLog.resource_id == str(doc_id), AuditLog.action == "document.purged"
        )
    )
    assert purge_entries.scalars().all()


@pytest.mark.asyncio
async def test_no_purge_within_grace_period(client, db_session, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, org_name="P2 Org", email="p2@example.com")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)
    await client.delete(f"/api/v1/documents/{doc_id}", headers=_auth(token))

    stats = await run_retention_pass()
    assert stats["documents_purged"] == 0

    db_session.expire_all()
    assert await _get_doc(db_session, doc_id)


@pytest.mark.asyncio
async def test_org_retention_policy_is_honored(client, db_session, monkeypatch):
    async def _nop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _nop)

    reg = await register_user(client, org_name="P3 Org", email="p3@example.com")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)
    await client.delete(f"/api/v1/documents/{doc_id}", headers=_auth(token))

    # Shorten the grace period to 1 day; deleted 6 hours ago → still safe.
    await client.patch(
        "/api/v1/admin/org", headers=_auth(token), json={"retention_days": 1}
    )
    doc = await _get_doc(db_session, doc_id)
    doc.deleted_at = datetime.now(UTC) - timedelta(hours=6)
    await db_session.commit()

    stats = await run_retention_pass()
    assert stats["documents_purged"] == 0

    # 2 days old with a 1-day policy → purged.
    doc = await _get_doc(db_session, doc_id)
    doc.deleted_at = datetime.now(UTC) - timedelta(days=2)
    await db_session.commit()
    stats = await run_retention_pass()
    assert stats["documents_purged"] == 1


@pytest.mark.asyncio
async def test_audit_logs_pruned_past_retention(client, db_session):
    reg = await register_user(client, org_name="P4 Org", email="p4@example.com")
    org_id = UUID(reg.json()["user"]["org_id"])

    # Create an entry, then age it beyond the default 730-day retention.
    db_session.add(
        AuditLog(
            organization_id=org_id,
            user_id=None,
            action="auth.login",
            created_at=datetime.now(UTC) - timedelta(days=731),
            updated_at=datetime.now(UTC) - timedelta(days=731),
        )
    )
    await db_session.commit()

    stats = await run_retention_pass()
    assert stats["audit_entries_pruned"] >= 1

    aged = await db_session.execute(
        select(AuditLog).where(
            AuditLog.organization_id == org_id,
            AuditLog.created_at < datetime.now(UTC) - timedelta(days=730),
        )
    )
    assert aged.scalars().all() == []


# ── Org deletion ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scheduled_org_deletion_cascades(client, db_session, monkeypatch):
    async def _nop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _nop)

    reg = await register_user(client, org_name="Doomed Org", email="doomed@example.com")
    token = reg.json()["access_token"]
    org_id = UUID(reg.json()["user"]["org_id"])
    doc_id = await _upload(client, token)

    resp = await client.post(
        "/api/v1/admin/org/deletion", headers=_auth(token), json={"confirm": True}
    )
    assert resp.status_code == 200
    scheduled_at = resp.json()["scheduled_deletion_at"]
    assert scheduled_at is not None

    # Simulate the 7-day waiting period elapsing.
    org = (
        await db_session.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one()
    org.scheduled_deletion_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    stats = await run_retention_pass()
    assert stats["orgs_deleted"] == 1

    db_session.expire_all()
    assert (
        await db_session.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(select(Document).where(Document.id == UUID(doc_id)))
    ).scalar_one_or_none() is None
    users = await db_session.execute(select(User).where(User.organization_id == org_id))
    assert users.scalars().all() == []
    logs = await db_session.execute(select(AuditLog).where(AuditLog.organization_id == org_id))
    assert logs.scalars().all() == []


@pytest.mark.asyncio
async def test_cancelled_org_deletion_is_not_executed(client, db_session):
    reg = await register_user(client, org_name="Saved Org", email="saved@example.com")
    token = reg.json()["access_token"]
    org_id = UUID(reg.json()["user"]["org_id"])

    await client.post("/api/v1/admin/org/deletion", headers=_auth(token), json={"confirm": True})
    await client.delete("/api/v1/admin/org/deletion", headers=_auth(token))

    stats = await run_retention_pass()
    assert stats["orgs_deleted"] == 0

    org = (
        await db_session.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one()
    assert org is not None
