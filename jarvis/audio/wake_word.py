"""Wake word detection using Picovoice Porcupine."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

import numpy as np
import pvporcupine
import sounddevice as sd

from jarvis.config import config

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """Detects wake word using Picovoice Porcupine.

    Uses the built-in "Jarvis" keyword for activation.
    """

    def __init__(
        self,
        access_key: Optional[str] = None,
        keywords: Optional[list[str]] = None,
        sensitivity: float = 0.5,
        on_wake: Optional[Callable[[], None]] = None,
    ):
        self.access_key = access_key or config.wake_word.picovoice_access_key
        self.keywords = keywords or config.wake_word.keywords
        self.sensitivity = sensitivity
        self.on_wake = on_wake

        self._porcupine: Optional[pvporcupine.Porcupine] = None
        self._stream: Optional[sd.InputStream] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _init_porcupine(self) -> None:
        """Initialize Porcupine wake word engine."""
        if self._porcupine is not None:
            return

        logger.info(f"Initializing Porcupine with keywords: {self.keywords}")

        self._porcupine = pvporcupine.create(
            access_key=self.access_key,
            keywords=self.keywords,
            sensitivities=[self.sensitivity] * len(self.keywords),
        )

        logger.info(
            f"Porcupine initialized - sample_rate: {self._porcupine.sample_rate}, "
            f"frame_length: {self._porcupine.frame_length}"
        )

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """Process audio frames for wake word detection."""
        if status:
            logger.warning(f"Audio callback status: {status}")

        if self._porcupine is None or not self._running:
            return

        # Convert to int16 for Porcupine
        audio_frame = (indata[:, 0] * 32767).astype(np.int16)

        # Process frame
        keyword_index = self._porcupine.process(audio_frame)

        if keyword_index >= 0:
            keyword = self.keywords[keyword_index]
            logger.info(f"Wake word detected: {keyword}")

            if self.on_wake and self._loop:
                # Schedule callback in the event loop
                self._loop.call_soon_threadsafe(self._handle_wake)

    def _handle_wake(self) -> None:
        """Handle wake word detection."""
        if self.on_wake:
            self.on_wake()

    async def start(self) -> None:
        """Start wake word detection."""
        if self._running:
            logger.warning("Wake word detector already running")
            return

        self._init_porcupine()
        self._loop = asyncio.get_running_loop()
        self._running = True

        # Start audio stream
        self._stream = sd.InputStream(
            samplerate=self._porcupine.sample_rate,
            channels=1,
            dtype=np.float32,
            blocksize=self._porcupine.frame_length,
            callback=self._audio_callback,
        )
        self._stream.start()

        logger.info("Wake word detection started - listening for 'Jarvis'...")

    async def stop(self) -> None:
        """Stop wake word detection."""
        self._running = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if self._porcupine:
            self._porcupine.delete()
            self._porcupine = None

        logger.info("Wake word detection stopped")

    async def wait_for_wake_word(self) -> str:
        """Wait for wake word and return the detected keyword."""
        wake_event = asyncio.Event()
        detected_keyword: list[str] = []

        def on_wake():
            detected_keyword.append(self.keywords[0])  # Default to first keyword
            wake_event.set()

        self.on_wake = on_wake

        await self.start()

        try:
            await wake_event.wait()
            return detected_keyword[0] if detected_keyword else "jarvis"
        finally:
            await self.stop()

    def __del__(self):
        """Cleanup resources."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
        if self._porcupine:
            self._porcupine.delete()
