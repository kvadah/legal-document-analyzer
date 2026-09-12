"""Phase 7 document-relationship tests — CRUD, RBAC, inference, tenancy."""
import pytest

from tests.conftest import register_user

MSA_CONTENT = (
    b"MASTER SERVICES AGREEMENT\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
    b"Payment. Client shall pay the Provider a total fee of $50,000 within 30 days of invoice.\n"
)

AMENDMENT_CONTENT = (
    b"FIRST AMENDMENT\n\n"
    b"This Amendment modifies the Master Services Agreement dated January 1, 2025 "
    b"between Acme Corp and Beta LLC.\n\n"
    b"The payment fee is hereby reduced to $40,000.\n"
)

UNRELATED_CONTENT = (
    b"NON-DISCLOSURE AGREEMENT\n\n"
    b"Between Gamma Inc and Delta LLC. Confidential information shall be protected.\n"
)


async def _upload(client, token, filename, content):
    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", (filename, content, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["documents"][0]["document_id"]


async def _invite_and_accept(client, admin_token, email, role):
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
    return accept.json()["access_token"]


async def _list_relationships(client, token, doc_id):
    resp = await client.get(
        f"/api/v1/documents/{doc_id}/relationships",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["relationships"]


@pytest.mark.asyncio
async def test_create_and_list_relationship(client):
    reg = await register_user(client, email="rel@example.com", org_name="Rel Org")
    token = reg.json()["access_token"]
    msa_id = await _upload(client, token, "Master Services Agreement.txt", MSA_CONTENT)
    amendment_id = await _upload(client, token, "amendment.txt", AMENDMENT_CONTENT)

    create = await client.post(
        f"/api/v1/documents/{amendment_id}/relationships",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "related_document_id": msa_id,
            "relationship_type": "amendment",
        },
    )
    assert create.status_code == 201, create.text
    entry = create.json()
    assert entry["relationship_type"] == "amendment"
    assert entry["direction"] == "outgoing"
    assert entry["other_document_id"] == msa_id
    assert entry["suggested"] is False

    # Listed from the amendment (outgoing)…
    from_amendment = await _list_relationships(client, token, amendment_id)
    assert len(from_amendment) == 1
    assert from_amendment[0]["direction"] == "outgoing"
    assert from_amendment[0]["other_document_id"] == msa_id

    # …and from the MSA (incoming).
    from_msa = await _list_relationships(client, token, msa_id)
    assert len(from_msa) == 1
    assert from_msa[0]["direction"] == "incoming"
    assert from_msa[0]["other_document_id"] == amendment_id


@pytest.mark.asyncio
async def test_duplicate_relationship_rejected(client):
    reg = await register_user(client, email="rel2@example.com", org_name="Rel2 Org")
    token = reg.json()["access_token"]
    doc_a = await _upload(client, token, "a.txt", MSA_CONTENT)
    doc_b = await _upload(client, token, "b.txt", UNRELATED_CONTENT)

    first = await client.post(
        f"/api/v1/documents/{doc_a}/relationships",
        headers={"Authorization": f"Bearer {token}"},
        json={"related_document_id": doc_b, "relationship_type": "related_agreement"},
    )
    assert first.status_code == 201

    same_direction = await client.post(
        f"/api/v1/documents/{doc_a}/relationships",
        headers={"Authorization": f"Bearer {token}"},
        json={"related_document_id": doc_b, "relationship_type": "supersedes"},
    )
    assert same_direction.status_code == 409

    reverse = await client.post(
        f"/api/v1/documents/{doc_b}/relationships",
        headers={"Authorization": f"Bearer {token}"},
        json={"related_document_id": doc_a, "relationship_type": "supersedes"},
    )
    assert reverse.status_code == 409


@pytest.mark.asyncio
async def test_self_relationship_rejected(client):
    reg = await register_user(client, email="rel3@example.com", org_name="Rel3 Org")
    token = reg.json()["access_token"]
    doc_a = await _upload(client, token, "a.txt", MSA_CONTENT)
    resp = await client.post(
        f"/api/v1/documents/{doc_a}/relationships",
        headers={"Authorization": f"Bearer {token}"},
        json={"related_document_id": doc_a, "relationship_type": "related_agreement"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_viewer_cannot_create_but_can_list(client):
    reg = await register_user(client, email="rel4@example.com", org_name="Rel4 Org")
    admin_token = reg.json()["access_token"]
    viewer_token = await _invite_and_accept(
        client, admin_token, "rel4-viewer@example.com", "viewer"
    )

    doc_a = await _upload(client, admin_token, "a.txt", MSA_CONTENT)
    doc_b = await _upload(client, admin_token, "b.txt", UNRELATED_CONTENT)

    denied = await client.post(
        f"/api/v1/documents/{doc_a}/relationships",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"related_document_id": doc_b, "relationship_type": "related_agreement"},
    )
    assert denied.status_code == 403

    allowed = await client.get(
        f"/api/v1/documents/{doc_a}/relationships",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_delete_relationship(client):
    reg = await register_user(client, email="rel5@example.com", org_name="Rel5 Org")
    token = reg.json()["access_token"]
    doc_a = await _upload(client, token, "a.txt", MSA_CONTENT)
    doc_b = await _upload(client, token, "b.txt", UNRELATED_CONTENT)

    create = await client.post(
        f"/api/v1/documents/{doc_a}/relationships",
        headers={"Authorization": f"Bearer {token}"},
        json={"related_document_id": doc_b, "relationship_type": "related_agreement"},
    )
    relationship_id = create.json()["relationship_id"]

    deleted = await client.delete(
        f"/api/v1/relationships/{relationship_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 204
    assert await _list_relationships(client, token, doc_a) == []


@pytest.mark.asyncio
async def test_inference_creates_suggestion_requiring_confirmation(client):
    """A document whose text names another corpus document produces an
    unconfirmed suggestion — never a silent link (08 §2)."""
    reg = await register_user(client, email="rel6@example.com", org_name="Rel6 Org")
    token = reg.json()["access_token"]
    msa_id = await _upload(client, token, "Master Services Agreement.txt", MSA_CONTENT)
    amendment_id = await _upload(client, token, "First Amendment.txt", AMENDMENT_CONTENT)

    relationships = await _list_relationships(client, token, amendment_id)
    suggestions = [r for r in relationships if r["suggested"]]
    assert len(suggestions) == 1, relationships
    suggestion = suggestions[0]
    assert suggestion["other_document_id"] == msa_id
    assert suggestion["relationship_type"] == "amendment"

    confirm = await client.post(
        f"/api/v1/relationships/{suggestion['relationship_id']}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert confirm.status_code == 204

    refreshed = await _list_relationships(client, token, amendment_id)
    assert len(refreshed) == 1
    assert refreshed[0]["suggested"] is False

    # Dismissing a suggestion removes it.
    dismiss = await client.delete(
        f"/api/v1/relationships/{suggestion['relationship_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dismiss.status_code == 204
    assert await _list_relationships(client, token, amendment_id) == []


@pytest.mark.asyncio
async def test_inference_ignores_unrelated_documents(client):
    reg = await register_user(client, email="rel7@example.com", org_name="Rel7 Org")
    token = reg.json()["access_token"]
    await _upload(client, token, "Master Services Agreement.txt", MSA_CONTENT)
    nda_id = await _upload(client, token, "nda.txt", UNRELATED_CONTENT)

    assert await _list_relationships(client, token, nda_id) == []


@pytest.mark.asyncio
async def test_relationships_cross_tenant_isolated(client):
    reg_a = await register_user(client, org_name="Rel Tenant A", email="rel_a@example.com")
    reg_b = await register_user(client, org_name="Rel Tenant B", email="rel_b@example.com")
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]

    doc_a1 = await _upload(client, token_a, "Master Services Agreement.txt", MSA_CONTENT)
    doc_a2 = await _upload(client, token_a, "First Amendment.txt", AMENDMENT_CONTENT)
    doc_b = await _upload(client, token_b, "b.txt", UNRELATED_CONTENT)

    # Inferred suggestion stays inside org A…
    rel_a = await _list_relationships(client, token_a, doc_a2)
    assert len(rel_a) == 1

    # …and org B cannot see or create relationships against A's documents.
    cross_list = await client.get(
        f"/api/v1/documents/{doc_a1}/relationships",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert cross_list.status_code == 404
    cross = await client.post(
        f"/api/v1/documents/{doc_b}/relationships",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"related_document_id": doc_a1, "relationship_type": "related_agreement"},
    )
    assert cross.status_code == 404

    # Org B cannot confirm/delete org A's relationship.
    relationship_id = rel_a[0]["relationship_id"]
    confirm = await client.post(
        f"/api/v1/relationships/{relationship_id}/confirm",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert confirm.status_code == 404
    deleted = await client.delete(
        f"/api/v1/relationships/{relationship_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert deleted.status_code == 404
