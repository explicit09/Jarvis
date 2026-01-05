"""OpenAI LLM integration.

Used as fallback or for specific use cases where GPT models excel.
"""

import logging
from typing import Optional

from livekit.plugins import openai as livekit_openai

from jarvis.config import config

logger = logging.getLogger(__name__)


def create_openai_llm(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> livekit_openai.LLM:
    """Create an OpenAI LLM instance for use with LiveKit.

    Args:
        api_key: OpenAI API key (defaults to config)
        model: Model name (defaults to gpt-4o-mini)
        temperature: Temperature for responses (defaults to 0.7)

    Returns:
        Configured LLM instance
    """
    key = api_key or config.llm.openai_api_key

    if not key:
        raise ValueError("OpenAI API key not configured")

    resolved_model = model or config.llm.openai_model
    resolved_temp = temperature if temperature is not None else config.llm.temperature

    logger.info(f"Creating OpenAI LLM - model: {resolved_model}")

    return livekit_openai.LLM(
        api_key=key,
        model=resolved_model,
        temperature=resolved_temp,
    )


def create_openai_realtime(
    api_key: Optional[str] = None,
    voice: str = "alloy",
) -> livekit_openai.realtime.RealtimeModel:
    """Create an OpenAI Realtime model for speech-to-speech.

    This is an alternative to the STT→LLM→TTS pipeline that uses
    OpenAI's native speech-to-speech capabilities for lower latency.

    Args:
        api_key: OpenAI API key (defaults to config)
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)

    Returns:
        Configured Realtime model
    """
    key = api_key or config.llm.openai_api_key

    if not key:
        raise ValueError("OpenAI API key not configured")

    logger.info(f"Creating OpenAI Realtime model - voice: {voice}")

    return livekit_openai.realtime.RealtimeModel(
        api_key=key,
        voice=voice,
        temperature=config.llm.temperature,
        modalities=["audio", "text"],
    )
