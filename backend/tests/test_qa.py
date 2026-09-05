"""Phase 5 RAG Q&A tests — grounding, threshold, tenancy, non-advisory."""
import json

import pytest
from app.core.config import settings

from tests.conftest import register_user

SAMPLE_CONTRACT = (
    b"MASTER SERVICES AGREEMENT\n\n"
    b"This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
    b"Payment. Client shall pay the Provider a total fee of $50,000 within 30 days of invoice.\n\n"
    b"Confidentiality. Each party shall keep information confidential.\n\n"
    b"Termination. Either party may terminate upon 30 days written notice.\n"
)


async def _upload(client, token):
    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("agreement.txt", SAMPLE_CONTRACT, "text/plain"))],
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["documents"][0]["document_id"]


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    """Parse a text/event-stream body into (event, data) pairs."""
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


async def _ask(client, token, doc_id, question, conversation_id=None):
    payload = {"question": question}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    return await client.post(
        f"/api/v1/documents/{doc_id}/ask",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )


@pytest.mark.asyncio
async def test_ask_streams_grounded_citations(client):
    reg = await register_user(client, email="qa@example.com", org_name="QA Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    resp = await _ask(client, token, doc_id, "What is the payment fee?")
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    names = [name for name, _data in events]
    assert "citations" in names
    assert "delta" in names
    assert names[-1] == "done"

    citations_event = next(data for name, data in events if name == "citations")
    done_event = next(data for name, data in events if name == "done")
    assert done_event["found_in_document"] is True
    assert done_event["conversation_id"]
    assert citations_event["citations"], "expected at least one grounded citation"

    # Every citation must point into this document with a verbatim quote
    text_resp = await client.get(
        f"/api/v1/documents/{doc_id}/text",
        headers={"Authorization": f"Bearer {token}"},
    )
    pages_text = "\n".join(
        block["text"] for page in text_resp.json()["pages"] for block in page["blocks"]
    )
    for citation in citations_event["citations"]:
        assert citation["page_number"] >= 1
        assert citation["quote"] in pages_text, f"quote not grounded: {citation['quote']!r}"

    # The streamed deltas reconstruct the final answer
    deltas = "".join(data["text"] for name, data in events if name == "delta")
    assert done_event["answer"].strip() in deltas or deltas.strip() in done_event["answer"]


@pytest.mark.asyncio
async def test_ask_below_threshold_says_not_found(client):
    reg = await register_user(client, email="qa2@example.com", org_name="QA2 Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    previous = settings.rag_similarity_threshold
    settings.rag_similarity_threshold = 1.1  # impossible cosine → always "not found"
    try:
        resp = await _ask(client, token, doc_id, "What is the payment fee?")
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
async def test_ask_declines_legal_advice(client):
    reg = await register_user(client, email="qa3@example.com", org_name="QA3 Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    resp = await _ask(client, token, doc_id, "Should I sign this contract?")
    assert resp.status_code == 200
    done_event = next(
        data for name, data in _parse_sse(resp.text) if name == "done"
    )
    answer = done_event["answer"].lower()
    assert "legal advice" in answer or "recommend" in answer or "counsel" in answer


@pytest.mark.asyncio
async def test_ask_conversation_continuity(client):
    reg = await register_user(client, email="qa4@example.com", org_name="QA4 Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    first = await _ask(client, token, doc_id, "What is the payment fee?")
    first_done = next(
        data for name, data in _parse_sse(first.text) if name == "done"
    )
    conversation_id = first_done["conversation_id"]

    second = await _ask(
        client, token, doc_id, "And the termination notice?", conversation_id
    )
    assert second.status_code == 200
    second_done = next(
        data for name, data in _parse_sse(second.text) if name == "done"
    )
    assert second_done["conversation_id"] == conversation_id


@pytest.mark.asyncio
async def test_ask_cross_tenant_returns_404(client):
    reg_a = await register_user(client, org_name="QA Tenant A", email="qa_a@example.com")
    reg_b = await register_user(client, org_name="QA Tenant B", email="qa_b@example.com")
    token_a = reg_a.json()["access_token"]
    token_b = reg_b.json()["access_token"]
    doc_id = await _upload(client, token_a)

    resp = await _ask(client, token_b, doc_id, "What is the payment fee?")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ask_requires_auth(client):
    reg = await register_user(client, email="qa5@example.com", org_name="QA5 Org")
    token = reg.json()["access_token"]
    doc_id = await _upload(client, token)

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/ask",
        json={"question": "What is this?"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ask_not_ready_returns_409(client, monkeypatch):
    async def _defer(document_id):
        return None

    monkeypatch.setattr("app.services.document_service.enqueue_ingestion", _defer)

    reg = await register_user(client, email="qa6@example.com", org_name="QA6 Org")
    token = reg.json()["access_token"]
    resp = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("pending.txt", b"queued content", "text/plain"))],
    )
    doc_id = resp.json()["documents"][0]["document_id"]

    ask_resp = await _ask(client, token, doc_id, "What is this?")
    assert ask_resp.status_code == 409
    assert ask_resp.json()["detail"]["code"] == "document_not_ready"
