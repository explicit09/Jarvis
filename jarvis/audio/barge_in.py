"""Barge-in support for voice assistant.

Allows interrupting TTS playback when:
- User speaks (VAD-based)
- Wake word is detected

Also provides preroll audio buffer to capture speech
before wake word detection.
"""

from __future__ import annotations

import asyncio
import collections
import logging
import platform
from dataclasses import dataclass, field
from typing import Callable, Deque, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Try to import audio dependencies
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    sd = None  # type: ignore
    SOUNDDEVICE_AVAILABLE = False

try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    webrtcvad = None  # type: ignore
    WEBRTCVAD_AVAILABLE = False


@dataclass
class BargeInConfig:
    """Configuration for barge-in detection."""
    vad_aggressiveness: int = 2  # 0-3, higher = more aggressive
    min_speech_ms: int = 200  # Minimum speech duration to trigger interrupt
    preroll_ms: int = 240  # Audio to keep before speech/wake word detected
    sample_rate: int = 16000
    frame_duration_ms: int = 30  # VAD frame size


@dataclass
class PrerollBuffer:
    """Ring buffer for keeping audio before detection."""
    duration_ms: int = 240
    sample_rate: int = 16000
    _buffer: Deque[bytes] = field(default_factory=collections.deque)
    _max_frames: int = field(init=False)
    _frame_duration_ms: int = 30

    def __post_init__(self):
        self._max_frames = max(1, self.duration_ms // self._frame_duration_ms)

    def add_frame(self, frame: bytes) -> None:
        """Add a frame to the buffer."""
        self._buffer.append(frame)
        while len(self._buffer) > self._max_frames:
            self._buffer.popleft()

    def get_preroll(self) -> bytes:
        """Get all buffered audio."""
        return b"".join(self._buffer)

    def clear(self) -> None:
        """Clear the buffer."""
        self._buffer.clear()


class InterruptiblePlayer:
    """Audio player that can be interrupted by voice activity."""

    def __init__(self, config: Optional[BargeInConfig] = None):
        self.config = config or BargeInConfig()
        self.is_playing = False
        self.should_stop = False
        self._vad = None

        if WEBRTCVAD_AVAILABLE:
            self._vad = webrtcvad.Vad(self.config.vad_aggressiveness)

    async def play_with_barge_in(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        on_interrupt: Optional[Callable[[], None]] = None,
    ) -> bool:
        """
        Play audio with barge-in detection.

        Args:
            audio_data: Raw PCM audio (int16)
            sample_rate: Sample rate
            on_interrupt: Callback when interrupted

        Returns:
            True if playback completed, False if interrupted
        """
        if not SOUNDDEVICE_AVAILABLE:
            logger.warning("sounddevice not available, playing without barge-in")
            return await self._play_simple(audio_data, sample_rate)

        if not WEBRTCVAD_AVAILABLE:
            logger.warning("webrtcvad not available, playing without barge-in")
            return await self._play_simple(audio_data, sample_rate)

        # Convert audio to numpy array
        audio = np.frombuffer(audio_data, dtype=np.int16)

        self.should_stop = False
        self.is_playing = True

        # Start monitoring for interruption
        monitor_task = asyncio.create_task(self._monitor_for_interrupt())

        # Play audio in chunks
        chunk_size = int(sample_rate * 0.1)  # 100ms chunks

        try:
            for i in range(0, len(audio), chunk_size):
                if self.should_stop:
                    if on_interrupt:
                        on_interrupt()
                    return False

                chunk = audio[i:i + chunk_size]
                sd.play(chunk, sample_rate, blocking=True)
                await asyncio.sleep(0.01)  # Yield to allow interrupt check

            return True  # Completed without interruption

        finally:
            self.is_playing = False
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    async def _play_simple(self, audio_data: bytes, sample_rate: int) -> bool:
        """Simple playback without barge-in."""
        if not SOUNDDEVICE_AVAILABLE:
            # Fallback to system audio on macOS
            if platform.system() == "Darwin":
                import subprocess
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tf:
                    # Write WAV
                    import wave
                    with wave.open(tf.name, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(sample_rate)
                        wf.writeframes(audio_data)
                    subprocess.run(["afplay", tf.name], check=False)
            return True

        audio = np.frombuffer(audio_data, dtype=np.int16)
        sd.play(audio, sample_rate, blocking=True)
        return True

    async def _monitor_for_interrupt(self) -> None:
        """Monitor microphone for speech during playback."""
        if not SOUNDDEVICE_AVAILABLE or not WEBRTCVAD_AVAILABLE:
            return

        frame_duration_ms = self.config.frame_duration_ms
        sample_rate = self.config.sample_rate
        frame_size = int(sample_rate * frame_duration_ms / 1000)
        required_frames = self.config.min_speech_ms // frame_duration_ms

        try:
            stream = sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype='int16',
                blocksize=frame_size
            )
            stream.start()
            speech_frames = 0

            while self.is_playing and not self.should_stop:
                try:
                    audio_frame, _ = stream.read(frame_size)

                    if len(audio_frame) == frame_size:
                        is_speech = self._vad.is_speech(
                            audio_frame.tobytes(),
                            sample_rate
                        )

                        if is_speech:
                            speech_frames += 1
                            if speech_frames >= required_frames:
                                logger.info("Barge-in: Speech detected, interrupting")
                                self.should_stop = True
                                break
                        else:
                            speech_frames = max(0, speech_frames - 1)

                    await asyncio.sleep(0.01)

                except Exception as e:
                    logger.debug(f"Monitor error: {e}")
                    await asyncio.sleep(0.1)

            stream.stop()
            stream.close()

        except Exception as e:
            logger.debug(f"Failed to monitor: {e}")

    def stop(self) -> None:
        """Stop current playback."""
        self.should_stop = True


class AudioPrerollCapture:
    """Captures audio with preroll buffer for wake word detection."""

    def __init__(self, config: Optional[BargeInConfig] = None):
        self.config = config or BargeInConfig()
        self.preroll = PrerollBuffer(
            duration_ms=self.config.preroll_ms,
            sample_rate=self.config.sample_rate,
        )
        self._is_capturing = False
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)

    def start_capture(self) -> None:
        """Start capturing audio with preroll."""
        if not SOUNDDEVICE_AVAILABLE:
            logger.warning("sounddevice not available")
            return

        self._is_capturing = True
        frame_size = int(self.config.sample_rate * self.config.frame_duration_ms / 1000)

        def callback(indata, frames, time_info, status):
            if status:
                pass  # Ignore overruns
            frame = indata.copy().tobytes()
            self.preroll.add_frame(frame)
            try:
                self._queue.put_nowait(frame)
            except asyncio.QueueFull:
                pass

        self._stream = sd.InputStream(
            samplerate=self.config.sample_rate,
            channels=1,
            dtype='int16',
            blocksize=frame_size,
            callback=callback,
        )
        self._stream.start()

    def stop_capture(self) -> None:
        """Stop capturing audio."""
        self._is_capturing = False
        if hasattr(self, '_stream'):
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass

    def get_preroll(self) -> bytes:
        """Get preroll audio buffer."""
        return self.preroll.get_preroll()

    async def get_frame(self, timeout: float = 0.1) -> Optional[bytes]:
        """Get next audio frame."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


# Singleton instances
_interruptible_player: Optional[InterruptiblePlayer] = None
_preroll_capture: Optional[AudioPrerollCapture] = None


def get_interruptible_player(config: Optional[BargeInConfig] = None) -> InterruptiblePlayer:
    """Get or create interruptible player."""
    global _interruptible_player
    if _interruptible_player is None:
        _interruptible_player = InterruptiblePlayer(config)
    return _interruptible_player


def get_preroll_capture(config: Optional[BargeInConfig] = None) -> AudioPrerollCapture:
    """Get or create preroll capture."""
    global _preroll_capture
    if _preroll_capture is None:
        _preroll_capture = AudioPrerollCapture(config)
    return _preroll_capture
