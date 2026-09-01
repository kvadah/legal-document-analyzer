"""Arq worker job definitions."""

from app.workers.pool import _redis_settings, process_ingestion


class WorkerSettings:
    """Arq worker configuration."""

    redis_settings = _redis_settings()
    functions = [process_ingestion]
