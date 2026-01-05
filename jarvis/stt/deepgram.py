"""Deepgram Nova-3 Speech-to-Text integration."""

import logging
from typing import Optional

from livekit.plugins import deepgram

from jarvis.config import config

logger = logging.getLogger(__name__)


def create_deepgram_stt(api_key: Optional[str] = None) -> deepgram.STT:
    """Create a Deepgram STT instance configured for low latency.

    Uses Nova-3 model for best accuracy and sub-300ms latency.
    """
    key = api_key or config.stt.deepgram_api_key

    if not key:
        raise ValueError("Deepgram API key not configured")

    logger.info("Creating Deepgram STT with Nova-3 model")

    return deepgram.STT(
        api_key=key,
        model="nova-3",
        language="en",
        smart_format=True,
        punctuate=True,
        filler_words=False,
        profanity_filter=False,
    )
