"""Phase 7 cross-document RAG Q&A tests — attribution, filters, tenancy."""
import json

import pytest
from app.core.config import settings

from tests.conftest import register_user

DOC_A = (
    b"MASTER SERVICES AGREEMENT\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
    b"Payment. Client shall pay the Provider a total fee of $50,000 within 30 days of invoice.\n"
)

DOC_B = (
    b"NON-DISCLOSURE AGREEMENT\n\n"
    b"Between Gamma Inc and Delta LLC.\n\n"
    b"Confidential information shall be protected for five years after termination.\n"
)


async def _upload(client, token, filename, content):
    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", (filename, content, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["documents"][0]["document_id"]


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    body = body.replace("\r\n", "\n")
    events = []
    for block in body.split("\n\n"):
        event_name = None
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())
        if event_name and data_lines:
            events.append((event_name, json.loads("\n".join(data_lines))))
    return events


async def _ask_all(client, token, question, filters=None, conversation_id=None):
    payload = {"question": question}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    if filters:
        payload["filters"] = filters
    return await client.post(
        "/api/v1/ask",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )


async def _document_text(client, token, doc_id) -> str:
    resp = await client.get(
        f"/api/v1/documents/{doc_id}/text",
        headers={"Authorization": f"Bearer {token}"},
    )
    return "\n".join(
        block["text"] for page in resp.json()["pages"] for block in page["blocks"]
    )


@pytest.mark.asyncio
async def test_ask_all_attributes_citations_to_source_documents(client):
    reg = await register_user(client, email="xqa@example.com", org_name="XQA Org")
    token = reg.json()["access_token"]
    doc_a = await _upload(client, token, "msa.txt", DOC_A)
    doc_b = await _upload(client, token, "nda.txt", DOC_B)

    resp = await _ask_all(client, token, "What is the payment fee and the confidentiality term?")
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    names = [name for name, _data in events]
    assert names[-1] == "done"

    citations_event = next(data for name, data in events if name == "citations")
    done_event = next(data for name, data in events if name == "done")
    assert done_event["found_in_document"] is True
    assert citations_event["citations"]

    texts = {doc_a: await _document_text(client, token, doc_a),
             doc_b: await _document_text(client, token, doc_b)}
    # The strict attribution requirement (08 §3): every citation must name the
    # document it came from, and the quote must be verbatim in THAT document.
    for citation in citations_event["citations"]:
        assert citation["document_id"] in texts
        assert citation["document_name"]
        assert citation["quote"] in texts[citation["document_id"]], (
            f"quote not grounded in cited document: {citation['quote']!r}"
        )


@pytest.mark.asyncio
async def test_ask_all_respects_document_filter(client):
    reg = await register_user(client, email="xqa2@example.com", org_name="XQA2 Org")
    token = reg.json()["access_token"]
    await _upload(client, token, "msa.txt", DOC_A)
    doc_b = await _upload(client, token, "nda.txt", DOC_B)

    resp = await _ask_all(
        client,
        token,
        "What is the payment fee and the confidentiality term?",
        filters={"document_ids": [doc_b]},
    )
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    citations_event = next((data for name, data in events if name == "citations"), None)
    if citations_event and citations_event["citations"]:
        assert all(c["document_id"] == doc_b for c in citations_event["citations"])


@pytest.mark.asyncio
async def test_ask_all_below_threshold_says_not_found(client):
    reg = await register_user(client, email="xqa3@example.com", org_name="XQA3 Org")
    token = reg.json()["access_token"]
    await _upload(client, token, "msa.txt", DOC_A)

    previous = settings.rag_similarity_threshold
    settings.rag_similarity_threshold = 1.1
    try:
        resp = await _ask_all(client, token, "What is the payment fee?")
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        citations_event = next(data for name, data in events if name == "citations")
        done_event = next(data for name, data in events if name == "done")
        assert citations_event["citations"] == []
        assert done_event["found_in_document"] is False
        assert "couldn't find" in done_event["answer"]
    finally:
        settings.rag_similarity_threshold = previous


@pytest.mark.asyncio
async def test_ask_all_cross_tenant_leaks_nothing(client):
    reg_a = await register_user(client, org_name="XQA Tenant A", email="xqa_a@example.com")
    reg_b = await register_user(client, org_name="XQA Tenant B", email="xqa_b@example.com")
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]
    await _upload(client, token_a, "msa.txt", DOC_A)

    # Org B has an empty corpus: the answer must be "not found" with no
    # citations leaking in from org A.
    resp = await _ask_all(client, token_b, "What is the payment fee?")
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    citations_event = next(data for name, data in events if name == "citations")
    done_event = next(data for name, data in events if name == "done")
    assert citations_event["citations"] == []
    assert done_event["found_in_document"] is False


@pytest.mark.asyncio
async def test_ask_all_requires_auth(client):
    resp = await client.post("/api/v1/ask", json={"question": "What is this?"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ask_all_conversation_continuity(client):
    reg = await register_user(client, email="xqa4@example.com", org_name="XQA4 Org")
    token = reg.json()["access_token"]
    await _upload(client, token, "msa.txt", DOC_A)

    first = await _ask_all(client, token, "What is the payment fee?")
    first_done = next(data for name, data in _parse_sse(first.text) if name == "done")
    conversation_id = first_done["conversation_id"]

    second = await _ask_all(
        client, token, "And the payment deadline?", conversation_id=conversation_id
    )
    assert second.status_code == 200
    second_done = next(data for name, data in _parse_sse(second.text) if name == "done")
    assert second_done["conversation_id"] == conversation_id
