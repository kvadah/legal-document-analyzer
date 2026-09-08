"""Google Gemini LLM provider (interim primary — to be swapped for Claude/GPT later).

Uses the same Gemini API key as the embeddings provider. Structured output is
enforced via `responseSchema` (Gemini's OpenAPI-3.0 subset), so no SDK is
needed — plain httpx, mirroring `app.providers.embeddings`.

Rate-limit handling: the AI pipeline issues ~15 LLM calls per document and
free-tier keys allow only ~10 requests/minute, so 429s are expected, not
exceptional. `_call` therefore (a) paces requests client-side
(`GEMINI_MIN_REQUEST_INTERVAL`) and (b) retries 429s up to 6 times, waiting
as long as the server's RetryInfo/retry-after advises.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.llm.base import ModelTier, StructuredResult, elapsed_ms, now_ms
from app.llm.prompts import GROUNDING_RULES, PROMPT_VERSION

logger = logging.getLogger(__name__)

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_MAX_CONTEXT_CHARS = 60_000
_MAX_OUTPUT_TOKENS = 16_384

# 429s: quota windows reset per-minute, so retry patiently (Google's
# RetryInfo often advises 20-60s). 5xx: transient, short backoff.
_MAX_ATTEMPTS_RATE_LIMITED = 6
_MAX_ATTEMPTS_SERVER_ERROR = 3
_MAX_BACKOFF_SECONDS = 60.0

# Keys from Pydantic's JSON schema that Gemini's responseSchema does not accept.
# Everything except the whitelist below is dropped; range constraints stay
# enforced Pydantic-side after validation.
_SUPPORTED_KEYS = frozenset(
    {"type", "enum", "const", "description", "nullable", "items", "properties", "required"}
)

_PRIMITIVE_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}


def to_gemini_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model's JSON schema into Gemini's responseSchema subset.

    Gemini accepts no `$ref`/`$defs` and no `anyOf`. Nested models are inlined,
    and Pydantic's `Optional[X]` (`anyOf: [X, null]`) becomes `nullable: true`.
    """
    raw: dict[str, Any] = schema.model_json_schema()
    return _convert_node(raw, defs=raw.get("$defs", {}))


def _convert_node(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in node:
        ref_name = node["$ref"].rsplit("/", 1)[-1]
        return _convert_node(defs[ref_name], defs=defs)

    if "anyOf" in node:
        # Pydantic emits Optional[X] as anyOf [X, {type: null}] (sometimes with
        # duplicated variants for implicit-None unions). Merge into one
        # nullable node.
        variants = [_convert_node(v, defs=defs) for v in node["anyOf"]]
        nullable = any(v.get("type") == "NULL" for v in variants)
        non_null = [v for v in variants if v.get("type") != "NULL"]
        merged: dict[str, Any] = dict(non_null[0]) if non_null else {"type": "STRING"}
        for v in non_null[1:]:
            merged.update(v)
        if nullable:
            merged["nullable"] = True
        return {k: v for k, v in merged.items() if k in _SUPPORTED_KEYS}

    out: dict[str, Any] = {}
    node_type = node.get("type")
    if node_type:
        out["type"] = node_type.upper() if node_type in _PRIMITIVE_TYPES else node_type
    if "const" in node:
        out["enum"] = [node["const"]]
    for key in ("enum", "description"):
        if key in node:
            out[key] = node[key]
    if node_type == "array" and "items" in node:
        out["items"] = _convert_node(node["items"], defs=defs)
    if node_type == "object" and "properties" in node:
        out["properties"] = {
            name: _convert_node(prop, defs=defs) for name, prop in node["properties"].items()
        }
        if "required" in node:
            out["required"] = list(node["required"])
    return out


def _parse_retry_delay(response: httpx.Response) -> float | None:
    """Extract the server-advised retry delay (seconds) from a 429 response.

    Google sends `error.details[].retryDelay` ("26s", RFC-500 RetryInfo);
    some proxies send a plain `Retry-After` header instead. Returns None when
    neither is present/parsable.
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), 1.0)
        except ValueError:
            pass
    try:
        details = response.json()["error"]["details"]
    except (ValueError, KeyError, TypeError):
        return None
    for detail in details:
        if not isinstance(detail, dict):
            continue
        delay = detail.get("retryDelay")
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return max(float(delay[:-1]), 1.0)
            except ValueError:
                continue
    return None


class GeminiProvider:
    """Gemini via responseSchema-constrained JSON structured output."""

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY must be set when using the gemini LLM provider")
        self._api_key: str = settings.gemini_api_key
        self._client: httpx.AsyncClient | None = None
        # Client-side rate pacing, shared across all jobs in this process
        # (the provider is a process-wide singleton).
        self._pacing_lock = asyncio.Lock()
        self._next_allowed_at = 0.0
        # Injectable for tests.
        self._sleep: Callable[[float], Awaitable[None]] = asyncio.sleep

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    def _model_for(self, tier: ModelTier) -> str:
        return settings.gemini_llm_model if tier == "capable" else settings.gemini_llm_fast_model

    def _generation_config(self, schema: type[BaseModel]) -> dict[str, Any]:
        config: dict[str, Any] = {
            "responseMimeType": "application/json",
            "responseSchema": to_gemini_schema(schema),
            "maxOutputTokens": _MAX_OUTPUT_TOKENS,
            "temperature": 0.0,
        }
        # Thinking budget: 0 disables thinking (gemini-2.5-flash), None omits
        # the field entirely (models without thinkingConfig support).
        if settings.gemini_thinking_budget is not None:
            config["thinkingConfig"] = {"thinkingBudget": settings.gemini_thinking_budget}
        return config

    async def _pace(self) -> None:
        """Enforce the configured minimum interval between API requests.

        Sleeps while holding the lock, so concurrent callers (multiple worker
        jobs share this provider instance) queue up instead of bursting past
        the quota together.
        """
        interval = settings.gemini_min_request_interval
        if interval <= 0:
            return
        async with self._pacing_lock:
            wait = max(0.0, self._next_allowed_at - time.monotonic())
            if wait > 0:
                await self._sleep(wait)
            self._next_allowed_at = time.monotonic() + interval

    async def _call(
        self,
        model: str,
        system: str,
        user_content: str,
        schema: type[BaseModel],
    ) -> tuple[dict[str, Any], dict[str, int]]:
        client = await self._get_client()
        url = f"{_GEMINI_BASE_URL}/{model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": self._generation_config(schema),
        }

        rate_limited_attempts = 0
        server_error_attempts = 0
        while True:
            await self._pace()
            response = await client.post(
                url, headers={"x-goog-api-key": self._api_key}, json=payload
            )

            if response.status_code == 429:
                rate_limited_attempts += 1
                if rate_limited_attempts >= _MAX_ATTEMPTS_RATE_LIMITED:
                    raise RuntimeError(
                        "Gemini API rate limit exceeded after "
                        f"{_MAX_ATTEMPTS_RATE_LIMITED} attempts (free-tier quotas "
                        "can be as low as 20 requests/day/model). Wait for the "
                        "quota window to reset, retry the document later, or "
                        "switch to a key/provider with higher limits."
                    ) from None
                delay = _parse_retry_delay(response) or min(
                    3.0 * 2 ** (rate_limited_attempts - 1), _MAX_BACKOFF_SECONDS
                )
                delay += random.uniform(0.0, 1.0)
                logger.warning(
                    "llm.rate_limited",
                    extra={
                        "model": model,
                        "attempt": rate_limited_attempts,
                        "retry_in_s": round(delay, 1),
                    },
                )
                await self._sleep(delay)
                continue

            if response.status_code >= 500:
                server_error_attempts += 1
                if server_error_attempts >= _MAX_ATTEMPTS_SERVER_ERROR:
                    response.raise_for_status()
                await self._sleep(min(2.0**server_error_attempts, 10.0) + random.uniform(0.0, 1.0))
                continue

            response.raise_for_status()
            break

        payload_json = response.json()
        candidates = payload_json.get("candidates") or []
        if not candidates or "content" not in candidates[0]:
            raise RuntimeError(f"Gemini returned no content: {json.dumps(payload_json)[:500]}")
        parts = candidates[0]["content"].get("parts") or []
        text = "".join(part.get("text", "") for part in parts)
        if not text.strip():
            finish = candidates[0].get("finishReason", "UNKNOWN")
            raise RuntimeError(f"Gemini returned empty text (finishReason={finish})")
        data: dict[str, Any] = json.loads(text)
        usage_meta = payload_json.get("usageMetadata", {})
        usage = {
            "input": usage_meta.get("promptTokenCount", 0),
            "output": usage_meta.get("candidatesTokenCount", 0),
        }
        return data, usage

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        context: list[str],
        model_tier: ModelTier,
        prompt_version: str = PROMPT_VERSION,
    ) -> StructuredResult:
        model = self._model_for(model_tier)
        context_text = "\n\n".join(context)[:_MAX_CONTEXT_CHARS]
        user_content = f"{prompt}\n\nCONTEXT:\n{context_text}"
        start = now_ms()
        data, usage = await self._call(model, GROUNDING_RULES, user_content, schema)
        result = StructuredResult(
            result=schema.model_validate(data),
            model_version=model,
            prompt_version=prompt_version,
            latency_ms=elapsed_ms(start),
            token_usage=usage,
        )
        logger.info(
            "llm.call",
            extra={
                "provider": "gemini",
                "model": model,
                "prompt_version": prompt_version,
                "latency_ms": result.latency_ms,
                "tokens": json.dumps(usage),
            },
        )
        return result

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
