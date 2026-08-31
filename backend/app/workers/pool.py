"""Arq worker pool helpers and ingestion job enqueue."""
from __future__ import annotations

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings
from app.pipelines.ingestion.pipeline import run_ingestion_pipeline

_arq_pool = None


def _redis_settings() -> RedisSettings:
    parsed = settings.redis_url.replace("redis://", "")
    host_port, _, db = parsed.partition("/")
    host, _, port = host_port.partition(":")
    return RedisSettings(
        host=host or "localhost",
        port=int(port or 6379),
        database=int(db or 0),
    )


async def get_arq_pool():
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(_redis_settings())
    return _arq_pool


async def enqueue_ingestion(document_id: str) -> None:
    if settings.run_ingestion_inline:
        await run_ingestion_pipeline(document_id)
        return
    pool = await get_arq_pool()
    await pool.enqueue_job("process_ingestion", document_id)


async def process_ingestion(ctx, document_id: str) -> None:  # noqa: ARG001
    await run_ingestion_pipeline(document_id)
