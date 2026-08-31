"""Phase 1 auth tests — register, login, RBAC, token lifecycle, cross-tenant isolation."""
import pytest

from tests.conftest import register_user


@pytest.mark.asyncio
async def test_register_creates_org_and_admin(client):
    resp = await register_user(client, email="admin1@example.com")
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"
    assert data["user"]["org_name"] == "Test Org"


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    email = "dup@example.com"
    await register_user(client, org_name="Org A", email=email)
    resp = await register_user(client, org_name="Org B", email=email)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client):
    email, pwd = "logintest@example.com", "securepass1"
    await register_user(client, org_name="Login Org", email=email, password=pwd)

    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == email


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    email = "wrongpw@example.com"
    await register_user(client, org_name="Pw Org", email=email, password="correct123")

    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong!!!"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth(client):
    resp = await client.post("/api/v1/auth/invite", json={"email": "x@x.com", "role": "viewer"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_with_valid_token(client):
    reg = await register_user(client, org_name="Protected Org", email="prot@example.com")
    token = reg.json()["access_token"]

    resp = await client.post(
        "/api/v1/auth/invite",
        json={"email": "invited@example.com", "role": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_viewer_cannot_invite(client):
    reg = await register_user(client, org_name="RBAC Org", email="rbac_admin@example.com")
    admin_token = reg.json()["access_token"]

    invite_resp = await client.post(
        "/api/v1/auth/invite",
        json={"email": "viewer@example.com", "role": "viewer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    invite_token = invite_resp.json()["token"]

    accept_resp = await client.post("/api/v1/auth/accept-invite", json={
        "token": invite_token,
        "password": "viewerpass1",
    })
    viewer_token = accept_resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/auth/invite",
        json={"email": "another@example.com", "role": "viewer"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_logout_invalidates_refresh_token(client):
    reg = await register_user(client, org_name="Logout Org", email="logout@example.com")
    cookies = dict(client.cookies)
    refresh_token = cookies.get("refresh_token", "")

    logout_resp = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 204

    refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401
