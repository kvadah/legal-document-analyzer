"""Shared helpers for SSE streaming endpoints."""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_UNREACHABLE_MESSAGE = (
    "The AI service is temporarily unreachable. Please try again in a moment."
)
_FALLBACK_MESSAGE = "Something went wrong while answering. Please try again."


def _public_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        if isinstance(exc.detail, dict) and exc.detail.get("message"):
            return str(exc.detail["message"])
        if isinstance(exc.detail, str) and exc.detail:
            return exc.detail
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return _UNREACHABLE_MESSAGE
    return _FALLBACK_MESSAGE


async def sse_error_guard(events: AsyncIterator[dict]) -> AsyncIterator[dict]:
    """Forward SSE events, converting generator failures into an `error` event.

    Once an SSE response has started, an exception raised inside the event
    generator can no longer become a proper HTTP error — it aborts the
    chunked response mid-stream and clients see a raw network failure
    (ERR_INCOMPLETE_CHUNKED_ENCODING). Yielding an `error` event instead
    lets the client render a friendly message. CancelledError (client
    disconnects) propagates untouched.
    """
    try:
        async for event in events:
            yield event
    except Exception as exc:
        logger.error("sse.stream_failed", exc_info=True)
        yield {
            "event": "error",
            "data": json.dumps({"message": _public_message(exc)}),
        }
