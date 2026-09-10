"""Admin user-management tests — GET/PATCH /auth/users (10-frontend-spec.md §8)."""
import pytest
from app.models.models import User
from sqlalchemy import select

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


async def _get_user_id(db_session, email):
    result = await db_session.execute(select(User).where(User.email == email))
    return result.scalar_one().id


@pytest.mark.asyncio
async def test_admin_can_list_org_users(client):
    reg = await register_user(client, org_name="Adm Org", email="adm@example.com")
    admin_token = reg.json()["access_token"]
    await _invite_and_accept(client, admin_token, "member@example.com", "reviewer")

    resp = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    emails = {user["email"] for user in body["items"]}
    assert emails == {"adm@example.com", "member@example.com"}
    member = next(u for u in body["items"] if u["email"] == "member@example.com")
    assert member["role"] == "reviewer"
    assert member["is_active"] is True


@pytest.mark.asyncio
async def test_non_admin_cannot_list_users(client):
    reg = await register_user(client, org_name="Adm2 Org", email="adm2@example.com")
    admin_token = reg.json()["access_token"]
    viewer = await _invite_and_accept(client, admin_token, "viewer2@example.com", "viewer")
    viewer_token = viewer["access_token"]

    resp = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_change_role_and_deactivate(client, db_session):
    reg = await register_user(client, org_name="Adm4 Org", email="adm4@example.com")
    admin_token = reg.json()["access_token"]
    await _invite_and_accept(client, admin_token, "member4@example.com", "viewer")
    user_id = await _get_user_id(db_session, "member4@example.com")

    resp = await client.patch(
        f"/api/v1/auth/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "reviewer"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "reviewer"

    # Deactivate — the member can no longer log in.
    resp = await client.patch(
        f"/api/v1/auth/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "member4@example.com", "password": "password123"},
    )
    assert login.status_code == 403

    # Reactivate works too.
    resp = await client.patch(
        f"/api/v1/auth/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": True},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_admin_cannot_modify_self(client):
    reg = await register_user(client, org_name="Adm5 Org", email="adm5@example.com")
    admin_token = reg.json()["access_token"]
    admin_id = reg.json()["user"]["id"]

    resp = await client.patch(
        f"/api/v1/auth/users/{admin_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "viewer"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "cannot_modify_self"


@pytest.mark.asyncio
async def test_admin_cannot_modify_other_org_user(client, db_session):
    reg_a = await register_user(
        client, org_name="Org A", email="a-admin@example.com"
    )
    reg_b = await register_user(
        client, org_name="Org B", email="b-admin@example.com"
    )
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]
    user_b_id = reg_b.json()["user"]["id"]

    resp = await client.patch(
        f"/api/v1/auth/users/{user_b_id}",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"role": "viewer"},
    )
    assert resp.status_code == 404

    # Org A's user list never contains org B's users.
    listing = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    emails = {u["email"] for u in listing.json()["items"]}
    assert "b-admin@example.com" not in emails
    # token_b still works (no accidental modification)
    assert (
        await client.get(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {token_b}"},
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_update_user_requires_admin(client):
    reg = await register_user(client, org_name="Adm6 Org", email="adm6@example.com")
    admin_token = reg.json()["access_token"]
    viewer = await _invite_and_accept(client, admin_token, "viewer6@example.com", "viewer")
    viewer_token = viewer["access_token"]

    resp = await client.patch(
        "/api/v1/auth/users/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"role": "admin"},
    )
    assert resp.status_code == 403
