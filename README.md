# Voice AI Platform

Realtime conversational AI voice agent platform — similar to Retell AI, running locally.

## Architecture

```
Browser (Next.js)
  │
  │ WebSocket (binary audio + JSON control)
  │
  ▼
FastAPI Backend
  ├── WebSocket Manager (connection registry, heartbeat, session lifecycle)
  ├── Audio Pipeline:  STT (Deepgram) → LLM (GPT-4o) → TTS (ElevenLabs)
  ├── Agent Orchestration (conversation state machine, tool calling)
  ├── Memory (short-term context + long-term pgvector RAG)
  └── Persistence (PostgreSQL + Redis)
```

### Component Communication

| From | To | Protocol | Data |
|------|----|----------|------|
| Browser | Backend | WebSocket binary frames | Raw audio chunks (16kHz PCM) |
| Browser | Backend | WebSocket JSON frames | Control messages (start, stop, interrupt, ping) |
| Backend | Deepgram | WebSocket | Streaming audio → partial/final transcripts |
| Backend | OpenAI | HTTPS streaming | Conversation context → token stream |
| Backend | ElevenLabs | HTTPS streaming | Text → audio byte stream |
| Backend | Browser | WebSocket binary frames | TTS audio chunks |
| Backend | Browser | WebSocket JSON frames | Transcripts, AI text, latency, errors |

### Latency Design

Target: **< 800ms** from end of user speech to first AI audio byte.

| Stage | Target | Strategy |
|-------|--------|----------|
| STT | < 200ms | Deepgram streaming with interim results, silence detection |
| LLM | < 300ms to first token | GPT-4o streaming, prompt caching |
| TTS | < 200ms to first byte | ElevenLabs streaming, sentence-level chunking |
| Network | < 100ms | Local deployment, binary WebSocket frames |

## Tech Stack

- **Frontend**: Next.js 15, TypeScript, TailwindCSS, Zustand, Web Audio API
- **Backend**: Python 3.12, FastAPI, asyncio, SQLAlchemy 2.0
- **AI**: OpenAI GPT-4o, Deepgram Nova-2, ElevenLabs Turbo v2.5
- **Data**: PostgreSQL 16 + pgvector, Redis 7
- **Infra**: Docker Compose, Alembic migrations

## Project Structure

```
Voice AI/
├── .env                          # Environment variables (local)
├── .env.example                  # Template for .env
├── docker-compose.yml            # Local infrastructure
├── Makefile                      # Dev commands
│
├── backend/
│   ├── pyproject.toml            # Python dependencies
│   ├── Dockerfile
│   ├── alembic.ini               # Migration config
│   ├── alembic/                  # Database migrations
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py               # FastAPI app factory
│   │   ├── config.py             # Settings (pydantic-settings)
│   │   ├── core/
│   │   │   ├── events.py         # Startup/shutdown lifecycle
│   │   │   ├── exceptions.py     # Error hierarchy + handlers
│   │   │   ├── logging.py        # Structured logging (structlog)
│   │   │   ├── middleware.py      # CORS, request ID, timing
│   │   │   └── security.py       # JWT, password hashing
│   │   ├── db/
│   │   │   ├── base.py           # SQLAlchemy base + mixins
│   │   │   ├── session.py        # Async engine + session factory
│   │   │   └── redis.py          # Redis connection manager
│   │   ├── models/
│   │   │   ├── conversation.py   # Conversation + Message models
│   │   │   └── user.py           # User model
│   │   ├── schemas/
│   │   │   ├── conversation.py   # API DTOs
│   │   │   └── websocket.py      # WS message protocol
│   │   ├── api/
│   │   │   ├── deps.py           # Dependency injection
│   │   │   └── v1/
│   │   │       ├── routes/
│   │   │       │   ├── health.py       # Health + readiness + metrics
│   │   │       │   └── conversations.py # CRUD endpoints
│   │   │       └── websockets/
│   │   │           └── voice.py        # Main voice WS endpoint
│   │   ├── websocket/
│   │   │   ├── connection.py     # VoiceConnection wrapper
│   │   │   ├── manager.py        # ConnectionManager registry
│   │   │   └── events.py         # Typed event factories
│   │   └── services/
│   │       ├── stt/              # Deepgram (Phase 3)
│   │       ├── tts/              # ElevenLabs (Phase 5)
│   │       ├── llm/              # OpenAI (Phase 4)
│   │       └── agent/            # Orchestration (Phase 4)
│   └── tests/
│       ├── conftest.py           # Fixtures
│       ├── test_health.py
│       └── test_websocket_manager.py
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── Dockerfile
│   └── src/
│       ├── app/
│       │   ├── layout.tsx        # Root layout
│       │   ├── page.tsx          # Home page (voice UI)
│       │   └── globals.css       # Design tokens + global styles
│       ├── components/
│       │   ├── connection-status.tsx
│       │   └── voice-button.tsx
│       ├── lib/
│       │   ├── websocket-client.ts  # WS client with reconnection
│       │   └── utils.ts
│       ├── stores/
│       │   └── voice-store.ts    # Zustand global state
│       └── types/
│           └── voice.ts          # Shared type definitions
│
└── infra/
    └── postgres/
        └── init.sql              # DB extensions (pgvector, uuid)
```

## Setup Instructions

### Prerequisites

- Docker Desktop (for PostgreSQL + Redis)
- Python 3.12+
- Node.js 22+

### 1. Start Infrastructure

```bash
# Start PostgreSQL and Redis
docker compose up -d postgres redis
```

### 2. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

### 4. Configure API Keys

Edit `.env` and add your API keys:
- `OPENAI_API_KEY` — from [platform.openai.com](https://platform.openai.com)
- `DEEPGRAM_API_KEY` — from [console.deepgram.com](https://console.deepgram.com)
- `ELEVENLABS_API_KEY` — from [elevenlabs.io](https://elevenlabs.io)

### 5. Verify

- Backend: http://localhost:8000/docs (Swagger UI)
- Frontend: http://localhost:3000
- Health: http://localhost:8000/api/v1/health

## Development Commands

```bash
make up                    # Start all Docker services
make down                  # Stop all services
make backend               # Run backend (outside Docker)
make frontend              # Run frontend (outside Docker)
make backend-test          # Run backend tests
make backend-lint          # Lint backend
make db-migrate msg="..."  # Create migration
make db-upgrade            # Apply migrations
```

## Testing Strategy

| Layer | Tool | What |
|-------|------|------|
| Unit | pytest | Services, connection manager, event factories |
| Integration | pytest + httpx | API endpoints, DB operations |
| WebSocket | pytest + websockets | WS lifecycle, message routing |
| Frontend | Jest + Testing Library | Components, store logic |
| E2E | Playwright | Full voice session flow |

## Scalability Considerations

**Phase 1 foundations that enable future scaling:**

1. **Stateless backend**: All session state in Redis, not process memory → horizontal scaling ready
2. **Connection manager**: Singleton per process, Redis pub/sub for cross-instance coordination
3. **Async everything**: No blocking I/O — SQLAlchemy async, aioredis, async WebSockets
4. **Database pooling**: 20 connections + 10 overflow, with health checks and recycling
5. **Modular services**: Each AI service (STT/LLM/TTS) is an independent, swappable module
6. **Docker Compose → K8s**: Services are already containerized with health checks

## Phases

- [x] **Phase 1**: Project setup, infrastructure, WebSocket manager
- [ ] **Phase 2**: Realtime audio streaming (mic capture, chunking, visualization)
- [ ] **Phase 3**: Streaming STT (Deepgram integration)
- [ ] **Phase 4**: AI agent orchestration (GPT-4o, state machine)
- [ ] **Phase 5**: Streaming TTS (ElevenLabs integration)
- [ ] **Phase 6**: Interruption handling (VAD, turn management)
- [ ] **Phase 7**: Tool calling (extensible tool registry)
- [ ] **Phase 8**: Memory + RAG (pgvector, semantic search)
- [ ] **Phase 9**: Frontend dashboard (transcript UI, analytics)
- [ ] **Phase 10**: Observability (metrics, tracing, monitoring)
- [ ] **Phase 11**: Security (auth, RBAC, rate limiting)
- [ ] **Phase 12**: Scalability (K8s, distributed WebSockets)
