"""Arq worker job definitions."""

from app.workers.pool import _redis_settings, process_ai_pipeline, process_ingestion


class WorkerSettings:
    """Arq worker configuration."""

    redis_settings = _redis_settings()
    functions = [process_ingestion, process_ai_pipeline]
    # Default arq job_timeout is 300s, which a rate-limited (free-tier)
    # Gemini run can exceed: ~15 paced LLM calls per document plus 429
    # backoffs. Keep the headroom so jobs aren't cancelled mid-pipeline.
    job_timeout = 1800
