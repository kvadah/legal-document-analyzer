"""Arq worker job definitions."""

from arq import cron

from app.workers.pool import (
    _redis_settings,
    process_ai_pipeline,
    process_comparison,
    process_ingestion,
    process_report,
    process_retention_pass,
)


class WorkerSettings:
    """Arq worker configuration."""

    redis_settings = _redis_settings()
    functions = [
        process_ingestion,
        process_ai_pipeline,
        process_comparison,
        process_report,
        process_retention_pass,
    ]
    # Default arq job_timeout is 300s, which a rate-limited (free-tier)
    # Gemini run can exceed: ~15 paced LLM calls per document plus 429
    # backoffs. Keep the headroom so jobs aren't cancelled mid-pipeline.
    job_timeout = 1800
    # Retention sweep: hard-delete past-grace soft-deleted documents, prune
    # audit logs, execute scheduled org deletions (11 §7). Daily at 03:00 UTC.
    cron_jobs = [cron(process_retention_pass, hour=3, minute=0, run_at_startup=False)]
