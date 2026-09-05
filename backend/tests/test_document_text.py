"""Tests for the document text endpoint (viewer data source)."""
import pytest
from app.models.models import DocumentStatus

from tests.conftest import register_user

SAMPLE_CONTRACT = (
    b"MASTER SERVICES AGREEMENT\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
    b"Payment. Client shall pay the Provider a total fee of $50,000 within 30 days.\n\n"
    b"Termination. Either party may terminate upon 30 days written notice.\n"
)


async def _upload(client, token, content=SAMPLE_CONTRACT, filename="agreement.txt"):
    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", (filename, content, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["documents"][0]["document_id"]


@pytest.mark.asyncio
async def test_document_text_returns_pages(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, email="text@example.com", org_name="Text Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/text",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["document_id"] == doc_id
    assert body["page_count"] >= 1
    assert len(body["pages"]) >= 1

    page = body["pages"][0]
    assert page["page_number"] == 1
    all_text = "\n".join(block["text"] for block in page["blocks"])
    assert "MASTER SERVICES AGREEMENT" in all_text
    assert "Acme Corp" in all_text
    for block in page["blocks"]:
        assert block["chunk_index"] >= 0
        assert block["text"]


@pytest.mark.asyncio
async def test_document_text_not_ready_returns_409(client, monkeypatch):
    async def _defer(document_id):
        return None

    monkeypatch.setattr("app.services.document_service.enqueue_ingestion", _defer)

    reg = await register_user(client, email="textpending@example.com", org_name="Pending Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token, content=b"still queued")

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/text",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "document_not_ready"


@pytest.mark.asyncio
async def test_document_text_cross_tenant_returns_404(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg_a = await register_user(client, org_name="Text Tenant A", email="text_a@example.com")
    reg_b = await register_user(client, org_name="Text Tenant B", email="text_b@example.com")
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]
    doc_id = await _upload(client, token_a)

    denied = await client.get(
        f"/api/v1/documents/{doc_id}/text",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_document_text_requires_auth(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, email="textauth@example.com", org_name="Auth Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    resp = await client.get(f"/api/v1/documents/{doc_id}/text")
    assert resp.status_code == 401
