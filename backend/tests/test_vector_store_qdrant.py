"""QdrantVectorStore regression tests.

The test suite normally runs against InMemoryVectorStore, which is exactly
how two Qdrant-only bugs shipped: an invalid `MatchValue(any=...)` filter
construction and the removed `client.search()` API (renamed to
`query_points` in qdrant-client 1.12+). These tests pin the real Qdrant
call shape with a stub client.
"""
from __future__ import annotations

import pytest

from app.services.vector_store import QdrantVectorStore


class StubQdrantClient:
    """Records the last query_points call; implements nothing else."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)

        class Point:
            def __init__(self):
                self.id = "chunk-1"
                self.score = 0.9
                self.payload = {"document_id": "doc-1"}

        class Response:
            points = [Point()]

        return Response()


@pytest.mark.asyncio
async def test_search_uses_query_points_with_match_any():
    store = QdrantVectorStore()
    stub = StubQdrantClient()
    store._client = stub

    hits = await store.search(
        [0.1] * 4,
        organization_id="org-1",
        document_ids=["doc-1", "doc-2"],
    )

    assert len(hits) == 1
    assert hits[0].chunk_id == "chunk-1"
    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert call["query"] == [0.1] * 4
    # org + document_id conditions, the latter matching any listed id
    must = call["query_filter"].must
    assert len(must) == 2
    assert must[0].match.value == "org-1"
    assert sorted(must[1].match.any) == ["doc-1", "doc-2"]


@pytest.mark.asyncio
async def test_search_without_document_scope_omits_filter():
    store = QdrantVectorStore()
    stub = StubQdrantClient()
    store._client = stub

    await store.search([0.1] * 4, organization_id="org-1", document_ids=None)

    must = stub.calls[0]["query_filter"].must
    assert len(must) == 1  # organization only


@pytest.mark.asyncio
async def test_search_with_empty_document_scope_returns_nothing():
    store = QdrantVectorStore()
    stub = StubQdrantClient()
    store._client = stub

    hits = await store.search([0.1] * 4, organization_id="org-1", document_ids=[])

    assert hits == []
    assert stub.calls == []  # never reaches Qdrant
