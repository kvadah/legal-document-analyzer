"""LLM provider package — factory and re-exports."""
from __future__ import annotations

from app.core.config import settings
from app.llm.base import LLMCallLog, LLMProvider, ModelTier, StructuredResult
from app.llm.mock_provider import MockLLMProvider

_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        if settings.mock_llm:
            _provider = MockLLMProvider()
        elif settings.default_llm_provider == "anthropic":
            from app.llm.anthropic_provider import AnthropicProvider

            _provider = AnthropicProvider()
        elif settings.default_llm_provider == "openai":
            from app.llm.openai_provider import OpenAIProvider

            _provider = OpenAIProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {settings.default_llm_provider}")
    return _provider


def reset_llm_provider(provider: LLMProvider | None = None) -> None:
    global _provider
    _provider = provider


__all__ = [
    "LLMCallLog",
    "LLMProvider",
    "ModelTier",
    "StructuredResult",
    "MockLLMProvider",
    "get_llm_provider",
    "reset_llm_provider",
]
