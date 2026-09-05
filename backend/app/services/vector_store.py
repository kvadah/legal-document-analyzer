"""Vector store abstraction over Qdrant (production) / in-memory (tests & dev).

The ingestion pipeline writes chunk embeddings here; search and RAG Q&A read
from here. The in-memory backend does brute-force cosine similarity — it exists
so the full search/Q&A flow works in tests and local dev without a Qdrant
instance (pair it with MOCK_EMBEDDINGS=true), matching the mock-LLM pattern.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Protocol

from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue, PointStruct

from app.core.config import settings


@dataclass
class ScoredChunk:
    """A retrieved chunk with its similarity score."""

    chunk_id: str
    score: float
    payload: dict


class VectorStore(Protocol):
    async def upsert(self, points: list[PointStruct]) -> None: ...
    async def search(
        self,
        query_vector: list[float],
        *,
        organization_id: str,
        document_ids: list[str] | None = None,
        limit: int = 50,
    ) -> list[ScoredChunk]: ...
    async def delete(self, chunk_ids: list[str]) -> None: ...


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStore:
    """Brute-force cosine search over points kept in process memory."""

    def __init__(self) -> None:
        self._points: dict[str, tuple[list[float], dict]] = {}

    async def upsert(self, points: list[PointStruct]) -> None:
        for point in points:
            self._points[str(point.id)] = (list(point.vector), dict(point.payload or {}))

    async def search(
        self,
        query_vector: list[float],
        *,
        organization_id: str,
        document_ids: list[str] | None = None,
        limit: int = 50,
    ) -> list[ScoredChunk]:
        allowed_docs = set(document_ids) if document_ids is not None else None
        scored: list[ScoredChunk] = []
        for chunk_id, (vector, payload) in self._points.items():
            if payload.get("organization_id") != organization_id:
                continue
            if allowed_docs is not None and payload.get("document_id") not in allowed_docs:
                continue
            scored.append(
                ScoredChunk(
                    chunk_id=chunk_id,
                    score=_cosine(query_vector, vector),
                    payload=payload,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:limit]

    async def delete(self, chunk_ids: list[str]) -> None:
        for chunk_id in chunk_ids:
            self._points.pop(chunk_id, None)

    def clear(self) -> None:
        self._points.clear()


class QdrantVectorStore:
    """Qdrant-backed store — sync client calls pushed onto a worker thread."""

    def _client(self) -> QdrantClient:
        return QdrantClient(url=settings.qdrant_url)

    async def upsert(self, points: list[PointStruct]) -> None:
        if not points:
            return

        def _write() -> None:
            client = self._client()
            client.upsert(collection_name=settings.qdrant_collection_name, points=points)

        await asyncio.to_thread(_write)

    async def search(
        self,
        query_vector: list[float],
        *,
        organization_id: str,
        document_ids: list[str] | None = None,
        limit: int = 50,
    ) -> list[ScoredChunk]:
        conditions = [
            FieldCondition(key="organization_id", match=MatchValue(value=organization_id))
        ]
        if document_ids is not None:
            conditions.append(
                FieldCondition(key="document_id", match=MatchValue(any=document_ids))
            )

        def _query() -> list[ScoredChunk]:
            client = self._client()
            response = client.search(
                collection_name=settings.qdrant_collection_name,
                query_vector=query_vector,
                query_filter=Filter(must=conditions),
                limit=limit,
                with_payload=True,
            )
            return [
                ScoredChunk(chunk_id=str(hit.id), score=hit.score, payload=hit.payload or {})
                for hit in response
            ]

        return await asyncio.to_thread(_query)

    async def delete(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return

        def _delete() -> None:
            from qdrant_client.http.models import PointIdsList

            client = self._client()
            client.delete(
                collection_name=settings.qdrant_collection_name,
                points_selector=PointIdsList(points=chunk_ids),
            )

        await asyncio.to_thread(_delete)


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        if settings.vector_search_backend == "memory":
            _store = InMemoryVectorStore()
        else:
            _store = QdrantVectorStore()
    return _store


def reset_vector_store(store: VectorStore | None = None) -> None:
    """Reset the module-level singleton (used in tests)."""
    global _store
    _store = store
