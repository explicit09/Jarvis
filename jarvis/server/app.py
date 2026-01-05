"""FastAPI application for J.A.R.V.I.S HTTP API."""

from __future__ import annotations

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import asyncio
import io
import json
import logging
import time
import wave
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from jarvis.config import config
from jarvis.server.session import session_store
from jarvis.server.metrics import (
    REQUESTS, ASR_LATENCY, LLM_LATENCY, TTS_LATENCY, E2E_LATENCY,
    prom_latest, SERVICE_UP
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="J.A.R.V.I.S API",
    description="Voice AI Assistant HTTP API",
    version="0.1.0",
)

# Enable CORS for client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Lazy imports to avoid circular dependencies
_stt_client = None
_tts_client = None
_llm_client = None


def _get_stt():
    """Get STT client (lazy load) - uses fallback ASR."""
    global _stt_client
    if _stt_client is None:
        from jarvis.stt.fallback import get_fallback_asr
        _stt_client = get_fallback_asr()
    return _stt_client


def _get_tts():
    """Get TTS client (lazy load)."""
    global _tts_client
    if _tts_client is None:
        # Import TTS - use system TTS as default for HTTP mode
        try:
            from jarvis.tts.system import SystemTTS
            _tts_client = SystemTTS()
        except ImportError:
            # Create a stub TTS that returns empty audio
            class StubTTS:
                async def synthesize(self, text: str) -> bytes:
                    logger.warning("No TTS available, returning empty audio")
                    return b""
            _tts_client = StubTTS()
    return _tts_client


def _convert_to_wav(audio_bytes: bytes) -> bytes:
    """Convert audio to WAV format if needed."""
    import io
    import subprocess
    import tempfile

    # Check if already WAV
    if audio_bytes[:4] == b'RIFF':
        return audio_bytes

    # Use ffmpeg to convert
    try:
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as in_file:
            in_file.write(audio_bytes)
            in_path = in_file.name

        out_path = in_path.replace('.webm', '.wav')

        result = subprocess.run([
            'ffmpeg', '-y', '-i', in_path,
            '-ar', '16000', '-ac', '1', '-f', 'wav', out_path
        ], capture_output=True, timeout=10)

        if result.returncode == 0:
            with open(out_path, 'rb') as f:
                wav_bytes = f.read()
            # Cleanup
            import os
            os.unlink(in_path)
            os.unlink(out_path)
            return wav_bytes
    except Exception as e:
        logger.warning(f"Audio conversion failed: {e}")

    return audio_bytes


async def _transcribe(audio_bytes: bytes) -> str:
    """Transcribe audio to text using fallback ASR."""
    # Convert to WAV if needed
    wav_bytes = _convert_to_wav(audio_bytes)
    stt = _get_stt()
    result = await stt.transcribe(wav_bytes)
    return result.text


async def _synthesize(text: str) -> tuple[bytes, int]:
    """Synthesize text to audio. Returns (audio_bytes, sample_rate)."""
    tts = _get_tts()
    audio = await tts.synthesize(text)
    return audio, 16000  # Most TTS returns 16kHz


async def _chat(text: str, session_id: str = "default") -> str:
    """Process text through LLM with tools."""
    from jarvis.llm.text_client import generate_reply
    return await generate_reply(text)


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    SERVICE_UP.labels("api").set(1)
    return {"ok": True, "service": "jarvis-api"}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "J.A.R.V.I.S API",
        "version": "0.1.0",
        "endpoints": {
            "/healthz": "Health check",
            "/chat": "Text chat (POST)",
            "/speak": "Text-to-speech (POST)",
            "/voice/ptt": "Push-to-talk voice (POST)",
            "/voice/ptt_speak": "Push-to-talk with audio response (POST)",
            "/metrics": "Prometheus metrics (GET)",
        }
    }


@app.post("/chat")
async def chat_endpoint(payload: dict[str, Any]):
    """
    Text chat endpoint.

    Request: {"text": "Hello", "session_id": "optional"}
    Response: {"ok": true, "response": "Hi there!", "metrics": {...}}
    """
    user_text = payload.get("text", "").strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Missing 'text' field")

    session_id = payload.get("session_id", "default")

    t0 = time.perf_counter()
    try:
        response = await _chat(user_text, session_id)
        llm_ms = int((time.perf_counter() - t0) * 1000)

        # Store in session
        await session_store.append_exchange(session_id, user_text, response)

        LLM_LATENCY.observe(llm_ms / 1000.0)
        REQUESTS.labels("/chat", "POST", "200").inc()

        return {
            "ok": True,
            "response": response,
            "session_id": session_id,
            "metrics": {"llm_ms": llm_ms}
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        REQUESTS.labels("/chat", "POST", "500").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/speak")
async def speak_endpoint(payload: dict[str, Any]):
    """
    Text-to-speech endpoint.

    Request: {"text": "Hello world"}
    Response: audio/wav binary
    """
    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'text' field")

    t0 = time.perf_counter()
    try:
        audio, sample_rate = await _synthesize(text)
        tts_ms = int((time.perf_counter() - t0) * 1000)

        # Convert to WAV
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(audio)

        TTS_LATENCY.observe(tts_ms / 1000.0)
        REQUESTS.labels("/speak", "POST", "200").inc()

        response = Response(content=wav_buf.getvalue(), media_type="audio/wav")
        response.headers["X-TTS-MS"] = str(tts_ms)
        return response

    except Exception as e:
        logger.error(f"TTS error: {e}")
        REQUESTS.labels("/speak", "POST", "500").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/voice/ptt")
async def voice_ptt(
    audio: UploadFile = File(...),
    session_id: str = "default"
):
    """
    Push-to-talk: Upload audio, get text response.

    Request: multipart/form-data with 'audio' file (WAV)
    Response: {"ok": true, "transcript": "...", "response": "...", "metrics": {...}}
    """
    t_start = time.perf_counter()

    try:
        audio_bytes = await audio.read()

        # ASR
        t_asr0 = time.perf_counter()
        transcript = await _transcribe(audio_bytes)
        t_asr1 = time.perf_counter()
        asr_ms = int((t_asr1 - t_asr0) * 1000)
        ASR_LATENCY.observe(asr_ms / 1000.0)

        if not transcript.strip():
            return JSONResponse({
                "ok": False,
                "error": "Could not transcribe audio",
                "metrics": {"asr_ms": asr_ms}
            })

        # LLM
        t_llm0 = time.perf_counter()
        response = await _chat(transcript, session_id)
        t_llm1 = time.perf_counter()
        llm_ms = int((t_llm1 - t_llm0) * 1000)
        LLM_LATENCY.observe(llm_ms / 1000.0)

        # Store in session
        await session_store.append_exchange(session_id, transcript, response)

        e2e_ms = int((time.perf_counter() - t_start) * 1000)
        E2E_LATENCY.observe(e2e_ms / 1000.0)
        REQUESTS.labels("/voice/ptt", "POST", "200").inc()

        return JSONResponse({
            "ok": True,
            "transcript": transcript,
            "response": response,
            "session_id": session_id,
            "metrics": {
                "asr_ms": asr_ms,
                "llm_ms": llm_ms,
                "e2e_ms": e2e_ms,
            }
        })

    except Exception as e:
        logger.error(f"Voice PTT error: {e}")
        REQUESTS.labels("/voice/ptt", "POST", "500").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/voice/ptt_speak")
async def voice_ptt_speak(
    audio: UploadFile = File(...),
    session_id: str = "default"
):
    """
    Push-to-talk with audio response: Upload audio, get audio response.

    Request: multipart/form-data with 'audio' file (WAV)
    Response: audio/wav binary with metrics in headers
    """
    t_start = time.perf_counter()

    try:
        audio_bytes = await audio.read()

        # ASR
        t_asr0 = time.perf_counter()
        transcript = await _transcribe(audio_bytes)
        t_asr1 = time.perf_counter()
        asr_ms = int((t_asr1 - t_asr0) * 1000)
        ASR_LATENCY.observe(asr_ms / 1000.0)

        if not transcript.strip():
            raise HTTPException(status_code=400, detail="Could not transcribe audio")

        # LLM
        t_llm0 = time.perf_counter()
        response_text = await _chat(transcript, session_id)
        t_llm1 = time.perf_counter()
        llm_ms = int((t_llm1 - t_llm0) * 1000)
        LLM_LATENCY.observe(llm_ms / 1000.0)

        # TTS
        t_tts0 = time.perf_counter()
        response_audio, sample_rate = await _synthesize(response_text)
        t_tts1 = time.perf_counter()
        tts_ms = int((t_tts1 - t_tts0) * 1000)
        TTS_LATENCY.observe(tts_ms / 1000.0)

        # Store in session
        await session_store.append_exchange(session_id, transcript, response_text)

        # Convert to WAV
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(response_audio)

        e2e_ms = int((time.perf_counter() - t_start) * 1000)
        E2E_LATENCY.observe(e2e_ms / 1000.0)
        REQUESTS.labels("/voice/ptt_speak", "POST", "200").inc()

        response = Response(content=wav_buf.getvalue(), media_type="audio/wav")
        response.headers.update({
            "X-Transcript": transcript[:100],  # Truncate for header
            "X-ASR-MS": str(asr_ms),
            "X-LLM-MS": str(llm_ms),
            "X-TTS-MS": str(tts_ms),
            "X-E2E-MS": str(e2e_ms),
        })
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice PTT Speak error: {e}")
        REQUESTS.labels("/voice/ptt_speak", "POST", "500").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    body, content_type = prom_latest()
    return Response(content=body, media_type=content_type)


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get conversation history for a session."""
    history = await session_store.get_history(session_id)
    return {"session_id": session_id, "history": history}


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    await session_store.clear(session_id)
    return {"ok": True, "session_id": session_id}


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time voice streaming.

    Protocol:
    - Client sends binary audio chunks (Float32 PCM, 16kHz)
    - Server sends JSON events and binary audio responses

    Events from server:
    - {"type": "ready", "state": "listening_wake_word", "wake_word": "Hey Jarvis"}
    - {"type": "wake_word_detected", "state": "listening_speech"}
    - {"type": "transcription", "state": "processing", "text": "..."}
    - {"type": "response", "state": "speaking", "text": "..."}
    - Binary audio data (MP3) for TTS playback

    Commands to server:
    - {"type": "skip_wake_word"} - Skip wake word, start listening immediately
    - {"type": "stop"} - Stop and disconnect
    """
    from jarvis.server.websocket_voice import voice_websocket_endpoint
    await voice_websocket_endpoint(websocket)


def run_server(host: str = "0.0.0.0", port: int = 18000):
    """Run the FastAPI server."""
    import uvicorn

    # Setup hub mode
    from jarvis.server.hub import setup_hub_mode
    setup_hub_mode(app)

    logger.info(f"Starting J.A.R.V.I.S API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


def main():
    """Entry point for jarvis-server command."""
    import argparse
    import logging

    parser = argparse.ArgumentParser(description="J.A.R.V.I.S HTTP API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=18000, help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
