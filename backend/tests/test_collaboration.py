"""Phase 9 collaboration tests — comments, annotations, RBAC, tenancy.

Includes the roadmap acceptance criterion: two users in the same org can
comment/annotate on the same document and see each other's additions.
"""
import pytest

from tests.conftest import register_user

SAMPLE_CONTRACT = (
    b"MASTER SERVICES AGREEMENT\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
    b"Payment. Client shall pay the Provider a total fee of $50,000 within 30 days of invoice.\n"
)

OTHER_CONTRACT = (
    b"NON-DISCLOSURE AGREEMENT\n\n"
    b"Between Gamma Inc and Delta LLC. Confidential information shall be protected.\n"
)


async def _upload(client, token, filename="contract.txt", content=SAMPLE_CONTRACT):
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


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _list_comments(client, token, doc_id):
    resp = await client.get(
        f"/api/v1/documents/{doc_id}/comments", headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["comments"]


async def _list_annotations(client, token, doc_id):
    resp = await client.get(
        f"/api/v1/documents/{doc_id}/annotations", headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["annotations"]


# ── Comments ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_comment_create_list_resolve(client):
    reg = await register_user(client, email="col@example.com", org_name="Col Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    created = await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        headers=_auth(token),
        json={"content": "This clause needs partner sign-off.", "page_number": 1},
    )
    assert created.status_code == 201, created.text
    comment = created.json()
    assert comment["resolved"] is False
    assert comment["author_email"] == "col@example.com"
    assert comment["page_number"] == 1

    listed = await _list_comments(client, token, doc_id)
    assert len(listed) == 1
    assert listed[0]["id"] == comment["id"]

    resolved = await client.patch(
        f"/api/v1/comments/{comment['id']}",
        headers=_auth(token),
        json={"resolved": True},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["resolved"] is True


@pytest.mark.asyncio
async def test_threaded_replies_and_cascade_delete(client):
    reg = await register_user(client, email="col2@example.com", org_name="Col2 Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    parent = (
        await client.post(
            f"/api/v1/documents/{doc_id}/comments",
            headers=_auth(token),
            json={"content": "Question about the payment terms"},
        )
    ).json()
    reply = (
        await client.post(
            f"/api/v1/documents/{doc_id}/comments",
            headers=_auth(token),
            json={
                "content": "It mirrors the MSA from last year",
                "parent_comment_id": parent["id"],
            },
        )
    ).json()
    assert reply["parent_comment_id"] == parent["id"]

    # Deleting the parent removes its replies too (no orphans).
    deleted = await client.delete(
        f"/api/v1/comments/{parent['id']}", headers=_auth(token)
    )
    assert deleted.status_code == 204
    assert await _list_comments(client, token, doc_id) == []


@pytest.mark.asyncio
async def test_reply_across_documents_rejected(client):
    reg = await register_user(client, email="col3@example.com", org_name="Col3 Org")
    token = reg.json()["access_token"]
    doc_a = await _upload(client, token, "a.txt")
    doc_b = await _upload(client, token, "b.txt", OTHER_CONTRACT)

    parent = (
        await client.post(
            f"/api/v1/documents/{doc_a}/comments",
            headers=_auth(token),
            json={"content": "Root comment"},
        )
    ).json()
    cross = await client.post(
        f"/api/v1/documents/{doc_b}/comments",
        headers=_auth(token),
        json={"content": "Reply", "parent_comment_id": parent["id"]},
    )
    assert cross.status_code == 400


@pytest.mark.asyncio
async def test_comment_edit_author_only(client):
    reg = await register_user(client, email="col4@example.com", org_name="Col4 Org")
    admin_token = reg.json()["access_token"]
    reviewer_token = await _invite_and_accept(
        client, admin_token, "col4-rev@example.com", "reviewer"
    )
    doc_id = await _upload(client, admin_token)

    comment = (
        await client.post(
            f"/api/v1/documents/{doc_id}/comments",
            headers=_auth(admin_token),
            json={"content": "Original text"},
        )
    ).json()

    denied = await client.patch(
        f"/api/v1/comments/{comment['id']}",
        headers=_auth(reviewer_token),
        json={"content": "tampered"},
    )
    assert denied.status_code == 403

    allowed = await client.patch(
        f"/api/v1/comments/{comment['id']}",
        headers=_auth(admin_token),
        json={"content": "Edited by author"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["content"] == "Edited by author"

    # Resolution, however, is the review workflow — any reviewer can toggle.
    resolve = await client.patch(
        f"/api/v1/comments/{comment['id']}",
        headers=_auth(reviewer_token),
        json={"resolved": True},
    )
    assert resolve.status_code == 200
    assert resolve.json()["resolved"] is True


# ── Annotations ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_annotation_crud_with_color(client):
    reg = await register_user(client, email="col5@example.com", org_name="Col5 Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    created = await client.post(
        f"/api/v1/documents/{doc_id}/annotations",
        headers=_auth(token),
        json={
            "highlight_text": "total fee of $50,000",
            "content": "Confirm the fee matches the SOW",
            "color": "red",
            "page_number": 1,
        },
    )
    assert created.status_code == 201, created.text
    annotation = created.json()
    assert annotation["color"] == "red"
    assert annotation["highlight_text"] == "total fee of $50,000"

    listed = await _list_annotations(client, token, doc_id)
    assert [a["id"] for a in listed] == [annotation["id"]]

    updated = await client.patch(
        f"/api/v1/annotations/{annotation['id']}",
        headers=_auth(token),
        json={"color": "green", "content": "OK after check"},
    )
    assert updated.status_code == 200
    assert updated.json()["color"] == "green"

    deleted = await client.delete(
        f"/api/v1/annotations/{annotation['id']}", headers=_auth(token)
    )
    assert deleted.status_code == 204
    assert await _list_annotations(client, token, doc_id) == []


@pytest.mark.asyncio
async def test_annotation_invalid_color_rejected(client):
    reg = await register_user(client, email="col6@example.com", org_name="Col6 Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/annotations",
        headers=_auth(token),
        json={
            "highlight_text": "text",
            "color": "hotpink",
            "page_number": 1,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_annotation_edit_author_only(client):
    reg = await register_user(client, email="col7@example.com", org_name="Col7 Org")
    admin_token = reg.json()["access_token"]
    reviewer_token = await _invite_and_accept(
        client, admin_token, "col7-rev@example.com", "reviewer"
    )
    doc_id = await _upload(client, admin_token)

    annotation = (
        await client.post(
            f"/api/v1/documents/{doc_id}/annotations",
            headers=_auth(reviewer_token),
            json={"highlight_text": "span", "page_number": 1},
        )
    ).json()

    denied = await client.patch(
        f"/api/v1/annotations/{annotation['id']}",
        headers=_auth(admin_token),
        json={"content": "not my note"},
    )
    assert denied.status_code == 403

    # Admins can still delete someone else's annotation (moderation path).
    deleted = await client.delete(
        f"/api/v1/annotations/{annotation['id']}", headers=_auth(admin_token)
    )
    assert deleted.status_code == 204


# ── RBAC + tenancy ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_viewer_reads_but_cannot_collaborate(client):
    reg = await register_user(client, email="col8@example.com", org_name="Col8 Org")
    admin_token = reg.json()["access_token"]
    viewer_token = await _invite_and_accept(
        client, admin_token, "col8-viewer@example.com", "viewer"
    )
    doc_id = await _upload(client, admin_token)

    await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        headers=_auth(admin_token),
        json={"content": "Visible to viewers too"},
    )

    can_read = await _list_comments(client, viewer_token, doc_id)
    assert len(can_read) == 1

    comment_denied = await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        headers=_auth(viewer_token),
        json={"content": "attempt"},
    )
    assert comment_denied.status_code == 403

    annotation_denied = await client.post(
        f"/api/v1/documents/{doc_id}/annotations",
        headers=_auth(viewer_token),
        json={"highlight_text": "span", "page_number": 1},
    )
    assert annotation_denied.status_code == 403


@pytest.mark.asyncio
async def test_collaboration_cross_tenant_isolated(client):
    reg_a = await register_user(client, org_name="Col Tenant A", email="col_a@example.com")
    reg_b = await register_user(client, org_name="Col Tenant B", email="col_b@example.com")
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]
    doc_a = await _upload(client, token_a)
    doc_b = await _upload(client, token_b, "b.txt", OTHER_CONTRACT)

    comment_a = (
        await client.post(
            f"/api/v1/documents/{doc_a}/comments",
            headers=_auth(token_a),
            json={"content": "internal note"},
        )
    ).json()
    annotation_a = (
        await client.post(
            f"/api/v1/documents/{doc_a}/annotations",
            headers=_auth(token_a),
            json={"highlight_text": "span", "page_number": 1},
        )
    ).json()

    # Org B sees nothing of org A's collaboration objects (404 — the
    # document is indistinguishable from a nonexistent one)…
    cross_list = await client.get(
        f"/api/v1/documents/{doc_a}/comments", headers=_auth(token_b)
    )
    assert cross_list.status_code == 404

    # …cannot create on A's documents (404 — indistinguishable from missing)…
    cross_comment = await client.post(
        f"/api/v1/documents/{doc_a}/comments",
        headers=_auth(token_b),
        json={"content": "intrusion"},
    )
    assert cross_comment.status_code == 404

    # …and cannot touch A's comment/annotation by id.
    patch_cross = await client.patch(
        f"/api/v1/comments/{comment_a['id']}",
        headers=_auth(token_b),
        json={"resolved": True},
    )
    assert patch_cross.status_code == 404
    delete_cross = await client.delete(
        f"/api/v1/annotations/{annotation_a['id']}", headers=_auth(token_b)
    )
    assert delete_cross.status_code == 404

    # Org A's own view is untouched.
    assert len(await _list_comments(client, token_a, doc_a)) == 1
    assert len(await _list_annotations(client, token_a, doc_a)) == 1
    assert await _list_comments(client, token_b, doc_b) == []


@pytest.mark.asyncio
async def test_two_users_see_each_others_additions(client):
    """Roadmap Phase 9 acceptance: two org members comment/annotate on the
    same document and see each other's additions."""
    reg = await register_user(client, email="col9@example.com", org_name="Col9 Org")
    admin_token = reg.json()["access_token"]
    reviewer_token = await _invite_and_accept(
        client, admin_token, "col9-rev@example.com", "reviewer"
    )
    doc_id = await _upload(client, admin_token)

    admin_comment = (
        await client.post(
            f"/api/v1/documents/{doc_id}/comments",
            headers=_auth(admin_token),
            json={"content": "Admin's page-1 note", "page_number": 1},
        )
    ).json()
    reviewer_reply = (
        await client.post(
            f"/api/v1/documents/{doc_id}/comments",
            headers=_auth(reviewer_token),
            json={
                "content": "Reviewer agrees",
                "parent_comment_id": admin_comment["id"],
            },
        )
    ).json()
    reviewer_annotation = (
        await client.post(
            f"/api/v1/documents/{doc_id}/annotations",
            headers=_auth(reviewer_token),
            json={
                "highlight_text": "total fee of $50,000",
                "content": "Reviewer's highlight",
                "color": "blue",
                "page_number": 1,
            },
        )
    ).json()

    # Both users see both comments (with the right authors)…
    for token in (admin_token, reviewer_token):
        comments = await _list_comments(client, token, doc_id)
        assert len(comments) == 2
        by_email = {c["author_email"]: c for c in comments}
        assert by_email["col9@example.com"]["id"] == admin_comment["id"]
        assert by_email["col9-rev@example.com"]["id"] == reviewer_reply["id"]
        assert by_email["col9-rev@example.com"]["parent_comment_id"] == admin_comment["id"]

    # …and the reviewer's annotation, including its color and author.
    annotations = await _list_annotations(client, admin_token, doc_id)
    assert [a["id"] for a in annotations] == [reviewer_annotation["id"]]
    assert annotations[0]["author_email"] == "col9-rev@example.com"
    assert annotations[0]["color"] == "blue"
