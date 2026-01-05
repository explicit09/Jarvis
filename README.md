# J.A.R.V.I.S

**Just A Rather Very Intelligent System**

A low-latency voice AI assistant built with LiveKit Agents, featuring:

- **Sub-1 second** end-to-end latency
- **Hybrid STT**: Deepgram Nova-3 (primary) + faster-whisper (fallback)
- **Natural TTS**: ElevenLabs (low-latency, high quality)
- **Intelligent LLM**: Auto-fallback between Claude and OpenAI (latency-first)
- **Wake word**: "Jarvis" via Picovoice Porcupine
- **Extensible tools**: System control, web search, and more

## Quick Start

### 1. Clone and Install

```bash
cd J.A.R.V.I.S
cp .env.example .env
# Edit .env with your API keys
make install
```

### 2. Configure API Keys

Edit `.env` with your keys:

```bash
# Required
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_key
LIVEKIT_API_SECRET=your_secret
DEEPGRAM_API_KEY=your_key
ELEVENLABS_API_KEY=your_key

# At least one LLM
ANTHROPIC_API_KEY=your_key    # For Claude
OPENAI_API_KEY=your_key       # For GPT-4

# Wake word (optional for LiveKit mode)
PICOVOICE_ACCESS_KEY=your_key
JARVIS_WAKE_WORDS=jarvis
JARVIS_WAKE_SENSITIVITY=0.5

# Optional integrations
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=+15551234567
HOME_ASSISTANT_URL=https://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=your_token
MS_CLIENT_ID=your_client_id
MS_TENANT_ID=common
MS_CALENDAR_ID=

# UI (recommended)
JARVIS_UI_TOKEN=change_me
JARVIS_UI_HOST=127.0.0.1
JARVIS_UI_PORT=8080
JARVIS_UI_ALLOW_REMOTE=false
```

### 3. Run

```bash
# LiveKit mode (recommended)
make run

# Standalone mode with wake word
make run-standalone

# Or via installed script
jarvis-standalone

# Text command mode (tool runner)
python -m jarvis.text_mode

# Or via installed script
jarvis-text

# Web UI dashboard (local)
jarvis-ui

# macOS menu bar launcher (optional)
jarvis-tray
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         J.A.R.V.I.S                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │ Wake Word   │───▶│ VAD         │───▶│ STT                 │ │
│  │ Porcupine   │    │ Silero      │    │ Deepgram / Whisper  │ │
│  │ ("Jarvis")  │    │ (<1ms)      │    │ (streaming)         │ │
│  └─────────────┘    └─────────────┘    └──────────┬──────────┘ │
│                                                    │            │
│                                                    ▼            │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    LLM BRAIN                                ││
│  │  ┌─────────────────────────────────────────────────────┐   ││
│  │  │ Auto: Claude / OpenAI (latency-first)               │   ││
│  │  └─────────────────────────────────────────────────────┘   ││
│  │                         │                                   ││
│  │  ┌─────────────────────────────────────────────────────┐   ││
│  │  │ Tools: System │ Web Search │ Weather │ ...          │   ││
│  │  └─────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                    │            │
│                                                    ▼            │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                  TTS (streaming)                            ││
│  │            ElevenLabs (low-latency)                         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Latency Budget

| Component | Target | Actual |
|-----------|--------|--------|
| Wake word | <50ms | ~20ms |
| VAD | <10ms | <1ms |
| STT (Deepgram) | <300ms | ~200ms |
| LLM (Claude) | <500ms | ~400ms |
| TTS (ElevenLabs) | <150ms | ~100ms |
| **Total** | **<1s** | **~660ms** |

## Project Structure

```
J.A.R.V.I.S/
├── jarvis/
│   ├── main.py           # Entry point
│   ├── agent.py          # LiveKit voice agent
│   ├── config.py         # Configuration
│   ├── audio/            # Wake word, VAD
│   ├── stt/              # Speech-to-text
│   ├── llm/              # LLM integration
│   ├── tts/              # Text-to-speech
│   └── tools/            # Agent tools
├── tests/
├── .env.example
├── pyproject.toml
└── Makefile
```

## Available Tools

### System Tools
- `get_current_time` - Get time in any timezone
- `open_application` - Open apps on your computer
- `run_shell_command` - Execute shell commands (with safety checks)
- `get_system_info` - System information
- `set_volume` - Control system volume
- `toggle_dark_mode` - Toggle dark mode (macOS)

### Web Tools
- `web_search` - Search the web
- `fetch_url` - Fetch content from URLs
- `get_weather` - Get weather for any city
- `get_definition` - Look up word definitions

### Memory / Notes / Tasks
- `remember` / `recall_memory` - Long-term memory
- `add_note` / `list_notes` - Notes storage
- `add_task` / `list_tasks` / `complete_task` - Task management
- `forget_memory_by_tag` / `forget_memory_before` - Memory hygiene

### Calendar
- `add_calendar_event` / `list_calendar_events` - Local calendar events
- `outlook_list_events` / `outlook_create_event` / `outlook_delete_event` - Outlook calendar

### Daily Briefing
- `daily_brief` - Weather + tasks + calendar snapshot

### Smart Home (Home Assistant)
- `get_device_state` / `set_device_state` / `toggle_device`

### Routines
- `add_routine` / `list_routines` / `run_routine` - Automation sequences

### Contacts
- `add_contact` / `list_contacts` / `find_contact`

### Files
- `list_files` / `read_file` / `write_file` / `search_files`

### Code Analysis
- `analyze_code` / `get_project_structure` / `count_lines` / `find_todos` / `diff_files` / `explain_code`

### GitHub
- `github_list_repos` / `github_read_file` / `github_search_code` / `github_list_issues` / `github_list_prs`

### Sandboxed Commands
- `run_quick_command` - fast allowlisted host execution
- `run_sandboxed_command` - Docker sandbox (network off + read-only by default)

### Calling
- `place_call` / `send_sms` (Twilio)
- Calls can use saved contact names when available.

### Alarms
- `add_alarm` / `list_alarms` / `cancel_alarm`

### macOS
- `get_battery_status` / `get_active_app` / `reveal_in_finder`
- `send_notification`
- `play_music` / `pause_music` / `next_track` / `previous_track` / `now_playing`
- `list_apple_calendars` / `create_apple_calendar_event`
- `create_apple_reminder`

## API Key Sources

| Service | Free Tier | Sign Up |
|---------|-----------|---------|
| LiveKit Cloud | 50 hrs/month | [cloud.livekit.io](https://cloud.livekit.io) |
| Deepgram | $200 credit | [console.deepgram.com](https://console.deepgram.com) |
| ElevenLabs | Paid subscription | [elevenlabs.io](https://elevenlabs.io) |
| Twilio | Pay-as-you-go | [twilio.com](https://www.twilio.com) |
| Home Assistant | Self-hosted | [home-assistant.io](https://www.home-assistant.io) |
| Anthropic | Pay-as-you-go | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI | Pay-as-you-go | [platform.openai.com](https://platform.openai.com) |
| Picovoice | Free tier | [console.picovoice.ai](https://console.picovoice.ai) |
| Microsoft Graph | Free tier | [learn.microsoft.com/graph](https://learn.microsoft.com/graph) |

## Development

```bash
# Install dev dependencies
make dev

# Run tests
make test

# Lint and format
make lint
make format

# Run with debug logging
make run-debug
```

## Benchmarking Models

Run interactive benchmarks (tool calling + speed + your scoring):

```bash
make install
jarvis-bench --judge \
  --model openai:gpt-4o-mini \
  --model openai:gpt-5-nano \
  --model openai:gpt-5-mini \
  --model anthropic:claude-sonnet-4-20250514
```

By default, benchmarks run with a focused toolset (only the expected tools for each scenario) to reduce noise and provider payload limits. To benchmark with all tools available:

```bash
jarvis-bench --toolset full --model openai:gpt-4o-mini
```

If `jarvis-bench` is not on your PATH, run:

```bash
python3 -m jarvis.bench.runner --judge --model openai:gpt-4o-mini
```

Summarize results:

```bash
jarvis-bench-report
```

Auto-judge (LLM-as-judge) example:

```bash
jarvis-bench \
  --model openai:gpt-4o-mini \
  --auto-judge anthropic:claude-sonnet-4-20250514
```

Notes:
- GPT-5 models may require different parameters; the benchmark runner handles this automatically.
- Auto pass for tool scenarios requires both calling the expected tool and producing a final user-facing answer.

## Roadmap

- [x] Smart home integration (Home Assistant)
- [x] Local calendar and notes/tasks
- [x] Phone calling (Twilio)
- [x] Persistent memory/context (local SQLite)
- [x] macOS Calendar + Reminders + Notifications
- [ ] Desktop UI
- [ ] Mobile app

## License

MIT
