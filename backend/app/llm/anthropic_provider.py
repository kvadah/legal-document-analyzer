"""Anthropic Claude LLM provider (primary, "capable" tier)."""
from __future__ import annotations

import json
import logging

from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.llm.base import ModelTier, StructuredResult, elapsed_ms, now_ms
from app.llm.prompts import GROUNDING_RULES, PROMPT_VERSION

logger = logging.getLogger(__name__)

TOOL_NAME = "record_result"

_MAX_CONTEXT_CHARS = 60_000


class AnthropicProvider:
    """Claude via tool-use constrained structured output."""

    def __init__(self) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    def _model_for(self, tier: ModelTier) -> str:
        return settings.anthropic_model if tier == "capable" else settings.anthropic_fast_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=20), reraise=True)
    async def _call(
        self,
        model: str,
        system: str,
        user_content: str,
        schema: type[BaseModel],
    ) -> tuple[dict[str, object], dict[str, int]]:
        tools: list[dict[str, object]] = [
            {
                "name": TOOL_NAME,
                "description": "Record the structured extraction result.",
                "input_schema": schema.model_json_schema(),
            }
        ]
        message = await self._client.messages.create(  # type: ignore[call-overload]
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_content}],
            tools=tools,
            tool_choice={"type": "tool", "name": TOOL_NAME},
        )
        data: dict[str, object] = {}
        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                data = dict(block.input)
                break
        usage = {
            "input": message.usage.input_tokens,
            "output": message.usage.output_tokens,
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
                "provider": "anthropic",
                "model": model,
                "prompt_version": prompt_version,
                "latency_ms": result.latency_ms,
                "tokens": json.dumps(usage),
            },
        )
        return result
