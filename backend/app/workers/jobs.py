"""Arq worker job definitions."""
from arq.connections import RedisSettings

from app.core.config import settings


class WorkerSettings:
    """Arq worker configuration."""

    redis_settings = RedisSettings(host="redis", port=6379, database=0)
    functions = []  # Jobs will be registered here


# Placeholder for future job definitions
