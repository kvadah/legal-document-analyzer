"""LLM provider package — factory and re-exports."""
from __future__ import annotations

from app.core.config import settings
from app.llm.base import LLMCallLog, LLMProvider, ModelTier, StructuredResult
from app.llm.mock_provider import MockLLMProvider

_providers: dict[str, LLMProvider] = {}


def _build_provider(name: str) -> LLMProvider:
    if settings.mock_llm:
        return MockLLMProvider()
    if name == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if name == "openai":
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if name == "gemini":
        from app.llm.gemini_provider import GeminiProvider

        return GeminiProvider()
    raise ValueError(f"Unknown LLM provider: {name}")


def get_llm_provider(preferred: str | None = None) -> LLMProvider:
    """Return the shared provider instance.

    ``preferred`` is the org-level provider preference (09-api-spec.md §9);
    it falls back to the server default. Providers are cached per name.
    """
    name = preferred or settings.default_llm_provider
    if name not in _providers:
        _providers[name] = _build_provider(name)
    return _providers[name]


def current_provider_name(preferred: str | None = None) -> str:
    if settings.mock_llm:
        return "mock"
    return preferred or settings.default_llm_provider


def reset_llm_provider(provider: LLMProvider | None = None) -> None:
    global _providers
    _providers = {}
    if provider is not None:
        # Tests reset with a single instance that must serve every lookup.
        _providers[settings.default_llm_provider] = provider


__all__ = [
    "LLMCallLog",
    "LLMProvider",
    "ModelTier",
    "StructuredResult",
    "MockLLMProvider",
    "get_llm_provider",
    "reset_llm_provider",
    "current_provider_name",
]
