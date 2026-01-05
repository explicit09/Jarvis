"""WebSocket-based voice streaming for real-time voice interaction.

This module handles:
- Audio streaming from browser via WebSocket
- Wake word detection using OpenWakeWord
- Real-time STT via Deepgram WebSocket
- LLM processing and TTS response
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import struct
import time
import wave
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable

import numpy as np
from fastapi import WebSocket, WebSocketDisconnect

from jarvis.config import config

logger = logging.getLogger(__name__)

# Try to import OpenWakeWord
try:
    import openwakeword
    from openwakeword.model import Model as OWWModel
    OWW_AVAILABLE = True
except ImportError:
    OWW_AVAILABLE = False
    logger.warning("OpenWakeWord not available")

# Try to import Deepgram
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class VoiceState(str, Enum):
    """Voice interaction states."""
    IDLE = "idle"
    LISTENING_WAKE_WORD = "listening_wake_word"
    LISTENING_SPEECH = "listening_speech"
    PROCESSING = "processing"
    SPEAKING = "speaking"


# Phrases that end the conversation
GOODBYE_PHRASES = ["goodbye", "bye", "that's all", "never mind", "stop", "thanks that's it", "thank you that's it"]


@dataclass
class AudioConfig:
    """Audio configuration."""
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1280  # 80ms at 16kHz (OpenWakeWord requirement)
    silence_seconds: float = 2.0  # Silence to end speech
    no_speech_timeout: float = 4.0  # Timeout if no speech in conversation


class WebSocketVoiceHandler:
    """Handles WebSocket voice streaming with wake word detection."""

    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.audio_config = AudioConfig()
        self.state = VoiceState.IDLE
        self._oww_model: Optional[OWWModel] = None
        self._audio_buffer: list[bytes] = []
        self._speech_buffer: list[bytes] = []
        self._silence_frames = 0
        self._speech_frames = 0
        self._running = False
        self._in_conversation = False  # True after wake word until goodbye
        self._last_speech_time: float = 0  # Track when we last heard speech
        self._conversation_silence_frames = 0  # Track silence during conversation

    async def send_event(self, event_type: str, data: dict = None):
        """Send event to client."""
        payload = {"type": event_type, "state": self.state.value}
        if data:
            payload.update(data)
        await self.ws.send_json(payload)

    def _init_wake_word(self):
        """Initialize OpenWakeWord model."""
        if not OWW_AVAILABLE:
            logger.warning("OpenWakeWord not available, skipping wake word detection")
            return

        if self._oww_model is None:
            logger.info("Loading OpenWakeWord model...")
            # Download and load the hey_jarvis model
            self._oww_model = OWWModel(
                wakeword_models=["hey_jarvis_v0.1"],
                inference_framework="onnx"
            )
            logger.info("OpenWakeWord model loaded")

    def _check_wake_word(self, audio_chunk: np.ndarray) -> bool:
        """Check if wake word is detected in audio chunk."""
        if self._oww_model is None:
            return False

        # Process audio through OpenWakeWord
        prediction = self._oww_model.predict(audio_chunk)

        # Check if any wake word score exceeds threshold
        for model_name, score in prediction.items():
            if score > 0.5:  # Threshold
                logger.info(f"Wake word detected: {model_name} (score: {score:.2f})")
                return True
        return False

    def _convert_browser_audio(self, data: bytes) -> np.ndarray:
        """Convert browser audio (Float32) to numpy array for processing."""
        # Browser sends Float32 PCM audio
        try:
            # Try Float32 format first (Web Audio API default)
            audio = np.frombuffer(data, dtype=np.float32)
            # Convert to int16 range for OpenWakeWord
            audio_int16 = (audio * 32767).astype(np.int16)
            return audio_int16
        except Exception:
            # Fallback: try Int16
            try:
                return np.frombuffer(data, dtype=np.int16)
            except Exception as e:
                logger.error(f"Failed to convert audio: {e}")
                return np.array([], dtype=np.int16)

    def _detect_speech_end(self, audio_chunk: np.ndarray, threshold: float = 0.02) -> bool:
        """Detect if speech has ended based on silence."""
        # Calculate RMS energy
        if len(audio_chunk) == 0:
            return False

        rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)) / 32768.0

        if rms < threshold:
            self._silence_frames += 1
        else:
            self._silence_frames = 0
            self._speech_frames += 1

        # End of speech: 1.5 seconds of silence after some speech
        silence_threshold = int(1.5 * self.audio_config.sample_rate / self.audio_config.chunk_size)
        min_speech = int(0.5 * self.audio_config.sample_rate / self.audio_config.chunk_size)

        return self._silence_frames > silence_threshold and self._speech_frames > min_speech

    async def _transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio using Deepgram."""
        if not HTTPX_AVAILABLE:
            return ""

        api_key = config.stt.deepgram_api_key
        if not api_key:
            logger.error("Deepgram API key not configured")
            return ""

        # Convert to WAV for Deepgram
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.audio_config.sample_rate)
            wf.writeframes(audio_data)
        wav_bytes = wav_buffer.getvalue()

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

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, params=params, headers=headers, content=wav_bytes)
                resp.raise_for_status()
                data = resp.json()

            channels = data.get("results", {}).get("channels", [])
            if channels:
                alternatives = channels[0].get("alternatives", [])
                if alternatives:
                    return alternatives[0].get("transcript", "")
        except Exception as e:
            logger.error(f"Transcription failed: {e}")

        return ""

    async def _get_llm_response(self, text: str) -> str:
        """Get LLM response."""
        from jarvis.llm.text_client import generate_reply
        return await generate_reply(text)

    async def _synthesize_speech(self, text: str) -> bytes:
        """Synthesize speech using ElevenLabs."""
        api_key = config.tts.elevenlabs_api_key
        if not api_key:
            return b""

        voice_id = config.tts.voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        payload = {
            "text": text,
            "model_id": config.tts.model,
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.8,
            }
        }
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.content
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            return b""

    def _check_goodbye(self, transcript: str) -> bool:
        """Check if transcript contains goodbye phrases."""
        lower = transcript.lower().strip()
        return any(phrase in lower for phrase in GOODBYE_PHRASES)

    async def _end_conversation(self):
        """End conversation and return to wake word mode."""
        from jarvis.llm.text_client import clear_history
        self._in_conversation = False
        self._conversation_silence_frames = 0
        clear_history()
        self.state = VoiceState.LISTENING_WAKE_WORD
        self._silence_frames = 0
        self._speech_frames = 0
        await self.send_event("listening_wake_word")
        logger.info("Conversation ended, waiting for wake word")

    async def handle_audio_chunk(self, data: bytes):
        """Process incoming audio chunk."""
        audio = self._convert_browser_audio(data)
        if len(audio) == 0:
            return

        if self.state == VoiceState.LISTENING_WAKE_WORD:
            # Check for wake word
            if self._check_wake_word(audio):
                self._in_conversation = True
                self._last_speech_time = time.time()
                self.state = VoiceState.LISTENING_SPEECH
                self._speech_buffer = []
                self._silence_frames = 0
                self._speech_frames = 0
                await self.send_event("wake_word_detected")

                # Speak acknowledgment
                self.state = VoiceState.SPEAKING
                await self.send_event("speaking", {"text": "Yes?"})
                audio_response = await self._synthesize_speech("Yes?")
                if audio_response:
                    await self.ws.send_bytes(audio_response)

                self.state = VoiceState.LISTENING_SPEECH
                self._last_speech_time = time.time()
                await self.send_event("listening_speech")

        elif self.state == VoiceState.LISTENING_SPEECH:
            # Track if there's voice activity
            rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2)) / 32768.0
            if rms > 0.02:
                self._last_speech_time = time.time()
                self._conversation_silence_frames = 0
            else:
                self._conversation_silence_frames += 1

            # Check for conversation timeout (no speech for too long)
            if self._in_conversation:
                silence_duration = time.time() - self._last_speech_time
                if silence_duration > self.audio_config.no_speech_timeout and self._speech_frames < 5:
                    logger.info("No speech detected, ending conversation")
                    await self._synthesize_and_speak("Just say Hey Jarvis if you need me.")
                    await self._end_conversation()
                    return

            # Accumulate speech
            self._speech_buffer.append(audio.tobytes())

            # Check for end of speech
            if self._detect_speech_end(audio):
                self.state = VoiceState.PROCESSING
                await self.send_event("processing")

                # Combine all speech audio
                all_audio = b"".join(self._speech_buffer)
                self._speech_buffer = []

                # Transcribe
                transcript = await self._transcribe_audio(all_audio)
                if transcript:
                    await self.send_event("transcription", {"text": transcript})
                    logger.info(f"Heard: {transcript}")

                    # Check for goodbye
                    if self._check_goodbye(transcript):
                        await self._synthesize_and_speak("Alright, just say Hey Jarvis if you need me.")
                        await self._end_conversation()
                        return

                    # Get LLM response
                    response = await self._get_llm_response(transcript)
                    await self.send_event("response", {"text": response})

                    # Synthesize and send audio
                    await self._synthesize_and_speak(response)

                    # Continue conversation - stay in LISTENING_SPEECH
                    self.state = VoiceState.LISTENING_SPEECH
                    self._silence_frames = 0
                    self._speech_frames = 0
                    self._last_speech_time = time.time()
                    await self.send_event("listening_speech")
                    logger.info("Continuing conversation, listening for follow-up...")
                else:
                    # No transcript - ask to repeat
                    await self._synthesize_and_speak("I didn't quite catch that. Could you repeat?")
                    self.state = VoiceState.LISTENING_SPEECH
                    self._silence_frames = 0
                    self._speech_frames = 0
                    self._last_speech_time = time.time()
                    await self.send_event("listening_speech")

    async def _synthesize_and_speak(self, text: str):
        """Helper to synthesize and send audio."""
        self.state = VoiceState.SPEAKING
        await self.send_event("speaking", {"text": text})
        audio_response = await self._synthesize_speech(text)
        if audio_response:
            await self.ws.send_bytes(audio_response)

    async def run(self):
        """Main WebSocket handling loop."""
        self._running = True
        self._init_wake_word()

        # Start in wake word listening mode
        self.state = VoiceState.LISTENING_WAKE_WORD
        await self.send_event("ready", {"wake_word": "Hey Jarvis"})

        try:
            while self._running:
                message = await self.ws.receive()

                if message["type"] == "websocket.disconnect":
                    break

                if message["type"] == "websocket.receive":
                    if "bytes" in message:
                        await self.handle_audio_chunk(message["bytes"])
                    elif "text" in message:
                        # Handle JSON commands
                        try:
                            cmd = json.loads(message["text"])
                            if cmd.get("type") == "stop":
                                self._running = False
                            elif cmd.get("type") == "skip_wake_word":
                                # Skip wake word, go directly to listening
                                self.state = VoiceState.LISTENING_SPEECH
                                self._speech_buffer = []
                                self._silence_frames = 0
                                self._speech_frames = 0
                                await self.send_event("listening_speech")
                        except json.JSONDecodeError:
                            pass

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self._running = False


async def voice_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for voice streaming."""
    await websocket.accept()
    logger.info("Voice WebSocket connected")

    handler = WebSocketVoiceHandler(websocket)
    await handler.run()

    logger.info("Voice WebSocket closed")
