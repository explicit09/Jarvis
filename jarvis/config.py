"""Configuration management for J.A.R.V.I.S."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _parse_csv_env(name: str) -> list[str]:
    """Parse a comma-separated environment variable into a list."""
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class LiveKitConfig:
    """LiveKit connection configuration."""

    url: str = field(default_factory=lambda: os.getenv("LIVEKIT_URL", ""))
    api_key: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_SECRET", ""))


@dataclass
class STTConfig:
    """Speech-to-Text configuration."""

    deepgram_api_key: str = field(default_factory=lambda: os.getenv("DEEPGRAM_API_KEY", ""))
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "base.en"))
    use_hybrid: bool = True  # Use Deepgram with Whisper fallback


@dataclass
class TTSConfig:
    """Text-to-Speech configuration."""

    elevenlabs_api_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    voice_id: str = field(
        default_factory=lambda: os.getenv(
            "ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb"  # George - British male
        )
    )
    model: str = "eleven_turbo_v2_5"
    speed: float = 1.0


@dataclass
class LLMConfig:
    """LLM configuration."""

    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    claude_model: str = field(
        default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    )
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    temperature: float = 0.7
    max_tokens: int = 1024
    auto_mode: str = field(default_factory=lambda: os.getenv("LLM_AUTO_MODE", "latency"))
    latency_probe: bool = field(
        default_factory=lambda: os.getenv("LLM_LATENCY_PROBE", "false").lower() == "true"
    )
    latency_timeout_s: float = field(
        default_factory=lambda: float(os.getenv("LLM_LATENCY_TIMEOUT_S", "4.0"))
    )


@dataclass
class WakeWordConfig:
    """Wake word detection configuration."""

    picovoice_access_key: str = field(
        default_factory=lambda: os.getenv("PICOVOICE_ACCESS_KEY", "")
    )
    keywords: list[str] = field(
        default_factory=lambda: _parse_csv_env("JARVIS_WAKE_WORDS") or ["jarvis"]
    )
    sensitivity: float = field(
        default_factory=lambda: _parse_float_env("JARVIS_WAKE_SENSITIVITY", 0.5)
    )


@dataclass
class StorageConfig:
    """Local storage configuration."""

    data_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("JARVIS_DATA_DIR", str(Path.home() / ".jarvis"))
        )
    )


@dataclass
class SafetyConfig:
    """Safety policy configuration for tools."""

    allowed_commands: list[str] = field(
        default_factory=lambda: _parse_csv_env("JARVIS_ALLOWED_COMMANDS")
    )
    allowed_paths: list[str] = field(
        default_factory=lambda: _parse_csv_env("JARVIS_ALLOWED_PATHS")
    )
    require_confirmation: bool = field(
        default_factory=lambda: os.getenv("JARVIS_REQUIRE_CONFIRMATION", "true").lower()
        != "false"
    )


@dataclass
class TwilioConfig:
    """Twilio configuration for calling and SMS."""

    account_sid: str = field(default_factory=lambda: os.getenv("TWILIO_ACCOUNT_SID", ""))
    auth_token: str = field(default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN", ""))
    from_number: str = field(default_factory=lambda: os.getenv("TWILIO_FROM_NUMBER", ""))
    default_to_number: str = field(default_factory=lambda: os.getenv("TWILIO_DEFAULT_TO_NUMBER", ""))


@dataclass
class HomeAssistantConfig:
    """Home Assistant integration configuration."""

    url: str = field(default_factory=lambda: os.getenv("HOME_ASSISTANT_URL", ""))
    token: str = field(default_factory=lambda: os.getenv("HOME_ASSISTANT_TOKEN", ""))


@dataclass
class CalendarConfig:
    """Calendar configuration."""

    timezone: str = field(default_factory=lambda: os.getenv("JARVIS_TIMEZONE", "local"))


@dataclass
class BriefingConfig:
    """Daily briefing configuration."""

    weather_city: str = field(default_factory=lambda: os.getenv("JARVIS_WEATHER_CITY", ""))
    brief_days: int = field(
        default_factory=lambda: int(os.getenv("JARVIS_BRIEF_DAYS", "7"))
    )


@dataclass
class OutlookConfig:
    """Outlook (Microsoft Graph) configuration."""

    client_id: str = field(default_factory=lambda: os.getenv("MS_CLIENT_ID", ""))
    tenant_id: str = field(default_factory=lambda: os.getenv("MS_TENANT_ID", "common"))
    calendar_id: str = field(default_factory=lambda: os.getenv("MS_CALENDAR_ID", ""))


@dataclass
class GitHubConfig:
    """GitHub configuration (read-only API)."""

    token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    allowed_owners: list[str] = field(
        default_factory=lambda: _parse_csv_env("GITHUB_ALLOWED_OWNERS")
    )
    allowed_repos: list[str] = field(
        default_factory=lambda: _parse_csv_env("GITHUB_ALLOWED_REPOS")
    )


@dataclass
class JarvisConfig:
    """Main configuration container."""

    livekit: LiveKitConfig = field(default_factory=LiveKitConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    twilio: TwilioConfig = field(default_factory=TwilioConfig)
    home_assistant: HomeAssistantConfig = field(default_factory=HomeAssistantConfig)
    calendar: CalendarConfig = field(default_factory=CalendarConfig)
    briefing: BriefingConfig = field(default_factory=BriefingConfig)
    outlook: OutlookConfig = field(default_factory=OutlookConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)

    # Agent settings
    agent_name: str = "J.A.R.V.I.S"
    greeting: str = "At your service."
    idle_timeout: float = 30.0  # Seconds before returning to wake word listening

    @classmethod
    def from_env(cls) -> "JarvisConfig":
        """Create configuration from environment variables."""
        return cls()

    def validate(self) -> list[str]:
        """Validate configuration and return list of missing required values."""
        missing = []

        if not self.livekit.url:
            missing.append("LIVEKIT_URL")
        if not self.livekit.api_key:
            missing.append("LIVEKIT_API_KEY")
        if not self.livekit.api_secret:
            missing.append("LIVEKIT_API_SECRET")
        if not self.stt.deepgram_api_key:
            missing.append("DEEPGRAM_API_KEY")
        if not self.tts.elevenlabs_api_key:
            missing.append("ELEVENLABS_API_KEY")
        if not self.llm.anthropic_api_key and not self.llm.openai_api_key:
            missing.append("ANTHROPIC_API_KEY or OPENAI_API_KEY")

        return missing


# Global config instance
config = JarvisConfig.from_env()
