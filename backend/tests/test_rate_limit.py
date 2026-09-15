"""Rate limiting tests (09-api-spec.md §12) — upload per-org, search/Q&A
per-user, 429 + Retry-After behavior, and disable switch."""
import pytest
from app.core.config import settings

from tests.conftest import register_user


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def rate_limits_on(monkeypatch):
    """Enable rate limiting with tiny limits for fast tests."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "upload_rate_limit_per_hour", 2)
    monkeypatch.setattr(settings, "search_rate_limit_per_minute", 3)


async def _upload(client, token, name):
    return await client.post(
        "/api/v1/documents/upload",
        headers=_auth(token),
        files=[("files", (name, b"MSA content", "text/plain"))],
    )


@pytest.mark.asyncio
async def test_upload_rate_limited_per_org(client, rate_limits_on):
    reg = await register_user(client, org_name="RL Org", email="rl@example.com")
    token = reg.json()["access_token"]

    assert (await _upload(client, token, "a.txt")).status_code == 202
    assert (await _upload(client, token, "b.txt")).status_code == 202

    third = await _upload(client, token, "c.txt")
    assert third.status_code == 429, third.text
    assert third.json()["detail"]["code"] == "rate_limited"
    retry_after = third.headers.get("Retry-After")
    assert retry_after is not None and int(retry_after) > 0


@pytest.mark.asyncio
async def test_upload_limit_is_shared_across_org_members(client, rate_limits_on):
    reg = await register_user(client, org_name="RL2 Org", email="rl2@example.com")
    admin_token = reg.json()["access_token"]
    invite = await client.post(
        "/api/v1/auth/invite",
        headers=_auth(admin_token),
        json={"email": "rl2-rev@example.com", "role": "reviewer"},
    )
    accept = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": invite.json()["token"], "password": "password123"},
    )
    reviewer_token = accept.json()["access_token"]

    # Org budget: 2 uploads total — one from each member.
    assert (await _upload(client, admin_token, "a.txt")).status_code == 202
    assert (await _upload(client, reviewer_token, "b.txt")).status_code == 202
    assert (await _upload(client, reviewer_token, "c.txt")).status_code == 429


@pytest.mark.asyncio
async def test_upload_limit_not_shared_across_orgs(client, rate_limits_on):
    reg_a = await register_user(client, org_name="RL3 A", email="rl3a@example.com")
    reg_b = await register_user(client, org_name="RL3 B", email="rl3b@example.com")

    assert (await _upload(client, reg_a.json()["access_token"], "a.txt")).status_code == 202
    assert (await _upload(client, reg_a.json()["access_token"], "b.txt")).status_code == 202
    # A separate org has its own budget.
    assert (await _upload(client, reg_b.json()["access_token"], "c.txt")).status_code == 202


@pytest.mark.asyncio
async def test_search_rate_limited_per_user(client, rate_limits_on):
    reg = await register_user(client, org_name="RL4 Org", email="rl4@example.com")
    token = reg.json()["access_token"]

    for _ in range(3):
        resp = await client.post(
            "/api/v1/search", headers=_auth(token), json={"query": "anything", "mode": "keyword"}
        )
        assert resp.status_code == 200

    fourth = await client.post(
        "/api/v1/search", headers=_auth(token), json={"query": "anything", "mode": "keyword"}
    )
    assert fourth.status_code == 429, fourth.text
    assert fourth.json()["detail"]["code"] == "rate_limited"
    assert int(fourth.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_rate_limits_can_be_disabled(client):
    reg = await register_user(client, org_name="RL5 Org", email="rl5@example.com")
    token = reg.json()["access_token"]

    # Default test configuration has rate limits disabled — a burst of
    # uploads must all succeed.
    for i in range(5):
        assert (await _upload(client, token, f"burst-{i}.txt")).status_code == 202
