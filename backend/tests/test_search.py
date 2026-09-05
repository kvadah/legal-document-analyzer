"""Phase 5 search tests — keyword / semantic / hybrid, filters, tenancy."""
import pytest

from tests.conftest import register_user

SAMPLE_CONTRACT = (
    b"MASTER SERVICES AGREEMENT\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
    b"Payment. Client shall pay the Provider a total fee of $50,000 within 30 days of invoice.\n\n"
    b"Confidentiality. Each party shall keep information confidential.\n\n"
    b"Termination. Either party may terminate upon 30 days written notice.\n"
)

UNIQUE_TERM_CONTRACT = (
    b"SETTLEMENT AGREEMENT\n\n"
    b"The parties release each other from detrimental reliance claims.\n"
)


async def _upload(client, token, filename, content):
    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", (filename, content, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["documents"][0]["document_id"]


async def _search(client, token, body):
    return await client.post(
        "/api/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )


@pytest.mark.asyncio
async def test_keyword_search_finds_exact_terms(client):
    reg = await register_user(client, email="kw@example.com", org_name="KW Org")
    token = reg.json()["access_token"]
    await _upload(client, token, "settlement.txt", UNIQUE_TERM_CONTRACT)

    resp = await _search(client, token, {
        "query": "detrimental reliance",
        "mode": "keyword",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] == "keyword"
    assert body["total_documents"] >= 1
    group = body["groups"][0]
    assert group["document"]["filename"] == "settlement.txt"
    snippet = group["snippets"][0]
    assert "detrimental reliance" in snippet["text"]
    assert snippet["page_number"] >= 1
    assert snippet["source"] == "keyword"


@pytest.mark.asyncio
async def test_keyword_search_no_match_is_empty(client):
    reg = await register_user(client, email="kw2@example.com", org_name="KW2 Org")
    token = reg.json()["access_token"]
    await _upload(client, token, "settlement.txt", UNIQUE_TERM_CONTRACT)

    resp = await _search(client, token, {"query": "zebra quantum", "mode": "keyword"})
    assert resp.status_code == 200
    assert resp.json()["groups"] == []


@pytest.mark.asyncio
async def test_semantic_search_returns_results(client):
    reg = await register_user(client, email="sem@example.com", org_name="Sem Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token, "agreement.txt", SAMPLE_CONTRACT)

    resp = await _search(client, token, {"query": "payment terms", "mode": "semantic"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_documents"] >= 1
    group = body["groups"][0]
    assert group["document"]["id"] == doc_id
    snippet = group["snippets"][0]
    assert snippet["chunk_id"]
    assert snippet["source"] == "semantic"


@pytest.mark.asyncio
async def test_hybrid_search_merges_sources(client):
    reg = await register_user(client, email="hyb@example.com", org_name="Hyb Org")
    token = reg.json()["access_token"]
    await _upload(client, token, "agreement.txt", SAMPLE_CONTRACT)

    resp = await _search(client, token, {
        "query": "confidentiality obligations",
        "mode": "hybrid",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "hybrid"
    assert body["total_documents"] >= 1
    sources = {
        snippet["source"]
        for group in body["groups"]
        for snippet in group["snippets"]
    }
    assert sources <= {"keyword", "semantic", "both"}
    assert "keyword" in sources or "both" in sources


@pytest.mark.asyncio
async def test_search_filters_by_document_type(client):
    reg = await register_user(client, email="filt@example.com", org_name="Filt Org")
    token = reg.json()["access_token"]
    await _upload(client, token, "agreement.txt", SAMPLE_CONTRACT)

    # The sample classifies as "contract"; an NDA filter must exclude it.
    resp = await _search(client, token, {
        "query": "payment",
        "mode": "keyword",
        "filters": {"document_type": "nda"},
    })
    assert resp.status_code == 200
    assert resp.json()["groups"] == []

    resp = await _search(client, token, {
        "query": "payment",
        "mode": "keyword",
        "filters": {"document_type": "contract"},
    })
    assert resp.status_code == 200
    assert resp.json()["total_documents"] >= 1


@pytest.mark.asyncio
async def test_search_cross_tenant_isolation(client):
    reg_a = await register_user(client, org_name="Search A", email="search_a@example.com")
    reg_b = await register_user(client, org_name="Search B", email="search_b@example.com")
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]
    await _upload(client, token_a, "settlement.txt", UNIQUE_TERM_CONTRACT)

    for mode in ("keyword", "semantic", "hybrid"):
        resp = await _search(client, token_b, {
            "query": "detrimental reliance",
            "mode": mode,
        })
        assert resp.status_code == 200
        assert resp.json()["groups"] == [], f"{mode} leaked across tenants"


@pytest.mark.asyncio
async def test_search_requires_auth(client):
    resp = await client.post("/api/v1/search", json={"query": "anything"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_validates_request(client):
    reg = await register_user(client, email="val@example.com", org_name="Val Org")
    token = reg.json()["access_token"]

    resp = await _search(client, token, {"query": "", "mode": "keyword"})
    assert resp.status_code == 422

    resp = await _search(client, token, {"query": "x", "mode": "telepathic"})
    assert resp.status_code == 422

    resp = await _search(client, token, {
        "query": "x",
        "mode": "keyword",
        "filters": {"date_from": "not-a-date"},
    })
    assert resp.status_code == 400
