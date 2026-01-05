"""Hybrid STT with Deepgram primary and Whisper fallback."""

import logging
from typing import Optional

from livekit import agents
from livekit.plugins import deepgram

from jarvis.config import config

from .whisper_local import LocalWhisperSTT

logger = logging.getLogger(__name__)


class HybridSTT:
    """Hybrid Speech-to-Text with automatic failover.

    Uses Deepgram Nova-3 as primary (low latency, high accuracy)
    Falls back to local faster-whisper when Deepgram is unavailable.
    """

    def __init__(self):
        self._deepgram: Optional[deepgram.STT] = None
        self._whisper: Optional[LocalWhisperSTT] = None
        self._use_deepgram = True
        self._failover_count = 0

    def _init_deepgram(self) -> deepgram.STT:
        """Initialize Deepgram STT."""
        if self._deepgram is None:
            api_key = config.stt.deepgram_api_key
            if not api_key:
                raise ValueError("Deepgram API key not configured")

            self._deepgram = deepgram.STT(
                api_key=api_key,
                model="nova-3",
                language="en",
                smart_format=True,
                punctuate=True,
            )
            logger.info("Deepgram STT initialized")

        return self._deepgram

    def _init_whisper(self) -> LocalWhisperSTT:
        """Initialize local Whisper STT."""
        if self._whisper is None:
            self._whisper = LocalWhisperSTT()
            logger.info("Local Whisper STT initialized")

        return self._whisper

    def get_stt(self) -> deepgram.STT:
        """Get the primary STT instance for LiveKit agent.

        Returns Deepgram STT for use with LiveKit VoicePipelineAgent.
        """
        return self._init_deepgram()

    def get_fallback_stt(self) -> LocalWhisperSTT:
        """Get the fallback STT instance."""
        return self._init_whisper()

    async def handle_failover(self) -> None:
        """Handle failover to local Whisper."""
        self._failover_count += 1
        self._use_deepgram = False
        logger.warning(
            f"Failover to local Whisper (count: {self._failover_count})"
        )

    async def reset_to_primary(self) -> None:
        """Reset to primary Deepgram STT."""
        self._use_deepgram = True
        logger.info("Reset to primary Deepgram STT")

    @property
    def is_using_primary(self) -> bool:
        """Check if using primary STT."""
        return self._use_deepgram

    @property
    def failover_count(self) -> int:
        """Get the number of failovers."""
        return self._failover_count
