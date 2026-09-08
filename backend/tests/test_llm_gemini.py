"""Unit tests for the Gemini LLM provider (no network access needed)."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from app.core.config import settings
from app.llm import MockLLMProvider, get_llm_provider, reset_llm_provider
from app.llm.gemini_provider import (
    _MAX_ATTEMPTS_RATE_LIMITED,
    GeminiProvider,
    _parse_retry_delay,
    to_gemini_schema,
)
from app.pipelines.ai.extraction import (
    ClauseDetectionResult,
    MetadataExtraction,
    RiskJudgmentResult,
)


@pytest.fixture(autouse=True)
def _restore_provider():
    yield
    reset_llm_provider(MockLLMProvider())


def test_schema_inlines_defs_and_uppercases_types():
    schema = to_gemini_schema(ClauseDetectionResult)

    assert schema["type"] == "OBJECT"
    props = schema["properties"]
    assert props["found"]["type"] == "BOOLEAN"

    instances = props["instances"]
    assert instances["type"] == "ARRAY"
    item = instances["items"]
    assert item["type"] == "OBJECT"
    assert set(item["properties"]) == {"chunk_id", "extracted_text", "summary", "confidence"}
    assert set(item["required"]) == {"chunk_id", "extracted_text", "summary", "confidence"}

    serialized = json.dumps(schema)
    assert "$ref" not in serialized
    assert "anyOf" not in serialized
    assert "$defs" not in serialized


def test_schema_converts_optional_to_nullable():
    schema = to_gemini_schema(MetadataExtraction)

    props = schema["properties"]
    assert props["governing_law"] == {"type": "STRING", "nullable": True}
    assert props["contract_value"] == {"type": "NUMBER", "nullable": True}
    # parties is a list of {name, role?} — role must be nullable, name required
    party = props["parties"]["items"]
    assert party["properties"]["role"]["nullable"] is True
    assert party["required"] == ["name"]


def test_schema_keeps_enums():
    schema = to_gemini_schema(RiskJudgmentResult)

    severity = schema["properties"]["severity"]
    assert severity["type"] == "STRING"
    assert set(severity["enum"]) == {"low", "medium", "high", "critical"}


def test_batched_clauses_schema_enum_matches_clause_type_enum():
    from app.models.models import ClauseType
    from app.pipelines.ai.extraction import AllClausesResult

    schema = to_gemini_schema(AllClausesResult)
    clause_type = schema["properties"]["clauses"]["items"]["properties"]["clause_type"]
    assert set(clause_type["enum"]) == {t.value for t in ClauseType}


def test_schema_drops_unsupported_keys():
    # confidence has ge/le constraints -> minimum/maximum must be dropped
    schema = to_gemini_schema(ClauseDetectionResult)

    serialized = json.dumps(schema)
    assert "minimum" not in serialized
    assert "maximum" not in serialized
    assert "title" not in serialized


def test_gemini_provider_requires_key():
    original = settings.gemini_api_key
    settings.gemini_api_key = None
    try:
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiProvider()
    finally:
        settings.gemini_api_key = original


def test_factory_selects_gemini_when_configured():
    original = (settings.mock_llm, settings.default_llm_provider, settings.gemini_api_key)
    settings.mock_llm = False
    settings.default_llm_provider = "gemini"
    settings.gemini_api_key = "test-key"
    reset_llm_provider(None)
    try:
        provider = get_llm_provider()
        assert isinstance(provider, GeminiProvider)
    finally:
        settings.mock_llm, settings.default_llm_provider, settings.gemini_api_key = original
        reset_llm_provider(MockLLMProvider())


def test_factory_rejects_unknown_provider():
    original = (settings.mock_llm, settings.default_llm_provider)
    settings.mock_llm = False
    settings.default_llm_provider = "bogus"
    reset_llm_provider(None)
    try:
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_provider()
    finally:
        settings.mock_llm, settings.default_llm_provider = original
        reset_llm_provider(MockLLMProvider())


def test_generation_config_thinking_budget():
    original = settings.gemini_thinking_budget
    provider = GeminiProvider.__new__(GeminiProvider)  # skip __init__ (no key needed)
    try:
        settings.gemini_thinking_budget = 0
        config = provider._generation_config(ClauseDetectionResult)
        assert config["thinkingConfig"] == {"thinkingBudget": 0}

        settings.gemini_thinking_budget = None
        config = provider._generation_config(ClauseDetectionResult)
        assert "thinkingConfig" not in config
        assert config["responseMimeType"] == "application/json"
        assert config["responseSchema"]["type"] == "OBJECT"
    finally:
        settings.gemini_thinking_budget = original


# ── Rate-limit handling (429 retry + client-side pacing) ─────────────────────


class _SleepRecorder:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class _StubClient:
    """Returns queued responses in order; repeats the last one if exhausted."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = responses
        self.calls = 0

    async def post(self, *args: object, **kwargs: object) -> httpx.Response:
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


def _response(
    status: int, json_body: dict | None = None, headers: dict | None = None
) -> httpx.Response:
    response = httpx.Response(status, json=json_body or {}, headers=headers or {})
    response.request = httpx.Request("POST", "https://api.example/generateContent")
    return response


def _ok_response(text: str) -> httpx.Response:
    return _response(
        200,
        {
            "candidates": [{"content": {"parts": [{"text": text}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        },
    )


def _rate_limited_response(retry_delay: str = "26s") -> httpx.Response:
    return _response(
        429,
        {
            "error": {
                "code": 429,
                "message": "Resource has been exhausted",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay}
                ],
            }
        },
    )


def _bare_provider(client: _StubClient) -> GeminiProvider:
    provider = GeminiProvider.__new__(GeminiProvider)
    provider._api_key = "test-key"
    provider._client = client
    provider._pacing_lock = asyncio.Lock()
    provider._next_allowed_at = 0.0
    provider._sleep = _SleepRecorder()
    return provider


def test_parse_retry_delay_prefers_retry_after_header():
    assert _parse_retry_delay(_response(429, None, {"Retry-After": "7"})) == 7.0


def test_parse_retry_delay_reads_google_retry_info():
    assert _parse_retry_delay(_rate_limited_response("26s")) == 26.0


def test_parse_retry_delay_returns_none_on_garbage():
    assert _parse_retry_delay(_response(429, {"unexpected": True})) is None


async def test_call_retries_429_using_server_retry_delay(monkeypatch):
    monkeypatch.setattr(settings, "gemini_min_request_interval", 0.0)
    stub = _StubClient([_rate_limited_response("2s"), _ok_response('{"found": true}')])
    provider = _bare_provider(stub)

    data, usage = await provider._call("gemini-3.6-flash", "sys", "user", ClauseDetectionResult)

    assert data == {"found": True}
    assert usage == {"input": 10, "output": 5}
    assert stub.calls == 2
    # waited the server-advised 2s (+ up to 1s jitter) between attempts
    assert len(provider._sleep.calls) == 1
    assert 2.0 <= provider._sleep.calls[0] <= 3.0


async def test_call_gives_up_after_max_rate_limit_attempts(monkeypatch):
    monkeypatch.setattr(settings, "gemini_min_request_interval", 0.0)
    stub = _StubClient([_rate_limited_response("1s")])  # always 429
    provider = _bare_provider(stub)

    with pytest.raises(RuntimeError, match="rate limit exceeded"):
        await provider._call("gemini-3.6-flash", "sys", "user", ClauseDetectionResult)

    assert stub.calls == _MAX_ATTEMPTS_RATE_LIMITED
    assert len(provider._sleep.calls) == _MAX_ATTEMPTS_RATE_LIMITED - 1


async def test_pace_enforces_interval_between_calls(monkeypatch):
    monkeypatch.setattr(settings, "gemini_min_request_interval", 2.0)
    provider = _bare_provider(_StubClient([]))

    await provider._pace()  # first call goes through immediately
    assert provider._sleep.calls == []

    await provider._pace()  # second call must wait ~the interval
    assert len(provider._sleep.calls) == 1
    assert 1.5 <= provider._sleep.calls[0] <= 2.0


async def test_pace_disabled_when_interval_zero(monkeypatch):
    monkeypatch.setattr(settings, "gemini_min_request_interval", 0.0)
    provider = _bare_provider(_StubClient([]))

    await provider._pace()
    await provider._pace()
    assert provider._sleep.calls == []
