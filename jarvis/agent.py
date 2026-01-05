"""J.A.R.V.I.S Voice Agent.

This is the main agent that ties together:
- Speech-to-Text (Deepgram/Whisper)
- LLM (Claude/OpenAI)
- Text-to-Speech (ElevenLabs)
- Tools
"""

from __future__ import annotations

import logging

from livekit import agents
from livekit.agents import AgentSession, Agent
from livekit.plugins import silero

from jarvis.config import config
from jarvis.llm.claude import get_system_prompt
from jarvis.llm.router import LLMProvider, LLMRouter
from jarvis.stt.deepgram import create_deepgram_stt
from jarvis.tools import get_all_tools, start_alarm_scheduler, stop_alarm_scheduler
from jarvis.tts import create_elevenlabs_tts

logger = logging.getLogger(__name__)


async def entrypoint(ctx: agents.JobContext) -> None:
    """LiveKit agent entrypoint.

    This is called by the LiveKit agent worker when a new session starts.
    """
    logger.info(f"New agent job: {ctx.job.id}")

    # Connect to the room
    await ctx.connect()

    # Get tools
    tools = get_all_tools()
    logger.info(f"Loaded {len(tools)} tools")

    # Configure LLM with auto-fallback (latency-first)
    llm_router = LLMRouter(primary_provider=LLMProvider.AUTO, enable_fallback=True)
    llm = llm_router.get_llm()

    # Create the agent session with components
    session = AgentSession(
        stt=create_deepgram_stt() if config.stt.deepgram_api_key else None,
        llm=llm,
        tts=create_elevenlabs_tts() if config.tts.elevenlabs_api_key else None,
        vad=silero.VAD.load(),
        tools=tools,
        allow_interruptions=True,
    )

    # Create the agent with instructions (fresh date/time each session)
    agent = Agent(instructions=get_system_prompt())

    # Start the session
    await session.start(agent, room=ctx.room)

    # Start the alarm scheduler (will announce alarms via session.say)
    alarm_task = start_alarm_scheduler(session.say)
    logger.info("Alarm scheduler started")

    # Send greeting
    await session.say(config.greeting)

    logger.info("J.A.R.V.I.S is ready and listening")

    # Keep running indefinitely (CLI handles shutdown)
    import asyncio
    shutdown_event = asyncio.Event()

    def on_shutdown():
        alarm_task.cancel()
        stop_alarm_scheduler()
        shutdown_event.set()

    ctx.add_shutdown_callback(on_shutdown)
    await shutdown_event.wait()


def create_worker() -> agents.WorkerOptions:
    """Create LiveKit worker options.

    Returns:
        Configured WorkerOptions instance
    """
    return agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
    )


def main():
    """Run the agent using LiveKit CLI."""
    agents.cli.run_app(create_worker())


if __name__ == "__main__":
    main()
