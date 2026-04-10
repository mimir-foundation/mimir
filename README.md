<p align="center">
  <img src="(https://res.cloudinary.com/dzthkpfkn/image/upload/v1775829396/Untitled_design_ure8fc.png" alt="Mimir" width="80" />
</p>

<h1 align="center">Mimir</h1>

<p align="center">
  <strong>Self-hosted AI-powered second brain.</strong><br/>
  Capture everything. Organize nothing. Recall anything.
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> •
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#messaging-bridge">Messaging Bridge</a> •
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License" />
  <img src="https://img.shields.io/badge/runtime-Python%203.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/database-SQLite%20%2B%20ChromaDB-003B57?style=flat-square" alt="Database" />
  <img src="https://img.shields.io/badge/AI-Multi--Provider-8b5cf6?style=flat-square" alt="AI" />
  <img src="https://img.shields.io/badge/LLM-Ollama-ffffff?style=flat-square&logo=ollama" alt="Ollama" />
  <img src="https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React" />
</p>

---

## What is Mimir?

Mimir is an open-source, self-hosted personal knowledge agent that uses AI to automatically organize, connect, and resurface your information. Deploy it with a single `docker compose up` and start capturing from anywhere — Telegram, Mattermost, email, browser extension, file drops, voice memos, or API.

Named after [Mímir](https://en.wikipedia.org/wiki/M%C3%ADmir), the Norse figure renowned for wisdom and memory.

**The problem:** Your knowledge is scattered across dozens of apps, chats, bookmarks, and notes. You save things and never find them again.

**Mimir's answer:** One place to throw everything. AI handles the rest — extracting entities and concepts, generating embeddings, discovering connections between ideas captured months apart, and resurfacing the right knowledge at the right moment. Not when you ask for it — before you know you need it.

---

## Features

- **Zero-friction capture** — Telegram, Mattermost, email, Chrome extension, file watch folder, voice, clipboard, REST API
- **Autonomous processing** — 7-stage pipeline: normalize, chunk, extract, embed, link, synthesize, index
- **Semantic search** — Hybrid search combining ChromaDB vector similarity with SQLite FTS5 and knowledge graph traversal
- **RAG chat** — Ask questions about your knowledge base and get LLM-generated answers grounded in your own notes
- **Knowledge graph** — Automatic connection discovery between related captures with force-directed visualization
- **Proactive resurfacing** — Daily briefs, spaced repetition, concept clustering, entity recurrence, follow-up detection
- **Taxonomy evolution** — AI reorganizes your concept hierarchy weekly as your knowledge grows
- **Multi-provider AI** — Ollama (local/free), Anthropic, OpenAI, or Google — configured via harness presets
- **Messaging bridge** — Bidirectional Telegram and Mattermost integration for capture, search, ask, and notifications
- **Self-hosted & private** — Your data stays on your hardware. No cloud dependency required.
- **Docker-first** — Full stack runs with `make build`. No manual dependency management.

---

## Quickstart

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2+
- 8 GB+ RAM (for Ollama with gemma3)
- (Optional) API key for Anthropic/OpenAI/Google if using cloud AI presets

### 1. Clone and configure

```bash
git clone https://github.com/mimir-foundation/mimir.git
cd mimir
cp .env.example .env
```

Edit `.env` with your preferences:

```env
# AI Engine — choose a preset
HARNESS_PRESET=local          # local | hybrid | cloud | budget

# Models
LLM_MODEL=gemma3
EMBEDDING_MODEL=nomic-embed-text

# Security (optional — leave blank to disable auth)
API_KEY=

# Daily brief delivery time
BRIEF_TIME=07:00

# Cloud AI keys (only needed for hybrid/cloud presets)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
```

### 2. Start Mimir

```bash
make build
```

### 3. Open the dashboard

Navigate to [**localhost:3081**](http://localhost:3081) and start capturing.

| Service | Port | Purpose |
|---------|------|---------|
| Frontend | [localhost:3081](http://localhost:3081) | Web dashboard |
| Backend | [localhost:3080](http://localhost:3080) | FastAPI server |
| Ollama | localhost:11435 | Local LLM inference |

On first boot, Ollama pulls `gemma3` and `nomic-embed-text` (~5 GB). Subsequent starts are instant.

### Guided setup (TUI)

```bash
cd tui && pip install -e . && mimir setup
```

The wizard walks through Ollama connection, AI presets, data paths, capture sources, and messaging bridge configuration in five steps.

---

## Architecture

```
mimir/
├── backend/              Python 3.12+, FastAPI
│   └── src/
│       ├── capture/      REST endpoints, IMAP poller, file watcher
│       ├── processing/   7-stage AI pipeline
│       ├── knowledge/    SQLite + ChromaDB + document store
│       ├── search/       Hybrid search engine + Ask mode (RAG)
│       ├── agent/        Briefs, resurface, taxonomy, signals, notifications
│       ├── harness/      Provider-agnostic AI routing layer
│       └── bridge/       Telegram + Mattermost adapters
├── frontend/             React 19, TypeScript, Vite, Tailwind CSS
├── tui/                  Textual terminal app + setup wizard
├── extensions/chrome/    Manifest V3 browser extension
├── docker-compose.yml
└── Makefile
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, APScheduler |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| LLM | Ollama (gemma3 default, swappable) |
| Embeddings | nomic-embed-text via Ollama (768-dim) |
| Vector DB | ChromaDB (embedded mode) |
| Relational DB | SQLite + FTS5 |
| TUI | Textual |
| Deployment | Docker Compose |

### Intelligence Pipeline

Every capture flows through a 7-stage pipeline, each stage idempotent and independently re-runnable:

```
Capture → NORMALIZE → CHUNK → EXTRACT → EMBED → LINK → SYNTHESIZE → INDEX
              │           │        │        │       │         │
           clean &     400-tok   entities  768-d   find     generate
           structure   windows   concepts  vector  related  synthesis
                       50-tok    key claims        notes    & title
                       overlap   content type
```

### Agent Runtime

The agent layer runs autonomously on top of the knowledge store:

| Job | Schedule | What it does |
|-----|----------|-------------|
| **Daily Brief** | Configurable (default 07:00) | Morning digest: recent captures, new connections, resurface items, dangling threads, this-day-last-year |
| **Deep Scan** | Every 6 hours | Discover connections between notes via embedding similarity + LLM verification |
| **Resurface** | Every 4 hours | Five triggers: strong connections, concept clusters, entity recurrence, spaced repetition, follow-ups |
| **Taxonomy** | Weekly (Sunday 04:00) | Merge, prune, and reorganize the auto-generated concept hierarchy |
| **Signal Decay** | Continuous | 7-day half-life on interest signals from searches, views, and stars |

### Design Decisions

- **SQLite over Postgres** — single-file, zero-config, sufficient for single-user scale
- **ChromaDB embedded** — no separate vector DB server process
- **APScheduler in-process** — avoids Redis/RabbitMQ dependency
- **Agent-driven taxonomy** — concepts are auto-generated and evolved, not user-defined
- **Local-first** — no cloud dependency required; cloud providers are optional via harness presets

---

## Messaging Bridge

Mimir integrates bidirectionally with Telegram and Mattermost. Send messages to capture notes, search your knowledge base, ask questions, and receive proactive notifications — all from your chat app.

### Telegram

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_USER_ID` in `.env`
3. Start chatting with your bot

### Commands

| Command | Action |
|---------|--------|
| *any text* | Capture as note |
| *any URL* | Capture and fetch page |
| *photo / audio / file* | Capture media (audio is transcribed) |
| `/search <query>` | Hybrid search |
| `/ask <question>` | RAG Q&A with citations |
| `/brief` | Get today's daily brief |
| `/recent` | Last 5 captures |
| `/star` | Star last captured note |
| `/tag <name>` | Tag last captured note |
| `/status` | System health |

Questions ending with `?` are auto-detected as Ask queries.

### Outbound Notifications

When configured, Mimir proactively sends:
- **Daily briefs** at your configured time
- **Connection alerts** when strong new relationships are found
- **Resurface items** for high-priority knowledge

---

## Capture Methods

| Method | Description |
|--------|------------|
| **Web Dashboard** | Persistent capture bar at the top of every page |
| **Mobile** | Dedicated capture page at `/capture` |
| **Telegram** | Text, URLs, photos, voice notes, documents |
| **Mattermost** | Channel messages with slash commands |
| **Chrome Extension** | Popup capture, context menu, text selection highlights |
| **Email** | IMAP polling — forward emails directly to Mimir |
| **File Drop** | Drop into the inbox folder — auto-ingested via watchdog |
| **Voice** | Upload audio for transcription and capture |
| **REST API** | 8 endpoints: `/note`, `/url`, `/file`, `/voice`, `/clipboard`, `/highlight`, `/email`, `/batch` |

---

## AI Harness Presets

| Preset | Embeddings | Reasoning | Cost |
|--------|-----------|-----------|------|
| **local** | Ollama | Ollama | Free |
| **hybrid** | Ollama | Cloud API | Low |
| **cloud** | Cloud API | Cloud API | Higher |
| **budget** | Ollama | Cheap cloud model | Minimal |

Switch presets at any time from Settings or via `PUT /api/harness/presets/{name}/apply`.

---

## API

Full Swagger documentation at [localhost:3080/docs](http://localhost:3080/docs) when running.

```
POST   /api/capture/note            Capture text
POST   /api/capture/url             Capture URL (auto-fetches)
POST   /api/capture/file            Upload file
POST   /api/capture/voice           Upload audio (transcribed)
GET    /api/search?q=...            Hybrid search
GET    /api/search?q=...&mode=ask   Ask a question (RAG)
GET    /api/notes                   Browse notes
GET    /api/agent/brief             Daily brief
GET    /api/graph                   Knowledge graph
GET    /api/bridge/status           Messaging bridge health
GET    /api/export/json             Full JSON backup
GET    /api/export/markdown         Markdown zip archive
```

---

## Development

```bash
# Install all dependencies
make install

# Start frontend dev server (HMR on :3081, proxies to :8000)
make dev-frontend

# Start backend dev server (auto-reload on :8000)
make dev-backend

# Run tests
make test

# Tail logs (Docker)
make logs
```

---

## Roadmap

- [x] FastAPI backend + SQLite + ChromaDB
- [x] 7-stage processing pipeline
- [x] Hybrid search (vector + FTS + graph) with reciprocal rank fusion
- [x] Ask mode — RAG Q&A with citations
- [x] Agent runtime — daily briefs, connection discovery, resurface engine
- [x] Interest signal tracking with decay
- [x] Taxonomy evolution (weekly merge/prune)
- [x] Webhook notifications (Mattermost, Slack, Discord, ntfy)
- [x] Chrome extension (Manifest V3)
- [x] IMAP email capture
- [x] File watcher (watchdog)
- [x] Voice capture with transcription
- [x] Knowledge graph visualization
- [x] Entity and concept detail pages
- [x] Export (JSON + Markdown)
- [x] React dashboard with Tailwind
- [x] Textual TUI + setup wizard
- [x] Docker Compose deployment
- [x] Telegram messaging bridge
- [x] Mattermost messaging bridge
- [ ] MCP server — expose knowledge base to Claude Code and other MCP clients
- [ ] WhatsApp capture via Baileys
- [ ] Discord capture via Discord.js
- [ ] Calendar integration (Google Calendar, CalDAV, ICS)
- [ ] Mobile app
- [ ] Helm chart for Kubernetes

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick version

1. Fork the repo
2. Create a feature branch (`feature/your-feature`)
3. Make your changes
4. Open a PR against `main`

---

## Community

- [GitHub Discussions](https://github.com/mimir-foundation/mimir/discussions) — Questions, ideas, show & tell
- [Issues](https://github.com/mimir-foundation/mimir/issues) — Bug reports and feature requests

---

## License

[MIT](LICENSE) — use it, fork it, self-host it, build on it.

---

<p align="center">
  <sub>Built by <a href="https://github.com/mimir-foundation">Mimir Foundation</a> — because your knowledge deserves better than 47 open browser tabs.</sub>
</p>
