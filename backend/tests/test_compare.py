"""Phase 6 comparison API tests — endpoints, RBAC, tenancy, readiness."""
from uuid import UUID

import pytest
from app.models.models import Document, DocumentStatus
from sqlalchemy import select

from tests.conftest import register_user

# Hand-annotated pair (13-roadmap-build-order.md Phase 6 acceptance):
# payment modified, confidentiality unchanged, termination removed (A only),
# arbitration added (B only); title + recital change outside clause types.
# NOTE: titles are mixed-case — all-caps lines are parsed as section headings
# and prefixed onto every following paragraph, which would pollute the diff.
DOC_A = (
    b"Acme Master Services Agreement (Original)\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
    b"The Client shall pay the Provider a total fee of $50,000 within 30 days of "
    b"receipt of invoice.\n\n"
    b"Each party shall keep all proprietary information strictly confidential and secure.\n\n"
    b"Either party may terminate this Agreement upon 30 days written notice.\n\n"
    b"WHEREAS the parties desire to establish a strategic partnership for mutual benefit.\n"
)

DOC_B = (
    b"Acme Master Services Agreement (Revised)\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
    b"The Client shall pay the Provider a total fee of $75,000 within 45 days of "
    b"receipt of invoice.\n\n"
    b"Each party shall keep all proprietary information strictly confidential and secure.\n\n"
    b"Any dispute arising under this Agreement shall be resolved by binding arbitration "
    b"in New York.\n\n"
    b"WHEREAS the parties desire to establish a joint venture for mutual growth.\n"
)


async def _upload(client, token, filename, content):
    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", (filename, content, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["documents"][0]["document_id"]


async def _compare(client, token, doc_a, doc_b):
    return await client.post(
        "/api/v1/compare",
        headers={"Authorization": f"Bearer {token}"},
        json={"document_id_a": doc_a, "document_id_b": doc_b},
    )


async def _setup_pair(client, token):
    doc_a = await _upload(client, token, "msa-v1.txt", DOC_A)
    doc_b = await _upload(client, token, "msa-v2.txt", DOC_B)
    return doc_a, doc_b


@pytest.mark.asyncio
async def test_compare_classifies_added_removed_modified_unchanged(client):
    reg = await register_user(client, email="cmp@example.com", org_name="Cmp Org")
    token = reg.json()["access_token"]
    doc_a, doc_b = await _setup_pair(client, token)

    resp = await _compare(client, token, doc_a, doc_b)
    assert resp.status_code == 202, resp.text
    comparison_id = resp.json()["comparison_id"]

    resp = await client.get(
        f"/api/v1/compare/{comparison_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["document_a"]["filename"] == "msa-v1.txt"
    assert body["document_b"]["filename"] == "msa-v2.txt"

    by_type = {entry["clause_type"]: entry for entry in body["clauses"]}
    assert by_type["payment"]["status"] == "modified"
    assert by_type["confidentiality"]["status"] == "unchanged"
    assert by_type["termination"]["status"] == "removed"
    assert by_type["arbitration"]["status"] == "added"

    counts = body["counts"]
    assert counts == {
        "added": 1,
        "removed": 1,
        "modified": 1,
        "unchanged": 1,
        "other_changes": 2,
    }


@pytest.mark.asyncio
async def test_compare_includes_word_level_diff(client):
    reg = await register_user(client, email="cmp2@example.com", org_name="Cmp2 Org")
    token = reg.json()["access_token"]
    doc_a, doc_b = await _setup_pair(client, token)

    resp = await _compare(client, token, doc_a, doc_b)
    comparison_id = resp.json()["comparison_id"]

    body = (
        await client.get(
            f"/api/v1/compare/{comparison_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    ).json()

    payment = next(e for e in body["clauses"] if e["clause_type"] == "payment")
    assert payment["word_diff"], "modified clause must carry a word diff"
    segments = {seg["op"] for seg in payment["word_diff"]}
    assert "equal" in segments
    assert "replace" in segments
    replaced = [seg for seg in payment["word_diff"] if seg["op"] == "replace"]
    assert any(seg["text_a"] == "$50,000" and seg["text_b"] == "$75,000" for seg in replaced)

    # Non-clause changes appear in the "Other Changes" section.
    others = body["other_changes"]
    assert all(entry["status"] == "modified" for entry in others)
    assert any("(Revised)" in (entry["text_b"] or "") for entry in others)
    assert any("joint venture" in (entry["text_b"] or "") for entry in others)
    # Clause-covered paragraphs must not be duplicated in Other Changes.
    assert not any("terminat" in (entry["text_a"] or "").lower() for entry in others)
    assert not any("arbitration" in (entry["text_b"] or "").lower() for entry in others)


@pytest.mark.asyncio
async def test_compare_same_document_rejected(client):
    reg = await register_user(client, email="cmp3@example.com", org_name="Cmp3 Org")
    token = reg.json()["access_token"]
    doc_a, _ = await _setup_pair(client, token)

    resp = await _compare(client, token, doc_a, doc_a)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "same_document"


@pytest.mark.asyncio
async def test_compare_requires_analysis_ready(client, db_session):
    reg = await register_user(client, email="cmp4@example.com", org_name="Cmp4 Org")
    token = reg.json()["access_token"]
    doc_a, doc_b = await _setup_pair(client, token)

    # Force doc A back to ingestion_ready to simulate a not-yet-analyzed doc.
    result = await db_session.execute(select(Document).where(Document.id == UUID(doc_a)))
    db_doc = result.scalar_one()
    db_doc.status = DocumentStatus.INGESTION_READY
    await db_session.commit()

    resp = await _compare(client, token, doc_a, doc_b)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "analysis_not_ready"


@pytest.mark.asyncio
async def test_compare_requires_reviewer_role(client):
    reg = await register_user(client, email="cmp5@example.com", org_name="Cmp5 Org")
    admin_token = reg.json()["access_token"]
    doc_a, doc_b = await _setup_pair(client, admin_token)

    invite = await client.post(
        "/api/v1/auth/invite",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "cmp5-viewer@example.com", "role": "viewer"},
    )
    assert invite.status_code == 201, invite.text
    accept = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": invite.json()["token"], "password": "password123"},
    )
    viewer_token = accept.json()["access_token"]

    # Viewers cannot trigger comparisons (11-security-compliance.md §2)…
    resp = await _compare(client, viewer_token, doc_a, doc_b)
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "forbidden"

    # …but can read a comparison created by a reviewer/admin.
    create = await _compare(client, admin_token, doc_a, doc_b)
    comparison_id = create.json()["comparison_id"]
    resp = await client.get(
        f"/api/v1/compare/{comparison_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_compare_cross_tenant_isolation(client):
    reg_a = await register_user(client, org_name="Cmp Ten A", email="cmp_a@example.com")
    reg_b = await register_user(client, org_name="Cmp Ten B", email="cmp_b@example.com")
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]
    doc_a, doc_b = await _setup_pair(client, token_a)

    # Org B cannot reference org A's documents (invisible → 404)…
    resp = await _compare(client, token_b, doc_a, doc_b)
    assert resp.status_code == 404

    # …and cannot read org A's comparison result.
    create = await _compare(client, token_a, doc_a, doc_b)
    comparison_id = create.json()["comparison_id"]
    resp = await client.get(
        f"/api/v1/compare/{comparison_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compare_requires_auth(client):
    resp = await client.post("/api/v1/compare", json={"document_id_a": "x", "document_id_b": "y"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_compare_validates_request(client):
    reg = await register_user(client, email="cmp6@example.com", org_name="Cmp6 Org")
    token = reg.json()["access_token"]

    resp = await client.post(
        "/api/v1/compare",
        headers={"Authorization": f"Bearer {token}"},
        json={"document_id_a": "not-a-uuid", "document_id_b": "also-not-a-uuid"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_compare_unknown_document_404(client):
    reg = await register_user(client, email="cmp7@example.com", org_name="Cmp7 Org")
    token = reg.json()["access_token"]
    doc_a, _ = await _setup_pair(client, token)

    resp = await _compare(client, token, doc_a, "00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_unknown_comparison_404(client):
    reg = await register_user(client, email="cmp8@example.com", org_name="Cmp8 Org")
    token = reg.json()["access_token"]
    resp = await client.get(
        "/api/v1/compare/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
