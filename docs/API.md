# J.A.R.V.I.S HTTP API Documentation

The J.A.R.V.I.S HTTP API provides endpoints for text chat, voice processing, and text-to-speech. The server runs on port 18000 by default.

## Base URL

```
http://localhost:18000
```

## Endpoints

### Health Check

#### `GET /healthz`

Check if the API server is running.

**Response:**
```json
{
  "ok": true,
  "service": "jarvis-api"
}
```

---

#### `GET /`

Get API information and available endpoints.

**Response:**
```json
{
  "service": "J.A.R.V.I.S API",
  "version": "0.1.0",
  "endpoints": {
    "/healthz": "Health check",
    "/chat": "Text chat (POST)",
    "/speak": "Text-to-speech (POST)",
    "/voice/ptt": "Push-to-talk voice (POST)",
    "/voice/ptt_speak": "Push-to-talk with audio response (POST)",
    "/metrics": "Prometheus metrics (GET)"
  }
}
```

---

### Text Chat

#### `POST /chat`

Send a text message and receive a text response.

**Request Body:**
```json
{
  "text": "What's the weather like?",
  "session_id": "optional-session-id"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | The message to send |
| `session_id` | string | No | Session ID for conversation context (default: "default") |

**Response:**
```json
{
  "ok": true,
  "response": "I don't have access to weather data right now.",
  "session_id": "default",
  "metrics": {
    "llm_ms": 150
  }
}
```

**Error Response (400):**
```json
{
  "detail": "Missing 'text' field"
}
```

**Example:**
```bash
curl -X POST http://localhost:18000/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello JARVIS"}'
```

---

### Text-to-Speech

#### `POST /speak`

Convert text to speech audio.

**Request Body:**
```json
{
  "text": "Hello, I am JARVIS"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | Text to synthesize |

**Response:**
- **Content-Type:** `audio/wav`
- **Headers:**
  - `X-TTS-MS`: TTS processing time in milliseconds
- **Body:** WAV audio data

**Example:**
```bash
curl -X POST http://localhost:18000/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}' \
  --output speech.wav
```

---

### Push-to-Talk Voice

#### `POST /voice/ptt`

Upload audio, get transcription and text response.

**Request:**
- **Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `audio` | file | Yes | Audio file (WAV, WebM, etc.) |
| `session_id` | string | No | Session ID (query param, default: "default") |

**Response:**
```json
{
  "ok": true,
  "transcript": "What time is it?",
  "response": "The current time is 3:45 PM.",
  "session_id": "default",
  "metrics": {
    "asr_ms": 120,
    "llm_ms": 200,
    "e2e_ms": 320
  }
}
```

**Error Response (when transcription fails):**
```json
{
  "ok": false,
  "error": "Could not transcribe audio",
  "metrics": {
    "asr_ms": 50
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:18000/voice/ptt \
  -F "audio=@recording.wav" \
  -F "session_id=my-session"
```

---

#### `POST /voice/ptt_speak`

Upload audio, get audio response (full voice-to-voice pipeline).

**Request:**
- **Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `audio` | file | Yes | Audio file (WAV, WebM, etc.) |
| `session_id` | string | No | Session ID (query param, default: "default") |

**Response:**
- **Content-Type:** `audio/wav`
- **Headers:**
  - `X-Transcript`: Transcribed text (truncated to 100 chars)
  - `X-ASR-MS`: ASR processing time
  - `X-LLM-MS`: LLM processing time
  - `X-TTS-MS`: TTS processing time
  - `X-E2E-MS`: End-to-end processing time
- **Body:** WAV audio data

**Example:**
```bash
curl -X POST http://localhost:18000/voice/ptt_speak \
  -F "audio=@recording.wav" \
  --output response.wav
```

---

### Session Management

#### `GET /session/{session_id}`

Get conversation history for a session.

**Response:**
```json
{
  "session_id": "my-session",
  "history": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
  ]
}
```

---

#### `DELETE /session/{session_id}`

Clear conversation history for a session.

**Response:**
```json
{
  "ok": true,
  "session_id": "my-session"
}
```

---

### Metrics

#### `GET /metrics`

Prometheus-compatible metrics endpoint.

**Response:**
- **Content-Type:** `text/plain`
- **Body:** Prometheus metrics in text format

Available metrics:
- `jarvis_requests_total` - Total API requests (by endpoint, method, status)
- `jarvis_asr_latency_seconds` - ASR processing latency
- `jarvis_llm_latency_seconds` - LLM processing latency
- `jarvis_tts_latency_seconds` - TTS processing latency
- `jarvis_e2e_latency_seconds` - End-to-end latency
- `jarvis_service_up` - Service health status

---

### WebSocket Voice Streaming

#### `WS /ws/voice`

Real-time voice streaming via WebSocket.

**Protocol:**
1. Client connects to WebSocket
2. Server sends ready event with initial state
3. Client sends binary audio chunks (Float32 PCM, 16kHz)
4. Server sends events and audio responses

**Events from Server:**
```json
{"type": "ready", "state": "listening_wake_word", "wake_word": "Hey Jarvis"}
{"type": "wake_word_detected", "state": "listening_speech"}
{"type": "transcription", "state": "processing", "text": "..."}
{"type": "response", "state": "speaking", "text": "..."}
```

**Commands to Server:**
```json
{"type": "skip_wake_word"}  // Skip wake word, start listening immediately
{"type": "stop"}            // Stop and disconnect
```

**Binary Data:**
- Client → Server: Float32 PCM audio chunks (16kHz)
- Server → Client: MP3 audio for TTS playback

---

## Error Handling

All endpoints return standard HTTP status codes:

| Status | Description |
|--------|-------------|
| 200 | Success |
| 400 | Bad Request (missing or invalid parameters) |
| 422 | Validation Error (malformed request) |
| 500 | Internal Server Error |

Error responses include a `detail` field:
```json
{
  "detail": "Error description"
}
```

---

## Running the Server

```bash
# Start with default settings (0.0.0.0:18000)
jarvis-server

# Custom host and port
jarvis-server --host 127.0.0.1 --port 8000

# Debug mode
jarvis-server --debug
```

---

## Environment Variables

The API server uses these environment variables (from `.env`):

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `OPENAI_API_KEY` | OpenAI API key (fallback) |
| `DEEPGRAM_API_KEY` | Deepgram API key for STT |
| `ELEVENLABS_API_KEY` | ElevenLabs API key for TTS |

---

## Rate Limiting

Currently no rate limiting is implemented. For production use, consider adding a reverse proxy (nginx, Caddy) with rate limiting.

---

## CORS

CORS is enabled for all origins by default. Modify `jarvis/server/app.py` to restrict origins for production.
