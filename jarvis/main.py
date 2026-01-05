"""J.A.R.V.I.S - Main Entry Point.

Run with: python -m jarvis.main
Or via LiveKit CLI: livekit-agents start jarvis.agent
"""

from __future__ import annotations

import logging
import sys

from jarvis.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jarvis")


def validate_config() -> bool:
    """Validate required configuration."""
    missing = config.validate()
    if missing:
        logger.error("Missing required configuration:")
        for key in missing:
            logger.error(f"  - {key}")
        logger.error("")
        logger.error("Please copy .env.example to .env and add your API keys")
        return False
    return True


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="J.A.R.V.I.S - Just A Rather Very Intelligent System"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate configuration and exit",
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate configuration
    if not validate_config():
        if args.validate:
            logger.info("Configuration validation failed")
        sys.exit(1)

    if args.validate:
        logger.info("Configuration validated successfully!")
        logger.info(f"Agent name: {config.agent_name}")
        logger.info(f"LiveKit URL: {config.livekit.url}")
        logger.info(f"STT: Deepgram Nova-3")
        logger.info(f"TTS: ElevenLabs {config.tts.model}")
        logger.info(f"LLM auto mode: {config.llm.auto_mode}")
        sys.exit(0)

    # Run the agent via LiveKit CLI
    logger.info("Starting J.A.R.V.I.S...")
    logger.info("Use 'python -m jarvis.agent' to run with LiveKit CLI")

    from jarvis.agent import main as agent_main
    agent_main()


if __name__ == "__main__":
    main()
