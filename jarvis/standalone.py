"""Standalone wake-word mode for local voice interaction."""

from __future__ import annotations

import asyncio
import io
import logging
import queue
import time
import wave
from dataclasses import dataclass
from typing import Optional

import numpy as np
import sounddevice as sd

from jarvis.config import config
from jarvis.llm.text_client import clear_history, generate_reply
from jarvis.tts.elevenlabs_tts import synthesize_speech

logger = logging.getLogger(__name__)


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    block_size: int = 1024
    max_seconds: float = 15.0      # Max recording time
    min_seconds: float = 2.0       # Must record at least 2 seconds
    silence_seconds: float = 2.0   # 2s of silence to stop
    silence_threshold: float = 0.003  # Very sensitive to quiet speech


def _audio_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    audio_int16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())
    return buffer.getvalue()


async def _record_until_silence(cfg: AudioConfig) -> Optional[np.ndarray]:
    audio_queue: queue.Queue[np.ndarray] = queue.Queue()
    start_time = time.monotonic()
    last_voice = None  # Only set when we first detect speech
    voice_detected = False

    def callback(indata, frames, time_info, status):
        if status:
            logger.debug("Audio status: %s", status)
        audio_queue.put(indata.copy())

    logger.info("Listening...")

    with sd.InputStream(
        samplerate=cfg.sample_rate,
        channels=1,
        dtype="float32",
        blocksize=cfg.block_size,
        callback=callback,
    ):
        frames = []
        while True:
            try:
                chunk = audio_queue.get(timeout=0.2)
            except queue.Empty:
                if time.monotonic() - start_time > cfg.max_seconds:
                    break
                continue

            frames.append(chunk)
            peak = float(np.max(np.abs(chunk)))

            # Detect voice activity
            if peak > cfg.silence_threshold:
                if not voice_detected:
                    logger.debug("Voice detected")
                    voice_detected = True
                last_voice = time.monotonic()

            elapsed = time.monotonic() - start_time

            # Max time reached
            if elapsed >= cfg.max_seconds:
                break

            # Only check for end-of-speech AFTER voice was detected
            if voice_detected and last_voice:
                silence_duration = time.monotonic() - last_voice
                if silence_duration >= cfg.silence_seconds:
                    logger.debug("End of speech detected")
                    break

            # Timeout if no voice detected after min_seconds
            if not voice_detected and elapsed >= cfg.min_seconds + 2.0:
                logger.debug("No speech detected, timing out")
                break

    if not frames:
        return None

    audio = np.concatenate(frames, axis=0).flatten()
    duration = len(audio) / cfg.sample_rate
    peak = float(np.max(np.abs(audio)))
    logger.info(f"Recorded {duration:.1f}s of audio (peak: {peak:.4f}, voice_detected: {voice_detected})")
    return audio


async def _transcribe_deepgram(audio: np.ndarray, sample_rate: int) -> str:
    import httpx

    if not config.stt.deepgram_api_key:
        return ""

    wav_bytes = _audio_to_wav_bytes(audio, sample_rate)
    headers = {"Authorization": f"Token {config.stt.deepgram_api_key}"}
    params = {
        "model": "nova-3",
        "language": "en",
        "smart_format": "true",
        "punctuate": "true",
    }

    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(
            "https://api.deepgram.com/v1/listen",
            params=params,
            headers=headers,
            content=wav_bytes,
        )
        response.raise_for_status()
        data = response.json()
        try:
            return data["results"]["channels"][0]["alternatives"][0]["transcript"].strip()
        except Exception:
            return ""


async def _transcribe_local(audio: np.ndarray, sample_rate: int) -> str:
    try:
        from jarvis.stt.whisper_local import LocalWhisperSTT
    except Exception:
        return ""

    stt = LocalWhisperSTT()
    return await stt.transcribe_async(audio, sample_rate)


async def _speak(text: str) -> None:
    """Speak text."""
    if not config.tts.elevenlabs_api_key:
        print(text)
        return

    audio_bytes = await synthesize_speech(text, output_format="pcm_16000")
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    # Simple playback - interrupt detection disabled for now
    # (requires proper echo cancellation to work correctly)
    sd.play(audio, samplerate=16000)
    sd.wait()

    # Small pause after speaking before listening
    await asyncio.sleep(0.3)


async def _handle_interaction(cfg: AudioConfig) -> bool:
    """Handle one interaction. Returns True if conversation should continue."""
    audio = await _record_until_silence(cfg)
    if audio is None:
        logger.info("No audio captured")
        return False  # No speech detected, end conversation

    # Check if we have meaningful audio (not just silence)
    # Use a very low threshold - we already did voice detection during recording
    peak = float(np.max(np.abs(audio)))
    if peak < 0.001:  # Very low - basically no signal at all
        logger.info("No audio signal detected")
        return False

    transcript = await _transcribe_deepgram(audio, cfg.sample_rate)
    if not transcript:
        transcript = await _transcribe_local(audio, cfg.sample_rate)

    if not transcript:
        await _speak("I didn't quite catch that. Could you repeat?")
        return True  # Let them try again

    # Check for conversation-ending phrases
    lower = transcript.lower().strip()
    if any(phrase in lower for phrase in ["goodbye", "bye", "that's all", "never mind", "stop", "thanks that's it"]):
        await _speak("Alright, just say Hey Jarvis if you need me.")
        return False

    logger.info("Heard: %s", transcript)
    response = await generate_reply(transcript)
    await _speak(response)
    return True  # Continue conversation


def _create_detector():
    """Create the best available wake word detector."""
    # Prefer Picovoice if API key is available (more accurate)
    if config.wake_word.picovoice_access_key:
        from jarvis.audio import WakeWordDetector

        logger.info("Using Picovoice Porcupine for wake word detection")
        return WakeWordDetector(
            access_key=config.wake_word.picovoice_access_key,
            keywords=config.wake_word.keywords,
            sensitivity=config.wake_word.sensitivity,
        )

    # Fall back to OpenWakeWord (free, no API key)
    try:
        from jarvis.audio import OpenWakeWordDetector

        logger.info("Using OpenWakeWord for wake word detection (free, no API key)")
        return OpenWakeWordDetector(
            wake_word="hey_jarvis_v0.1",
            threshold=0.5,
        )
    except ImportError:
        raise RuntimeError(
            "No wake word detector available. Either:\n"
            "  1. Set PICOVOICE_ACCESS_KEY in .env (get free key at console.picovoice.ai)\n"
            "  2. Install openwakeword: pip install openwakeword"
        )


async def main_loop() -> None:
    cfg = AudioConfig()
    detector = _create_detector()

    while True:
        logger.info("Waiting for wake word...")
        await detector.wait_for_wake_word()
        logger.info("Wake word detected")
        await _speak("At your service.")

        # Continuous conversation loop
        while True:
            keep_going = await _handle_interaction(cfg)
            if not keep_going:
                break
            # Small delay before listening for follow-up
            await asyncio.sleep(0.3)

        # Clear conversation history for next wake
        clear_history()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nGoodbye.")
    except RuntimeError as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
