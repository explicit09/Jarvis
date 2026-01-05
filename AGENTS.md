# AGENTS.md

## Project Overview
J.A.R.V.I.S is a low-latency voice assistant built on LiveKit Agents. The core pipeline is:
Wake word (optional) -> VAD -> STT -> LLM -> TTS -> tools.

## Key Product Goals
- Optimize for latency first; default to cloud models.
- Use Deepgram for STT (primary).
- Use ElevenLabs for TTS (paid subscription is available).
- Use LLM auto-fallback between cloud providers to minimize latency.
- Provide safe, powerful tools: allowlist + confirmations for shell/system actions.
- Add core capabilities: memory, notes/tasks, calendar, smart home, file operations, and calling.

## Code Conventions
- Keep responses concise for voice; avoid verbose logs.
- Prefer explicit configuration via .env and jarvis/config.py.
- When adding tools, register them via jarvis/tools/__init__.py.
- Avoid adding heavy dependencies unless necessary for the core features above.

## Testing
- Run tests with: `make test`
- Lint with: `make lint`

## Notes for Contributors
- Align README, .env.example, and config defaults when changing providers.
- If you change tools, update `tests/test_tools.py` as needed.
