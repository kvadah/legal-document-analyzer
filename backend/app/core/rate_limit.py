"""Redis-backed API rate limiting (09-api-spec.md §12).

Fixed-window counters scoped per-org (uploads) or per-user (search/Q&A),
matching the spec: upload ≈ 100 documents/hour per org, search/Q&A ≈ 60
requests/minute per user. Exceeding a limit returns 429 with a
``Retry-After`` header. Limits are configurable and can be disabled
entirely (tests, dev) via ``RATE_LIMIT_ENABLED=false``.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.config import settings
from app.core.deps import CurrentUser, get_current_user
from app.db.redis import get_redis


async def _retry_after_seconds(key: str, limit: int) -> int:
    """Increment the counter for *key*; return 0 when within *limit*.

    Otherwise returns the number of seconds until the window resets
    (the Retry-After value).
    """
    r = await get_redis()
    pipe = r.pipeline()
    pipe.incr(key)
    # TTL only on the first hit of a window (NX semantics).
    pipe.expire(key, 3600, nx=True)
    count, _ = await pipe.execute()
    if count <= limit:
        return 0
    ttl = await r.ttl(key)
    return max(ttl, 1)


def _deny(scope: str, retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "code": "rate_limited",
            "message": (
                f"Rate limit exceeded for {scope}. "
                f"Retry after {retry_after} second(s)."
            ),
        },
        headers={"Retry-After": str(retry_after)},
    )


def _make_limiter(*, scope: str, limit_getter, window_seconds: int, per_user: bool):
    async def _limiter(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> None:
        limit = limit_getter()
        if not settings.rate_limit_enabled or limit <= 0:
            return
        identity = current_user.id if per_user else current_user.org_id
        key = f"ratelimit:{scope}:{identity}"
        retry_after = await _retry_after_seconds(key, limit)
        if retry_after:
            raise _deny(scope, retry_after)

    return _limiter


def upload_rate_limit():
    """Upload budget: N documents/hour per org (configurable per plan tier)."""
    return _make_limiter(
        scope="upload",
        limit_getter=lambda: settings.upload_rate_limit_per_hour,
        window_seconds=3600,
        per_user=False,
    )


def search_rate_limit():
    """Search & RAG Q&A budget: N requests/minute per user."""
    return _make_limiter(
        scope="search",
        limit_getter=lambda: settings.search_rate_limit_per_minute,
        window_seconds=60,
        per_user=True,
    )
