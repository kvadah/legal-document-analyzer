"""OpenAI LLM provider (secondary)."""
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


class OpenAIProvider:
    """OpenAI via function-calling constrained structured output."""

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    def _model_for(self, tier: ModelTier) -> str:
        return settings.openai_model if tier == "capable" else settings.openai_fast_model

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
                "type": "function",
                "function": {
                    "name": TOOL_NAME,
                    "description": "Record the structured extraction result.",
                    "parameters": schema.model_json_schema(),
                },
            }
        ]
        response = await self._client.chat.completions.create(  # type: ignore[call-overload]
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            tools=tools,
            tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
        )
        message = response.choices[0].message
        data: dict[str, object] = {}
        if message.tool_calls:
            data = json.loads(message.tool_calls[0].function.arguments or "{}")
        usage = {
            "input": response.usage.prompt_tokens if response.usage else 0,
            "output": response.usage.completion_tokens if response.usage else 0,
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
                "provider": "openai",
                "model": model,
                "prompt_version": prompt_version,
                "latency_ms": result.latency_ms,
                "tokens": json.dumps(usage),
            },
        )
        return result
