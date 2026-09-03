"""LLM provider abstraction.

All LLM calls across the AI pipeline (and later RAG Q&A) go through the
`LLMProvider` protocol defined here. Providers must return schema-constrained
structured output (tool-calling on both Claude and OpenAI) — never parsed
free text.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

ModelTier = Literal["fast", "capable"]

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass
class StructuredResult:
    """Result of one structured LLM call, with call telemetry."""

    result: BaseModel
    model_version: str
    prompt_version: str
    latency_ms: int
    token_usage: dict[str, int] = field(default_factory=dict)

    def typed(self, schema: type[SchemaT]) -> SchemaT:
        """Return the inner result narrowed to the expected schema type."""
        assert isinstance(self.result, schema)
        return self.result


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol every LLM provider implements."""

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        context: list[str],
        model_tier: ModelTier,
        prompt_version: str = "unversioned",
    ) -> StructuredResult: ...


@dataclass
class LLMCallLog:
    """Telemetry record for cost tracking and reproducibility."""

    task: str
    model_version: str
    prompt_version: str
    latency_ms: int
    token_usage: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "task": self.task,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "latency_ms": self.latency_ms,
            "token_usage": self.token_usage,
        }


def elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def now_ms() -> float:
    return time.monotonic()
