"""Model providers for the benchmark harness."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from jarvis.config import config


@dataclass
class ModelResponse:
    text: str
    tool_calls: list[dict[str, Any]]
    latency_ms: float


class ProviderError(RuntimeError):
    pass


class ModelProvider:
    name: str

    async def complete(
        self,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        raise NotImplementedError


class OpenAIChatProvider(ModelProvider):
    name = "openai"

    async def complete(
        self,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        if not config.llm.openai_api_key:
            raise ProviderError("OPENAI_API_KEY not configured.")

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        # GPT-5 models don't support custom temperature (only default 1)
        if not model.lower().startswith("gpt-5"):
            payload["temperature"] = 0.2
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        # Some models (e.g., GPT-5*) use max_completion_tokens instead of max_tokens.
        if model.lower().startswith("gpt-5"):
            payload["max_completion_tokens"] = 2000
        else:
            payload["max_tokens"] = 800
        headers = {"Authorization": f"Bearer {config.llm.openai_api_key}"}

        # GPT-5 models have higher TTFT, increase timeout
        timeout = 60.0 if model.lower().startswith("gpt-5") else 30.0
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = response.text
                raise ProviderError(f"OpenAI error: {detail}") from exc
            data = response.json()
        latency_ms = (time.monotonic() - start) * 1000.0

        choice = data["choices"][0]["message"]
        text = (choice.get("content") or "").strip()
        tool_calls = []
        for call in choice.get("tool_calls", []) or []:
            tool_calls.append(
                {
                    "id": call.get("id"),
                    "name": call.get("function", {}).get("name"),
                    "arguments": call.get("function", {}).get("arguments"),
                }
            )
        return ModelResponse(text=text, tool_calls=tool_calls, latency_ms=latency_ms)


class AnthropicProvider(ModelProvider):
    name = "anthropic"

    async def complete(
        self,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        if not config.llm.anthropic_api_key:
            raise ProviderError("ANTHROPIC_API_KEY not configured.")

        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": 800,
            "temperature": 0.2,
            "system": system,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
        headers = {
            "x-api-key": config.llm.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = response.text
                raise ProviderError(f"Anthropic error: {detail}") from exc
            data = response.json()
        latency_ms = (time.monotonic() - start) * 1000.0

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in data.get("content", []) or []:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id"),
                        "name": block.get("name"),
                        "arguments": block.get("input"),
                    }
                )

        return ModelResponse(
            text="".join(text_parts).strip(),
            tool_calls=tool_calls,
            latency_ms=latency_ms,
        )


def get_provider(name: str) -> ModelProvider:
    name = name.strip().lower()
    if name == "openai":
        return OpenAIChatProvider()
    if name in {"anthropic", "claude"}:
        return AnthropicProvider()
    raise ProviderError(f"Unknown provider: {name}")
