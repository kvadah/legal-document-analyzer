"""Async Redis client with helpers for refresh tokens, invite tokens, and rate limiting."""
import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

# Module-level pool (initialised lazily; closed in lifespan shutdown)
_redis_pool: aioredis.Redis | None = None

REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60   # 7 days
INVITE_TOKEN_TTL_SECONDS = 48 * 60 * 60         # 48 hours
LOGIN_RATE_LIMIT_WINDOW = 15 * 60               # 15 minutes
LOGIN_RATE_LIMIT_MAX = 5                        # max bad attempts


async def get_redis() -> aioredis.Redis:
    """Return (or create) the shared async Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool (called on app shutdown)."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None


# ── Refresh tokens ────────────────────────────────────────────────────────────

def _refresh_key(token: str) -> str:
    return f"refresh:{token}"


async def store_refresh_token(token: str, user_id: str) -> None:
    r = await get_redis()
    await r.set(_refresh_key(token), user_id, ex=REFRESH_TOKEN_TTL_SECONDS)


async def validate_refresh_token(token: str) -> str | None:
    """Return the user_id associated with this refresh token, or None if invalid/expired."""
    r = await get_redis()
    return await r.get(_refresh_key(token))


async def delete_refresh_token(token: str) -> None:
    r = await get_redis()
    await r.delete(_refresh_key(token))


# ── Invite tokens ─────────────────────────────────────────────────────────────

def _invite_key(token: str) -> str:
    return f"invite:{token}"


async def store_invite_token(token: str, payload: dict[str, Any]) -> None:
    r = await get_redis()
    await r.set(_invite_key(token), json.dumps(payload), ex=INVITE_TOKEN_TTL_SECONDS)


async def get_invite_token(token: str) -> dict[str, Any] | None:
    r = await get_redis()
    raw = await r.get(_invite_key(token))
    return json.loads(raw) if raw else None


async def delete_invite_token(token: str) -> None:
    r = await get_redis()
    await r.delete(_invite_key(token))


# ── Login rate limiting ───────────────────────────────────────────────────────

def _rate_key(email: str) -> str:
    return f"login_attempts:{email.lower()}"


async def check_login_rate_limit(email: str) -> bool:
    """Return True if the email is rate-limited (too many failed attempts)."""
    r = await get_redis()
    key = _rate_key(email)
    count = await r.get(key)
    return int(count or 0) >= LOGIN_RATE_LIMIT_MAX


async def increment_login_failures(email: str) -> None:
    """Increment the failed-login counter for an email (sliding window)."""
    r = await get_redis()
    key = _rate_key(email)
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, LOGIN_RATE_LIMIT_WINDOW)
    await pipe.execute()


async def clear_login_failures(email: str) -> None:
    """Clear the failed-login counter after a successful login."""
    r = await get_redis()
    await r.delete(_rate_key(email))
