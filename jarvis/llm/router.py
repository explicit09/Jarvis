"""LLM Router for intelligent model selection.

Routes requests to appropriate LLM based on:
- Complexity of the request
- Tool usage requirements
- Latency requirements
- Availability/fallback
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Optional

import httpx
from livekit.plugins import openai as livekit_openai

from jarvis.config import config

from .claude import create_claude_llm
from .openai_llm import create_openai_llm

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Available LLM providers."""

    CLAUDE = "claude"
    OPENAI = "openai"
    AUTO = "auto"


class LLMRouter:
    """Routes requests to appropriate LLM based on requirements.

    Strategy:
    - Claude: Complex reasoning, tool-heavy tasks, nuanced responses
    - OpenAI: Quick responses, simple queries, fallback

    In AUTO mode, analyzes the request to choose the best provider.
    """

    def __init__(
        self,
        primary_provider: LLMProvider = LLMProvider.CLAUDE,
        enable_fallback: bool = True,
    ):
        self.primary_provider = primary_provider
        self.enable_fallback = enable_fallback

        self._claude: Optional[livekit_openai.LLM] = None
        self._openai: Optional[livekit_openai.LLM] = None
        self._latency_ms: dict[LLMProvider, float] = {}
        self._auto_preference: list[LLMProvider] = []

        self._initialize_providers()
        self._auto_preference = self._build_auto_preference()

    def _initialize_providers(self) -> None:
        """Initialize available LLM providers."""
        # Try to initialize Claude
        if config.llm.anthropic_api_key:
            try:
                self._claude = create_claude_llm()
                logger.info("Claude LLM initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Claude: {e}")

        # Try to initialize OpenAI
        if config.llm.openai_api_key:
            try:
                self._openai = create_openai_llm()
                logger.info("OpenAI LLM initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")

        # Validate at least one provider is available
        if self._claude is None and self._openai is None:
            raise RuntimeError("No LLM providers available. Check API keys.")

    def _build_auto_preference(self) -> list[LLMProvider]:
        """Build AUTO provider preference order based on config."""
        auto_mode = config.llm.auto_mode.lower()

        if config.llm.latency_probe:
            self._latency_ms = self._probe_latencies()

        if auto_mode == "latency":
            if self._latency_ms:
                ordered = sorted(self._latency_ms.items(), key=lambda item: item[1])
                return [provider for provider, _ in ordered]
            return [LLMProvider.OPENAI, LLMProvider.CLAUDE]

        # Default to quality-first (Claude tends to be stronger reasoning)
        return [LLMProvider.CLAUDE, LLMProvider.OPENAI]

    def _probe_latencies(self) -> dict[LLMProvider, float]:
        """Probe LLM providers with a tiny request to estimate latency."""
        latencies: dict[LLMProvider, float] = {}

        if self._openai:
            latency = self._probe_openai_latency()
            if latency is not None:
                latencies[LLMProvider.OPENAI] = latency

        if self._claude:
            latency = self._probe_claude_latency()
            if latency is not None:
                latencies[LLMProvider.CLAUDE] = latency

        return latencies

    def _probe_openai_latency(self) -> Optional[float]:
        """Probe OpenAI latency with a minimal request."""
        key = config.llm.openai_api_key
        if not key:
            return None

        payload = {
            "model": config.llm.openai_model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0,
        }

        headers = {"Authorization": f"Bearer {key}"}

        try:
            start = time.monotonic()
            with httpx.Client(timeout=config.llm.latency_timeout_s) as client:
                response = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
            return (time.monotonic() - start) * 1000.0
        except Exception as exc:
            logger.warning("OpenAI latency probe failed: %s", exc)
            return None

    def _probe_claude_latency(self) -> Optional[float]:
        """Probe Claude latency with a minimal request."""
        key = config.llm.anthropic_api_key
        if not key:
            return None

        payload = {
            "model": config.llm.claude_model,
            "max_tokens": 1,
            "temperature": 0,
            "messages": [{"role": "user", "content": "ping"}],
        }

        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        try:
            start = time.monotonic()
            with httpx.Client(timeout=config.llm.latency_timeout_s) as client:
                response = client.post(
                    "https://api.anthropic.com/v1/messages",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
            return (time.monotonic() - start) * 1000.0
        except Exception as exc:
            logger.warning("Claude latency probe failed: %s", exc)
            return None

    def get_llm(
        self,
        provider: Optional[LLMProvider] = None,
    ) -> livekit_openai.LLM:
        """Get an LLM instance based on provider preference.

        Args:
            provider: Specific provider to use, or None for default

        Returns:
            LLM instance

        Raises:
            RuntimeError: If requested provider is not available
        """
        target = provider or self.primary_provider

        if target == LLMProvider.CLAUDE:
            if self._claude:
                return self._claude
            elif self.enable_fallback and self._openai:
                logger.warning("Claude unavailable, falling back to OpenAI")
                return self._openai
            else:
                raise RuntimeError("Claude LLM not available")

        elif target == LLMProvider.OPENAI:
            if self._openai:
                return self._openai
            elif self.enable_fallback and self._claude:
                logger.warning("OpenAI unavailable, falling back to Claude")
                return self._claude
            else:
                raise RuntimeError("OpenAI LLM not available")

        else:  # AUTO
            return self._select_auto()

    def _select_auto(self) -> livekit_openai.LLM:
        """Auto-select the best LLM.

        Uses latency preference when enabled; otherwise defaults to Claude
        for quality-first or OpenAI for latency-first.
        """
        for provider in self._auto_preference:
            if provider == LLMProvider.OPENAI and self._openai:
                return self._openai
            if provider == LLMProvider.CLAUDE and self._claude:
                return self._claude

        if self._openai:
            return self._openai
        if self._claude:
            return self._claude

        raise RuntimeError("No LLM providers available")

    def get_primary_llm(self) -> livekit_openai.LLM:
        """Get the primary LLM instance.

        This is the recommended way to get an LLM for the voice agent.
        """
        return self.get_llm(self.primary_provider)

    @property
    def has_claude(self) -> bool:
        """Check if Claude is available."""
        return self._claude is not None

    @property
    def has_openai(self) -> bool:
        """Check if OpenAI is available."""
        return self._openai is not None

    @property
    def available_providers(self) -> list[LLMProvider]:
        """Get list of available providers."""
        providers = []
        if self._claude:
            providers.append(LLMProvider.CLAUDE)
        if self._openai:
            providers.append(LLMProvider.OPENAI)
        return providers
