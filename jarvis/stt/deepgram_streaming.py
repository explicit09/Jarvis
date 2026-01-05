"""Deepgram WebSocket streaming for real-time STT.

Provides lower latency than HTTP API with:
- Partial transcripts (interim results)
- Final transcripts
- Automatic endpointing
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import wave
from typing import AsyncIterator, Callable, Optional

from jarvis.config import config

logger = logging.getLogger(__name__)

# Try to import websockets
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    websockets = None  # type: ignore
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets not installed, streaming STT disabled")


class DeepgramStreamingSTT:
    """Real-time streaming STT using Deepgram WebSocket API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "nova-2",
        language: str = "en",
        sample_rate: int = 16000,
        encoding: str = "linear16",
    ):
        self.api_key = api_key or config.stt.deepgram_api_key
        self.model = model
        self.language = language
        self.sample_rate = sample_rate
        self.encoding = encoding

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._events: asyncio.Queue[dict] = asyncio.Queue()
        self._final_text: str = ""
        self._on_partial: Optional[Callable[[str], None]] = None
        self._on_final: Optional[Callable[[str], None]] = None

    @property
    def base_url(self) -> str:
        """Get the WebSocket URL with parameters."""
        params = [
            f"model={self.model}",
            f"language={self.language}",
            f"encoding={self.encoding}",
            f"sample_rate={self.sample_rate}",
            "punctuate=true",
            "smart_format=true",
            "interim_results=true",
            "endpointing=300",  # 300ms silence = end of utterance
        ]
        return f"wss://api.deepgram.com/v1/listen?{'&'.join(params)}"

    async def connect(self) -> bool:
        """Open WebSocket connection to Deepgram."""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets package not installed")
            return False

        if not self.api_key:
            logger.error("Deepgram API key not configured")
            return False

        try:
            headers = [("Authorization", f"Token {self.api_key}")]
            self._ws = await websockets.connect(
                self.base_url,
                extra_headers=headers,
                ping_interval=20,
            )
            self._reader_task = asyncio.create_task(self._reader_loop())
            logger.info("Deepgram streaming connection opened")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Deepgram: {e}")
            return False

    async def _reader_loop(self) -> None:
        """Read messages from WebSocket."""
        if self._ws is None:
            return

        try:
            async for message in self._ws:
                try:
                    data = json.loads(message) if isinstance(message, (str, bytes)) else {}
                except Exception:
                    continue

                # Parse Deepgram response format
                channel = data.get("channel", {})
                alternatives = channel.get("alternatives", [])

                if not alternatives:
                    continue

                transcript = alternatives[0].get("transcript", "")
                is_final = channel.get("is_final", False)

                if is_final:
                    self._final_text = transcript
                    await self._events.put({"type": "final", "text": transcript})
                    if self._on_final:
                        self._on_final(transcript)
                else:
                    await self._events.put({"type": "partial", "text": transcript})
                    if self._on_partial:
                        self._on_partial(transcript)

        except Exception as e:
            logger.debug(f"Reader loop ended: {e}")

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Send audio chunk to Deepgram."""
        if self._ws is None:
            await self.connect()

        if self._ws is not None:
            try:
                await self._ws.send(audio_chunk)
            except Exception as e:
                logger.error(f"Failed to send audio: {e}")

    async def finalize(self) -> None:
        """Signal end of audio stream."""
        if self._ws is not None:
            try:
                await self._ws.send(json.dumps({"type": "Finalize"}))
            except Exception:
                pass

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        if self._ws and not self._ws.closed:
            try:
                await self._ws.close()
            except Exception:
                pass

        self._ws = None
        self._reader_task = None

    async def next_event(self, timeout: float = 0.1) -> Optional[dict]:
        """Get next event (partial or final transcript)."""
        try:
            return await asyncio.wait_for(self._events.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def wait_for_final(self, timeout: float = 5.0) -> str:
        """Wait for final transcript."""
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            if self._final_text:
                return self._final_text

            event = await self.next_event(timeout=0.1)
            if event and event.get("type") == "final":
                return event.get("text", "")

        return self._final_text

    async def transcribe_stream(
        self,
        audio_iterator: AsyncIterator[bytes],
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Transcribe streaming audio.

        Args:
            audio_iterator: Async iterator yielding audio chunks
            on_partial: Callback for partial transcripts
            on_final: Callback for final transcript

        Returns:
            Final transcript text
        """
        self._on_partial = on_partial
        self._on_final = on_final

        if not await self.connect():
            return ""

        try:
            # Stream audio
            async for chunk in audio_iterator:
                await self.send_audio(chunk)

            # Signal end
            await self.finalize()

            # Wait for final
            return await self.wait_for_final()

        finally:
            await self.close()

    async def transcribe_wav(self, wav_bytes: bytes) -> str:
        """Transcribe a complete WAV file via streaming."""
        if not await self.connect():
            return ""

        try:
            # Extract PCM from WAV
            pcm_data = self._extract_pcm(wav_bytes)
            if not pcm_data:
                return ""

            # Send in chunks
            chunk_size = int(self.sample_rate * 0.1) * 2  # 100ms chunks, 16-bit
            for i in range(0, len(pcm_data), chunk_size):
                chunk = pcm_data[i:i + chunk_size]
                await self.send_audio(chunk)
                await asyncio.sleep(0.01)  # Small delay between chunks

            # Signal end
            await self.finalize()

            # Wait for final
            return await self.wait_for_final()

        finally:
            await self.close()

    def _extract_pcm(self, wav_bytes: bytes) -> Optional[bytes]:
        """Extract PCM data from WAV file."""
        try:
            buf = io.BytesIO(wav_bytes)
            with wave.open(buf, 'rb') as wf:
                return wf.readframes(wf.getnframes())
        except Exception as e:
            logger.error(f"Failed to extract PCM: {e}")
            return None


class DeepgramSession:
    """Session-based streaming for WebSocket API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.stt.deepgram_api_key
        self._stt: Optional[DeepgramStreamingSTT] = None

    async def __aenter__(self):
        self._stt = DeepgramStreamingSTT(api_key=self.api_key)
        await self._stt.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._stt:
            await self._stt.close()

    async def send(self, audio_chunk: bytes) -> None:
        """Send audio chunk."""
        if self._stt:
            await self._stt.send_audio(audio_chunk)

    async def finalize(self) -> str:
        """Finalize and get transcript."""
        if self._stt:
            await self._stt.finalize()
            return await self._stt.wait_for_final()
        return ""

    async def next_event(self) -> Optional[dict]:
        """Get next event."""
        if self._stt:
            return await self._stt.next_event()
        return None


def pcm_to_wav_bytes(pcm_bytes: bytes, rate: int = 16000, width: int = 2, channels: int = 1) -> bytes:
    """Convert raw PCM to WAV format."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()
