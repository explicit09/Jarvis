"""Local Whisper Speech-to-Text using faster-whisper."""

import logging
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel

from jarvis.config import config

logger = logging.getLogger(__name__)


class LocalWhisperSTT:
    """Local Speech-to-Text using faster-whisper.

    Used as fallback when Deepgram is unavailable.
    """

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: str = "auto",
        compute_type: str = "auto",
    ):
        self.model_size = model_size or config.stt.whisper_model
        self.device = device
        self.compute_type = compute_type
        self._model: Optional[WhisperModel] = None

    def _load_model(self) -> None:
        """Load the Whisper model."""
        if self._model is not None:
            return

        logger.info(f"Loading faster-whisper model: {self.model_size}")

        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )

        logger.info("Whisper model loaded successfully")

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
    ) -> str:
        """Transcribe audio to text.

        Args:
            audio: Audio samples as numpy array (float32, mono)
            sample_rate: Sample rate of the audio

        Returns:
            Transcribed text
        """
        self._load_model()

        if self._model is None:
            raise RuntimeError("Whisper model not loaded")

        # Ensure audio is float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Normalize if needed
        if np.abs(audio).max() > 1.0:
            audio = audio / 32768.0

        segments, info = self._model.transcribe(
            audio,
            language="en",
            beam_size=5,
            vad_filter=False,  # Disable VAD - we do our own detection
        )

        # Combine all segments
        text = " ".join(segment.text.strip() for segment in segments)

        logger.debug(f"Whisper transcription: {text}")
        return text

    async def transcribe_async(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
    ) -> str:
        """Async wrapper for transcription."""
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.transcribe, audio, sample_rate)
