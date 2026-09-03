"""Phase 3 AI pipeline tests."""
import pytest
from app.models.models import DocumentStatus

from tests.conftest import register_user

SAMPLE_CONTRACT = (
    b"MASTER SERVICES AGREEMENT\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC effective March 1, 2024.\n\n"
    b"Payment. Client shall pay the Provider a total fee of $50,000 within 30 days of invoice.\n\n"
    b"Confidentiality. Each party shall keep information confidential.\n\n"
    b"Termination. Either party may terminate upon 30 days written notice.\n\n"
    b"Liability. Provider shall be responsible for all damages arising from performance.\n\n"
    b"Renewal. This Agreement shall automatically renew for successive one-year terms.\n\n"
    b"Governing law. This Agreement shall be governed by the laws of the State of New York.\n\n"
    b"Provider shall use reasonable efforts to complete deliverables as soon as practicable.\n"
)


@pytest.mark.asyncio
async def test_full_ai_pipeline_reaches_analysis_ready(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, email="ai@example.com", org_name="AI Org")
    token = reg.json()["access_token"]

    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("agreement.txt", SAMPLE_CONTRACT, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    doc_id = resp.json()["documents"][0]["document_id"]

    get_resp = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    doc = get_resp.json()
    assert doc["status"] == DocumentStatus.ANALYSIS_READY.value
    assert doc["contract_score"] is not None
    assert doc["ai_confidence_score"] is not None


@pytest.mark.asyncio
async def test_clause_detection_and_absence(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, email="clauses@example.com", org_name="Clause Org")
    token = reg.json()["access_token"]
    upload = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("agreement.txt", SAMPLE_CONTRACT, "text/plain"))],
    )
    doc_id = upload.json()["documents"][0]["document_id"]

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/clauses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    found_types = {item["clause_type"] for item in body["items"]}
    assert "termination" in found_types
    assert "confidentiality" in found_types
    assert "payment" in found_types
    assert "liability" in found_types
    assert "force_majeure" in body["not_found"]
    assert "indemnification" in body["not_found"]

    for item in body["items"]:
        assert item["extracted_text"]
        assert item["page_number"] >= 1
        assert item["confidence_score"] is not None


@pytest.mark.asyncio
async def test_risk_detection_rules_and_llm(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, email="risks@example.com", org_name="Risk Org")
    token = reg.json()["access_token"]
    upload = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("agreement.txt", SAMPLE_CONTRACT, "text/plain"))],
    )
    doc_id = upload.json()["documents"][0]["document_id"]

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/risks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    risks = {item["risk_type"]: item for item in resp.json()["items"]}

    assert "unlimited_liability" in risks
    assert risks["unlimited_liability"]["severity"] == "high"
    assert "auto_renewal" in risks
    assert "ambiguous_language" in risks
    assert "missing_termination" not in risks
    assert "no_governing_law" not in risks

    recommendation = risks["unlimited_liability"]["recommendation"]
    assert recommendation and "consider" in recommendation.lower()


@pytest.mark.asyncio
async def test_entities_and_summary(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, email="ents@example.com", org_name="Entity Org")
    token = reg.json()["access_token"]
    upload = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("agreement.txt", SAMPLE_CONTRACT, "text/plain"))],
    )
    doc_id = upload.json()["documents"][0]["document_id"]

    entity_resp = await client.get(
        f"/api/v1/documents/{doc_id}/entities",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert entity_resp.status_code == 200
    groups = {g["entity_type"]: g["items"] for g in entity_resp.json()["groups"]}
    assert "company" in groups
    company_values = {e["value"] for e in groups["company"]}
    assert "Acme Corp" in company_values or "Acme Corp." in company_values
    assert "money" in groups
    assert "date" in groups

    summary_resp = await client.get(
        f"/api/v1/documents/{doc_id}/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["purpose"]
    assert summary["governing_law"]
    assert summary["contract_value"] == 50000.0
    assert summary["effective_date"] == "2024-03-01"
    party_names = {p["name"] for p in summary["parties"]}
    assert "Acme Corp" in party_names


@pytest.mark.asyncio
async def test_score_endpoint_with_breakdown(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, email="score@example.com", org_name="Score Org")
    token = reg.json()["access_token"]
    upload = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("agreement.txt", SAMPLE_CONTRACT, "text/plain"))],
    )
    doc_id = upload.json()["documents"][0]["document_id"]

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/score",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert 0 <= body["contract_score"] <= 100
    assert body["contract_score"] < 100
    assert 0 < body["ai_confidence_score"] <= 1
    assert body["scores_version"] >= 1
    assert body["total_deduction"] > 0
    assert len(body["breakdown"]) >= 1
    assert sum(item["deduction"] for item in body["breakdown"]) == body["total_deduction"]
    assert 100 - body["total_deduction"] == body["contract_score"]


@pytest.mark.asyncio
async def test_risk_status_patch(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, email="patch@example.com", org_name="Patch Org")
    token = reg.json()["access_token"]
    upload = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("agreement.txt", SAMPLE_CONTRACT, "text/plain"))],
    )
    doc_id = upload.json()["documents"][0]["document_id"]

    risks_resp = await client.get(
        f"/api/v1/documents/{doc_id}/risks",
        headers={"Authorization": f"Bearer {token}"},
    )
    risk_id = risks_resp.json()["items"][0]["id"]

    patch_resp = await client.patch(
        f"/api/v1/documents/{doc_id}/risks/{risk_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "acknowledged"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_analysis_cross_tenant_isolation(client, monkeypatch):
    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg_a = await register_user(client, org_name="Tenant A2", email="ai_tenant_a@example.com")
    reg_b = await register_user(client, org_name="Tenant B2", email="ai_tenant_b@example.com")
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]

    upload = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files=[("files", ("private.txt", SAMPLE_CONTRACT, "text/plain"))],
    )
    doc_id = upload.json()["documents"][0]["document_id"]

    for path in ("clauses", "risks", "entities", "obligations", "summary", "score"):
        resp = await client.get(
            f"/api/v1/documents/{doc_id}/{path}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404, f"{path} leaked across tenants: {resp.status_code}"


@pytest.mark.asyncio
async def test_analysis_not_ready_returns_409(client, monkeypatch):
    async def _defer_ai(document_id):
        return None

    monkeypatch.setattr("app.workers.pool.enqueue_ai_pipeline", _defer_ai)

    async def _noop(points):
        return None

    monkeypatch.setattr("app.pipelines.ingestion.pipeline._upsert_qdrant_points", _noop)

    reg = await register_user(client, email="notready@example.com", org_name="NotReady Org")
    token = reg.json()["access_token"]
    upload = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("agreement.txt", SAMPLE_CONTRACT, "text/plain"))],
    )
    doc_id = upload.json()["documents"][0]["document_id"]

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/clauses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "analysis_not_ready"
