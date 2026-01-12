"""Tests for FastAPI HTTP API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for the API."""
    from jarvis.server.app import app
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_healthz(self, client):
        """Test health check endpoint."""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["service"] == "jarvis-api"

    def test_root(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "J.A.R.V.I.S API"
        assert "endpoints" in data


class TestChatEndpoint:
    """Tests for chat endpoint."""

    def test_chat_missing_text(self, client):
        """Test chat with missing text field."""
        response = client.post("/chat", json={})
        assert response.status_code == 400
        assert "text" in response.json()["detail"].lower()

    def test_chat_empty_text(self, client):
        """Test chat with empty text."""
        response = client.post("/chat", json={"text": ""})
        assert response.status_code == 400

    def test_chat_success(self, client):
        """Test successful chat request."""
        with patch("jarvis.server.app._chat") as mock_chat:
            mock_chat.return_value = "Hello! How can I help?"

            response = client.post("/chat", json={"text": "Hello"})
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert data["response"] == "Hello! How can I help?"
            assert "metrics" in data
            assert "llm_ms" in data["metrics"]

    def test_chat_with_session_id(self, client):
        """Test chat with custom session ID."""
        with patch("jarvis.server.app._chat") as mock_chat:
            mock_chat.return_value = "Response"

            response = client.post(
                "/chat",
                json={"text": "Hello", "session_id": "test-session"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == "test-session"


class TestSpeakEndpoint:
    """Tests for text-to-speech endpoint."""

    def test_speak_missing_text(self, client):
        """Test speak with missing text field."""
        response = client.post("/speak", json={})
        assert response.status_code == 400

    def test_speak_empty_text(self, client):
        """Test speak with empty text."""
        response = client.post("/speak", json={"text": ""})
        assert response.status_code == 400

    def test_speak_success(self, client):
        """Test successful TTS request."""
        # Mock TTS to return dummy audio
        with patch("jarvis.server.app._synthesize") as mock_tts:
            # Return some fake audio data (just zeros for testing)
            mock_tts.return_value = (b"\x00" * 100, 16000)

            response = client.post("/speak", json={"text": "Hello world"})
            assert response.status_code == 200
            assert response.headers["content-type"] == "audio/wav"
            assert "X-TTS-MS" in response.headers


class TestSessionEndpoints:
    """Tests for session management endpoints."""

    def test_get_session(self, client):
        """Test getting session history."""
        response = client.get("/session/test-session")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session"
        assert "history" in data

    def test_clear_session(self, client):
        """Test clearing session history."""
        response = client.delete("/session/test-session")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["session_id"] == "test-session"


class TestMetricsEndpoint:
    """Tests for metrics endpoint."""

    def test_metrics(self, client):
        """Test Prometheus metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        # Prometheus metrics are text-based
        assert "text/plain" in response.headers["content-type"] or response.status_code == 200


class TestVoiceEndpoints:
    """Tests for voice PTT endpoints."""

    def test_voice_ptt_no_audio(self, client):
        """Test PTT without audio file."""
        response = client.post("/voice/ptt")
        assert response.status_code == 422  # Validation error

    def test_voice_ptt_success(self, client):
        """Test successful PTT request."""
        with patch("jarvis.server.app._transcribe") as mock_transcribe, \
             patch("jarvis.server.app._chat") as mock_chat:
            mock_transcribe.return_value = "Hello"
            mock_chat.return_value = "Hi there!"

            # Create a minimal WAV file
            wav_data = b"RIFF" + b"\x00" * 40  # Minimal WAV header

            response = client.post(
                "/voice/ptt",
                files={"audio": ("test.wav", wav_data, "audio/wav")},
                data={"session_id": "test"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert data["transcript"] == "Hello"
            assert data["response"] == "Hi there!"

    def test_voice_ptt_speak_success(self, client):
        """Test successful PTT with audio response."""
        with patch("jarvis.server.app._transcribe") as mock_transcribe, \
             patch("jarvis.server.app._chat") as mock_chat, \
             patch("jarvis.server.app._synthesize") as mock_synthesize:
            mock_transcribe.return_value = "Hello"
            mock_chat.return_value = "Hi there!"
            mock_synthesize.return_value = (b"\x00" * 100, 16000)

            wav_data = b"RIFF" + b"\x00" * 40

            response = client.post(
                "/voice/ptt_speak",
                files={"audio": ("test.wav", wav_data, "audio/wav")},
                data={"session_id": "test"}
            )
            assert response.status_code == 200
            assert response.headers["content-type"] == "audio/wav"
            assert "X-ASR-MS" in response.headers
            assert "X-LLM-MS" in response.headers
            assert "X-TTS-MS" in response.headers


class TestErrorHandling:
    """Tests for error handling."""

    def test_chat_internal_error(self, client):
        """Test chat endpoint handles internal errors."""
        with patch("jarvis.server.app._chat") as mock_chat:
            mock_chat.side_effect = Exception("Internal error")

            response = client.post("/chat", json={"text": "Hello"})
            assert response.status_code == 500
