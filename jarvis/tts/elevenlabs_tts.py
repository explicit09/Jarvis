"""ElevenLabs Text-to-Speech integration."""

import logging
from typing import Optional

import httpx

from livekit.plugins import elevenlabs

from jarvis.config import config

logger = logging.getLogger(__name__)


def create_elevenlabs_tts(
    api_key: Optional[str] = None,
    voice_id: Optional[str] = None,
    model: Optional[str] = None,
    speed: Optional[float] = None,
) -> elevenlabs.TTS:
    """Create an ElevenLabs TTS instance configured for low latency."""
    key = api_key or config.tts.elevenlabs_api_key
    if not key:
        raise ValueError("ElevenLabs API key not configured")

    resolved_voice_id = voice_id or config.tts.voice_id
    resolved_model = model or config.tts.model
    resolved_speed = speed if speed is not None else config.tts.speed

    logger.info(
        "Creating ElevenLabs TTS - model: %s, voice: %s..., speed: %.2f",
        resolved_model,
        resolved_voice_id[:8],
        resolved_speed,
    )

    return elevenlabs.TTS(
        api_key=key,
        voice_id=resolved_voice_id,
        model=resolved_model,
    )


async def synthesize_speech(
    text: str,
    api_key: Optional[str] = None,
    voice_id: Optional[str] = None,
    model: Optional[str] = None,
    output_format: str = "pcm_16000",
) -> bytes:
    """Synthesize speech with ElevenLabs and return raw audio bytes."""
    key = api_key or config.tts.elevenlabs_api_key
    if not key:
        raise ValueError("ElevenLabs API key not configured")

    resolved_voice_id = voice_id or config.tts.voice_id
    resolved_model = model or config.tts.model

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{resolved_voice_id}"
    params = {"output_format": output_format}
    payload = {
        "text": text,
        "model_id": resolved_model,
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.8,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }
    headers = {
        "xi-api-key": key,
        "accept": "audio/mpeg" if output_format.startswith("mp3") else "audio/wav",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, params=params, json=payload, headers=headers)
        response.raise_for_status()
        return response.content
