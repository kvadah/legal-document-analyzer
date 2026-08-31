"""Embedding provider abstraction for ingestion pipeline."""
from __future__ import annotations

import hashlib
import math
from typing import Protocol

from app.core.config import settings

VECTOR_SIZE = 1024


class EmbeddingProvider(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class MockEmbeddingProvider:
    """Deterministic pseudo-embeddings for dev/test without ML dependencies."""

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_hash_to_vector(text) for text in texts]


class SentenceTransformerEmbeddingProvider:
    """Self-hosted BGE-large embeddings via sentence-transformers."""

    def __init__(self) -> None:
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(settings.embedding_model_name)
        return self._model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        vectors = await asyncio_to_thread(model.encode, texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]


async def asyncio_to_thread(func, *args, **kwargs):
    import asyncio

    return await asyncio.to_thread(func, *args, **kwargs)


def _hash_to_vector(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    while len(values) < VECTOR_SIZE:
        for i in range(0, len(digest), 4):
            chunk = digest[i : i + 4]
            if len(chunk) < 4:
                chunk = chunk.ljust(4, b"\0")
            num = int.from_bytes(chunk, "big", signed=False)
            values.append((num % 10000) / 10000.0)
            if len(values) >= VECTOR_SIZE:
                break
        digest = hashlib.sha256(digest).digest()
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        if settings.mock_embeddings:
            _provider = MockEmbeddingProvider()
        else:
            _provider = SentenceTransformerEmbeddingProvider()
    return _provider


def reset_embedding_provider(provider: EmbeddingProvider | None = None) -> None:
    global _provider
    _provider = provider
