"""Phase 5 export tests — PDF / DOCX / JSON."""
import io
import json
import zipfile

import pytest

from tests.conftest import register_user

SAMPLE_CONTRACT = (
    b"MASTER SERVICES AGREEMENT\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
    b"Payment. Client shall pay the Provider a total fee of $50,000 within 30 days of invoice.\n\n"
    b"Confidentiality. Each party shall keep information confidential.\n\n"
    b"Termination. Either party may terminate upon 30 days written notice.\n"
)


async def _upload(client, token):
    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("agreement.txt", SAMPLE_CONTRACT, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["documents"][0]["document_id"]


@pytest.mark.asyncio
async def test_export_json(client):
    reg = await register_user(client, email="exp@example.com", org_name="Exp Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/export",
        headers={"Authorization": f"Bearer {token}"},
        params={"format": "json"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/json")
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.headers["content-disposition"].endswith('.json"')

    body = json.loads(resp.content)
    assert body["document"]["id"] == doc_id
    assert body["document"]["filename"] == "agreement.txt"
    for section in ("summary", "clauses", "risks", "obligations", "entities", "score"):
        assert section in body
    assert body["summary"]["contract_value"] == 50000.0
    assert "not legal advice" in body["disclaimer"]


@pytest.mark.asyncio
async def test_export_pdf(client):
    reg = await register_user(client, email="exp2@example.com", org_name="Exp2 Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/export",
        headers={"Authorization": f"Bearer {token}"},
        params={"format": "pdf"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"].endswith('.pdf"')
    assert resp.content.startswith(b"%PDF")
    assert b"%%EOF" in resp.content


@pytest.mark.asyncio
async def test_export_docx(client):
    reg = await register_user(client, email="exp3@example.com", org_name="Exp3 Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/export",
        headers={"Authorization": f"Bearer {token}"},
        params={"format": "docx"},
    )
    assert resp.status_code == 200
    assert "wordprocessingml" in resp.headers["content-type"]
    assert resp.headers["content-disposition"].endswith('.docx"')

    archive = zipfile.ZipFile(io.BytesIO(resp.content))
    names = archive.namelist()
    assert "word/document.xml" in names
    assert "[Content_Types].xml" in names
    document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "agreement.txt" in document_xml
    assert "not legal advice" in document_xml


@pytest.mark.asyncio
async def test_export_invalid_format_returns_400(client):
    reg = await register_user(client, email="exp4@example.com", org_name="Exp4 Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/export",
        headers={"Authorization": f"Bearer {token}"},
        params={"format": "rtf"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_export_requires_analysis_ready(client, monkeypatch):
    async def _defer(document_id):
        return None

    monkeypatch.setattr("app.workers.pool.enqueue_ai_pipeline", _defer)

    reg = await register_user(client, email="exp5@example.com", org_name="Exp5 Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/export",
        headers={"Authorization": f"Bearer {token}"},
        params={"format": "json"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "document_not_ready"


@pytest.mark.asyncio
async def test_export_cross_tenant_returns_404(client):
    reg_a = await register_user(client, org_name="Exp A", email="exp_a@example.com")
    reg_b = await register_user(client, org_name="Exp B", email="exp_b@example.com")
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]
    doc_id = await _upload(client, token_a)

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/export",
        headers={"Authorization": f"Bearer {token_b}"},
        params={"format": "json"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_requires_auth(client):
    resp = await client.get(
        "/api/v1/documents/00000000-0000-0000-0000-000000000000/export",
        params={"format": "json"},
    )
    assert resp.status_code == 401
