"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest


def test_config_loads_defaults():
    """Test that config loads with default values."""
    from jarvis.config import JarvisConfig

    config = JarvisConfig()
    assert config.agent_name == "J.A.R.V.I.S"
    assert config.greeting == "At your service."


def test_config_validate_missing_keys():
    """Test that validate returns missing keys."""
    from jarvis.config import JarvisConfig

    # Create config with empty values
    with patch.dict(os.environ, {}, clear=True):
        config = JarvisConfig()
        missing = config.validate()

        assert "LIVEKIT_URL" in missing
        assert "DEEPGRAM_API_KEY" in missing


def test_config_from_env():
    """Test loading config from environment."""
    from jarvis.config import JarvisConfig

    test_env = {
        "LIVEKIT_URL": "wss://test.livekit.cloud",
        "LIVEKIT_API_KEY": "test_key",
        "LIVEKIT_API_SECRET": "test_secret",
        "DEEPGRAM_API_KEY": "test_deepgram",
        "ELEVENLABS_API_KEY": "test_elevenlabs",
        "ANTHROPIC_API_KEY": "test_anthropic",
    }

    with patch.dict(os.environ, test_env, clear=True):
        config = JarvisConfig.from_env()

        assert config.livekit.url == "wss://test.livekit.cloud"
        assert config.stt.deepgram_api_key == "test_deepgram"
        assert config.llm.anthropic_api_key == "test_anthropic"
