"""Multi-backend ASR fallback for standalone/HTTP mode.

Provides automatic failover between ASR providers:
1. Deepgram (primary - fast, accurate)
2. Local Whisper (secondary - no network required)
3. OpenAI Whisper API (tertiary - reliable cloud fallback)
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
import wave
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

import numpy as np

from jarvis.config import config

logger = logging.getLogger(__name__)

# Try to import backends
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    httpx = None  # type: ignore
    HTTPX_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None  # type: ignore
    WHISPER_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    openai = None  # type: ignore
    OPENAI_AVAILABLE = False


class ASRBackend(Enum):
    """Available ASR backends."""
    DEEPGRAM = "deepgram"
    WHISPER_LOCAL = "whisper_local"
    OPENAI_WHISPER = "openai_whisper"


@dataclass
class ASRResult:
    """Result from ASR transcription."""
    text: str
    backend: ASRBackend
    latency_ms: float
    confidence: Optional[float] = None


@dataclass
class FallbackASRConfig:
    """Configuration for fallback ASR."""
    # Backend order (first = primary)
    backend_order: list[ASRBackend] = field(default_factory=lambda: [
        ASRBackend.DEEPGRAM,
        ASRBackend.WHISPER_LOCAL,
        ASRBackend.OPENAI_WHISPER,
    ])
    # Timeouts
    deepgram_timeout: float = 5.0
    openai_timeout: float = 10.0
    # Whisper local settings
    whisper_model: str = "small"
    whisper_device: str = "auto"
    # Retry settings
    max_retries_per_backend: int = 1
    # Health check
    mark_unhealthy_after_failures: int = 3
    health_check_interval: float = 60.0


class FallbackASR:
    """Multi-backend ASR with automatic failover.

    Attempts transcription in order of configured backends,
    falling back to the next if one fails.
    """

    def __init__(self, config_obj: Optional[FallbackASRConfig] = None):
        self.config = config_obj or FallbackASRConfig()
        self._whisper_model: Optional[WhisperModel] = None
        self._backend_failures: dict[ASRBackend, int] = {b: 0 for b in ASRBackend}
        self._backend_healthy: dict[ASRBackend, bool] = {b: True for b in ASRBackend}
        self._last_health_check: dict[ASRBackend, float] = {b: 0.0 for b in ASRBackend}
        self._on_failover: Optional[Callable[[ASRBackend, ASRBackend], None]] = None

    def set_failover_callback(
        self,
        callback: Callable[[ASRBackend, ASRBackend], None]
    ) -> None:
        """Set callback for failover events. Args: (from_backend, to_backend)."""
        self._on_failover = callback

    def _check_backend_available(self, backend: ASRBackend) -> bool:
        """Check if a backend is available."""
        if backend == ASRBackend.DEEPGRAM:
            return HTTPX_AVAILABLE and bool(config.stt.deepgram_api_key)
        elif backend == ASRBackend.WHISPER_LOCAL:
            return WHISPER_AVAILABLE
        elif backend == ASRBackend.OPENAI_WHISPER:
            return OPENAI_AVAILABLE and bool(config.llm.openai_api_key)
        return False

    def _should_try_backend(self, backend: ASRBackend) -> bool:
        """Determine if we should try a backend."""
        if not self._check_backend_available(backend):
            return False

        if not self._backend_healthy[backend]:
            # Check if we should re-try unhealthy backend
            now = time.time()
            if now - self._last_health_check[backend] > self.config.health_check_interval:
                self._backend_healthy[backend] = True
                self._backend_failures[backend] = 0
                logger.info(f"Re-enabling {backend.value} for health check")
                return True
            return False

        return True

    def _mark_failure(self, backend: ASRBackend) -> None:
        """Record a failure for a backend."""
        self._backend_failures[backend] += 1
        if self._backend_failures[backend] >= self.config.mark_unhealthy_after_failures:
            self._backend_healthy[backend] = False
            self._last_health_check[backend] = time.time()
            logger.warning(f"Marking {backend.value} as unhealthy")

    def _mark_success(self, backend: ASRBackend) -> None:
        """Record a success for a backend."""
        self._backend_failures[backend] = 0
        self._backend_healthy[backend] = True

    async def _transcribe_deepgram(self, audio_bytes: bytes) -> str:
        """Transcribe using Deepgram HTTP API."""
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx not available")

        api_key = config.stt.deepgram_api_key
        if not api_key:
            raise ValueError("Deepgram API key not configured")

        url = "https://api.deepgram.com/v1/listen"
        params = {
            "model": "nova-2",
            "language": "en",
            "punctuate": "true",
            "smart_format": "true",
        }

        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "audio/wav",
        }

        async with httpx.AsyncClient(timeout=self.config.deepgram_timeout) as client:
            resp = await client.post(
                url,
                params=params,
                headers=headers,
                content=audio_bytes,
            )
            resp.raise_for_status()
            data = resp.json()

        # Extract transcript
        channels = data.get("results", {}).get("channels", [])
        if channels:
            alternatives = channels[0].get("alternatives", [])
            if alternatives:
                return alternatives[0].get("transcript", "")

        return ""

    def _transcribe_whisper_local(self, audio_bytes: bytes) -> str:
        """Transcribe using local faster-whisper."""
        if not WHISPER_AVAILABLE:
            raise RuntimeError("faster-whisper not available")

        # Load model if needed
        if self._whisper_model is None:
            logger.info(f"Loading Whisper model: {self.config.whisper_model}")
            self._whisper_model = WhisperModel(
                self.config.whisper_model,
                device=self.config.whisper_device,
                compute_type="auto",
            )

        # Convert WAV bytes to numpy array
        buf = io.BytesIO(audio_bytes)
        with wave.open(buf, 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            sample_rate = wf.getframerate()

        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        # Transcribe
        segments, _ = self._whisper_model.transcribe(
            audio,
            language="en",
            beam_size=5,
            vad_filter=False,
        )

        return " ".join(seg.text.strip() for seg in segments)

    async def _transcribe_whisper_local_async(self, audio_bytes: bytes) -> str:
        """Async wrapper for local Whisper."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._transcribe_whisper_local,
            audio_bytes
        )

    async def _transcribe_openai(self, audio_bytes: bytes) -> str:
        """Transcribe using OpenAI Whisper API."""
        if not OPENAI_AVAILABLE:
            raise RuntimeError("openai not available")

        api_key = config.llm.openai_api_key
        if not api_key:
            raise ValueError("OpenAI API key not configured")

        client = openai.AsyncOpenAI(
            api_key=api_key,
            timeout=self.config.openai_timeout,
        )

        # Create file-like object
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"

        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en",
        )

        return response.text

    async def transcribe(self, audio_bytes: bytes) -> ASRResult:
        """Transcribe audio with automatic fallback.

        Args:
            audio_bytes: WAV audio data

        Returns:
            ASRResult with transcription and metadata
        """
        last_error = None
        tried_backends = []

        for backend in self.config.backend_order:
            if not self._should_try_backend(backend):
                continue

            tried_backends.append(backend)
            start_time = time.time()

            for attempt in range(self.config.max_retries_per_backend):
                try:
                    if backend == ASRBackend.DEEPGRAM:
                        text = await self._transcribe_deepgram(audio_bytes)
                    elif backend == ASRBackend.WHISPER_LOCAL:
                        text = await self._transcribe_whisper_local_async(audio_bytes)
                    elif backend == ASRBackend.OPENAI_WHISPER:
                        text = await self._transcribe_openai(audio_bytes)
                    else:
                        continue

                    latency_ms = (time.time() - start_time) * 1000
                    self._mark_success(backend)

                    logger.debug(
                        f"ASR {backend.value}: '{text[:50]}...' ({latency_ms:.0f}ms)"
                    )

                    return ASRResult(
                        text=text,
                        backend=backend,
                        latency_ms=latency_ms,
                    )

                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"ASR {backend.value} attempt {attempt + 1} failed: {e}"
                    )

            # All retries failed for this backend
            self._mark_failure(backend)

            # Notify of failover
            if len(tried_backends) > 1 and self._on_failover:
                self._on_failover(tried_backends[-2], backend)

        # All backends failed
        error_msg = f"All ASR backends failed. Last error: {last_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    async def transcribe_pcm(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 16000,
        sample_width: int = 2,
        channels: int = 1,
    ) -> ASRResult:
        """Transcribe raw PCM audio (converts to WAV internally)."""
        # Convert PCM to WAV
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)

        return await self.transcribe(buf.getvalue())

    def get_backend_status(self) -> dict[str, dict]:
        """Get status of all backends."""
        return {
            backend.value: {
                "available": self._check_backend_available(backend),
                "healthy": self._backend_healthy[backend],
                "failures": self._backend_failures[backend],
            }
            for backend in ASRBackend
        }


# Global instance
_fallback_asr: Optional[FallbackASR] = None


def get_fallback_asr(config_obj: Optional[FallbackASRConfig] = None) -> FallbackASR:
    """Get or create the global fallback ASR instance."""
    global _fallback_asr
    if _fallback_asr is None:
        _fallback_asr = FallbackASR(config_obj)
    return _fallback_asr
