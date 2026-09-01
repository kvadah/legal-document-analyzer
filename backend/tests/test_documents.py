"""Phase 2 document upload and ingestion tests."""
import pytest
from app.models.models import DocumentStatus

from tests.conftest import register_user


@pytest.mark.asyncio
async def test_upload_and_ingest_text_document(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, email="upload@example.com", org_name="Upload Org")
    token = reg.json()["access_token"]

    content = (
        b"MASTER SERVICES AGREEMENT\n\n"
        b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
        b"Confidentiality. Each party shall keep information confidential.\n"
    )

    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("agreement.txt", content, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    doc_id = body["documents"][0]["document_id"]

    get_resp = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    doc = get_resp.json()
    assert doc["status"] == DocumentStatus.INGESTION_READY.value
    assert doc["page_count"] == 1
    assert doc["filename"] == "agreement.txt"


@pytest.mark.asyncio
async def test_cross_tenant_document_access_returns_404(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg_a = await register_user(client, org_name="Tenant A", email="tenant_a@example.com")
    reg_b = await register_user(client, org_name="Tenant B", email="tenant_b@example.com")
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]

    upload = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files=[("files", ("private.txt", b"Tenant A confidential contract", "text/plain"))],
    )
    doc_id = upload.json()["documents"][0]["document_id"]

    denied = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_upload_surfaces_warning(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, email="dupdoc@example.com", org_name="Dup Org")
    token = reg.json()["access_token"]
    files = [("files", ("same.txt", b"duplicate content", "text/plain"))]

    first = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert first.status_code == 202

    second = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert second.status_code == 202
    result = second.json()["documents"][0]
    assert result["possible_duplicate_of"] is not None
