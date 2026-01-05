"""Wake word detection using OpenWakeWord (free, no API key required)."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class OpenWakeWordDetector:
    """Detects wake word using OpenWakeWord (free, local, no API key).

    Supports wake words: "hey jarvis", "alexa", "hey mycroft", etc.
    """

    def __init__(
        self,
        wake_word: str = "hey_jarvis_v0.1",
        threshold: float = 0.5,
        on_wake: Optional[Callable[[], None]] = None,
    ):
        """Initialize OpenWakeWord detector.

        Args:
            wake_word: Wake word model to use. Options:
                - "hey_jarvis_v0.1" (recommended)
                - "alexa_v0.1"
                - "hey_mycroft_v0.1"
            threshold: Detection threshold 0.0-1.0 (default 0.5)
            on_wake: Callback when wake word detected
        """
        self.wake_word = wake_word
        self.threshold = threshold
        self.on_wake = on_wake

        self._model = None
        self._stream: Optional[sd.InputStream] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._sample_rate = 16000
        self._chunk_size = 1280  # 80ms at 16kHz

    def _init_model(self) -> None:
        """Initialize OpenWakeWord model."""
        if self._model is not None:
            return

        try:
            from openwakeword.model import Model
            from openwakeword import utils

            # Download model if not present
            logger.info(f"Loading OpenWakeWord model: {self.wake_word}")
            try:
                self._model = Model(
                    wakeword_models=[self.wake_word],
                    inference_framework="onnx",
                )
            except Exception:
                logger.info(f"Downloading model: {self.wake_word}")
                utils.download_models([self.wake_word])
                self._model = Model(
                    wakeword_models=[self.wake_word],
                    inference_framework="onnx",
                )

            logger.info("OpenWakeWord model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load OpenWakeWord: {e}")
            raise

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """Process audio frames for wake word detection."""
        if status:
            logger.debug(f"Audio callback status: {status}")

        if self._model is None or not self._running:
            return

        # Convert to int16 for OpenWakeWord
        audio_frame = (indata[:, 0] * 32767).astype(np.int16)

        # Process frame
        prediction = self._model.predict(audio_frame)

        # Check if wake word detected
        for wake_word, score in prediction.items():
            if score > self.threshold:
                logger.info(f"Wake word detected: {wake_word} (score: {score:.2f})")
                # Reset model to avoid repeated detections
                self._model.reset()

                if self.on_wake and self._loop:
                    self._loop.call_soon_threadsafe(self._handle_wake)
                break

    def _handle_wake(self) -> None:
        """Handle wake word detection."""
        if self.on_wake:
            self.on_wake()

    async def start(self) -> None:
        """Start wake word detection."""
        if self._running:
            logger.warning("Wake word detector already running")
            return

        self._init_model()
        self._loop = asyncio.get_running_loop()
        self._running = True

        # Start audio stream
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype=np.float32,
            blocksize=self._chunk_size,
            callback=self._audio_callback,
        )
        self._stream.start()

        # Show friendly name in logs
        friendly_name = self.wake_word.replace("_v0.1", "").replace("_", " ").title()
        logger.info(f"Listening for wake word: \"{friendly_name}\"...")

    async def stop(self) -> None:
        """Stop wake word detection."""
        self._running = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        logger.info("Wake word detection stopped")

    async def wait_for_wake_word(self) -> str:
        """Wait for wake word and return the detected keyword."""
        wake_event = asyncio.Event()

        def on_wake():
            wake_event.set()

        self.on_wake = on_wake

        await self.start()

        try:
            await wake_event.wait()
            return self.wake_word
        finally:
            await self.stop()

    def __del__(self):
        """Cleanup resources."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
