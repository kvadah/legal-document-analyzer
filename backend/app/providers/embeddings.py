"""Embedding provider abstraction for ingestion pipeline."""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Protocol

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)

VECTOR_SIZE = 1024

_GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class EmbeddingProvider(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class MockEmbeddingProvider:
    """Deterministic pseudo-embeddings for dev/test without ML dependencies."""

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_hash_to_vector(text) for text in texts]


class GeminiEmbeddingProvider:
    """Embeddings via the Google Gemini API (no local ML stack required)."""

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY must be set when MOCK_EMBEDDINGS=false")
        self._api_key: str = settings.gemini_api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=20), reraise=True)
    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = await self._get_client()
        model = settings.embedding_model_name.removeprefix("models/")
        response = await client.post(
            f"{_GEMINI_EMBED_URL}/{model}:batchEmbedContents",
            headers={"x-goog-api-key": self._api_key},
            json={
                "requests": [
                    {
                        "model": f"models/{model}",
                        "content": {"parts": [{"text": text}]},
                        "taskType": "RETRIEVAL_DOCUMENT",
                        "outputDimensionality": VECTOR_SIZE,
                    }
                    for text in texts
                ]
            },
        )
        response.raise_for_status()
        return [item["values"] for item in response.json()["embeddings"]]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        result = await self._embed_batch(texts)
        logger.info(
            "embeddings.call",
            extra={"model": settings.embedding_model_name, "count": len(texts)},
        )
        return result


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
            _provider = GeminiEmbeddingProvider()
    return _provider


def reset_embedding_provider(provider: EmbeddingProvider | None = None) -> None:
    global _provider
    _provider = provider
