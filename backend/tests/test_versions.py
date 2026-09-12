"""Phase 7 version-history tests — version-aware upload and chain listing."""
import pytest

from tests.conftest import register_user

V1_CONTENT = (
    b"MASTER SERVICES AGREEMENT\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
    b"Payment. Client shall pay the Provider a total fee of $50,000 within 30 days of invoice.\n"
)

V2_CONTENT = (
    b"MASTER SERVICES AGREEMENT (v2)\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
    b"Payment. Client shall pay the Provider a total fee of $40,000 within 15 days of invoice.\n"
)


async def _upload(client, token, filename, content):
    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", (filename, content, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["documents"][0]["document_id"]


async def _upload_version(client, token, parent_id, filename, content, change_note=None):
    data = {"file": (filename, content, "text/plain")}
    if change_note is not None:
        data["change_note"] = (None, change_note)
    resp = await client.post(
        f"/api/v1/documents/{parent_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        files=data,
    )
    return resp


@pytest.mark.asyncio
async def test_upload_new_version_links_chain(client):
    reg = await register_user(client, email="ver@example.com", org_name="Version Org")
    token = reg.json()["access_token"]
    v1_id = await _upload(client, token, "msa.txt", V1_CONTENT)

    resp = await _upload_version(
        client, token, v1_id, "msa_v2.txt", V2_CONTENT, "Reduced fee and shorter payment window"
    )
    assert resp.status_code == 202, resp.text
    v2_id = resp.json()["document_id"]
    assert v2_id != v1_id

    v2 = await client.get(
        f"/api/v1/documents/{v2_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v2.status_code == 200
    assert v2.json()["parent_document_id"] == v1_id

    listing = await client.get(
        f"/api/v1/documents/{v1_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["root_document_id"] == v1_id
    assert [v["version_number"] for v in body["versions"]] == [1, 2]
    assert [v["document_id"] for v in body["versions"]] == [v1_id, v2_id]
    assert body["versions"][1]["change_note"] == "Reduced fee and shorter payment window"
    assert body["versions"][1]["is_current"] is False
    assert body["versions"][0]["is_current"] is True


@pytest.mark.asyncio
async def test_version_has_own_analysis(client):
    """Each version is a distinct document with its own pipeline run."""
    reg = await register_user(client, email="ver2@example.com", org_name="Version2 Org")
    token = reg.json()["access_token"]
    v1_id = await _upload(client, token, "msa.txt", V1_CONTENT)

    resp = await _upload_version(client, token, v1_id, "msa_v2.txt", V2_CONTENT)
    assert resp.status_code == 202, resp.text
    v2_id = resp.json()["document_id"]

    v2 = await client.get(
        f"/api/v1/documents/{v2_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v2.json()["status"] == "analysis_ready"

    summary = await client.get(
        f"/api/v1/documents/{v2_id}/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert summary.status_code == 200, summary.text


@pytest.mark.asyncio
async def test_version_numbers_increment_across_chain(client):
    reg = await register_user(client, email="ver3@example.com", org_name="Version3 Org")
    token = reg.json()["access_token"]
    v1_id = await _upload(client, token, "msa.txt", V1_CONTENT)

    v2_resp = await _upload_version(client, token, v1_id, "msa_v2.txt", V2_CONTENT, "v2")
    v2_id = v2_resp.json()["document_id"]

    # Uploading against v2 (a non-root chain member) must resolve to the same chain.
    v3_resp = await _upload_version(client, token, v2_id, "msa_v3.txt", V2_CONTENT, "v3")
    assert v3_resp.status_code == 202, v3_resp.text
    v3_id = v3_resp.json()["document_id"]

    v3 = await client.get(
        f"/api/v1/documents/{v3_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v3.json()["parent_document_id"] == v1_id  # anchored to the root

    listing = await client.get(
        f"/api/v1/documents/{v3_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert [v["version_number"] for v in listing.json()["versions"]] == [1, 2, 3]


@pytest.mark.asyncio
async def test_versions_cross_tenant_isolated(client):
    reg_a = await register_user(client, org_name="Ver Tenant A", email="ver_a@example.com")
    reg_b = await register_user(client, org_name="Ver Tenant B", email="ver_b@example.com")
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]
    doc_a = await _upload(client, token_a, "msa.txt", V1_CONTENT)

    # Org B cannot upload a version onto org A's document…
    resp = await _upload_version(client, token_b, doc_a, "steal.txt", V2_CONTENT)
    assert resp.status_code == 404

    # …nor see A's version history.
    listing = await client.get(
        f"/api/v1/documents/{doc_a}/versions",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert listing.status_code == 404


@pytest.mark.asyncio
async def test_version_upload_validates_file_type(client):
    reg = await register_user(client, email="ver4@example.com", org_name="Version4 Org")
    token = reg.json()["access_token"]
    v1_id = await _upload(client, token, "msa.txt", V1_CONTENT)

    resp = await _upload_version(client, token, v1_id, "evil.exe", b"MZ\x90\x00")
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_viewer_cannot_upload_version(client):
    """Version upload is reviewer-level (08-feature-spec-collaboration.md §8)."""
    reg = await register_user(client, email="ver6@example.com", org_name="Version6 Org")
    admin_token = reg.json()["access_token"]
    v1_id = await _upload(client, admin_token, "msa.txt", V1_CONTENT)

    invite = await client.post(
        "/api/v1/auth/invite",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "ver6-viewer@example.com", "role": "viewer"},
    )
    assert invite.status_code == 201, invite.text
    accept = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": invite.json()["token"], "password": "password123"},
    )
    viewer_token = accept.json()["access_token"]

    resp = await _upload_version(client, viewer_token, v1_id, "msa_v2.txt", V2_CONTENT)
    assert resp.status_code == 403

    # …but listing versions stays available to any org member.
    listing = await client.get(
        f"/api/v1/documents/{v1_id}/versions",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert listing.status_code == 200


@pytest.mark.asyncio
async def test_version_of_missing_document_404(client):
    reg = await register_user(client, email="ver5@example.com", org_name="Version5 Org")
    token = reg.json()["access_token"]
    resp = await _upload_version(
        client, token, "00000000-0000-0000-0000-000000000000", "x.txt", V2_CONTENT
    )
    assert resp.status_code == 404
