# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Mimir** is a self-hosted, AI-powered second brain agent. It ingests everything you capture, organizes it autonomously via AI, connects ideas across time, and proactively resurfaces knowledge. It is NOT a chatbot — it's an agentic system that drives resurfacing and organization without manual effort.

**Current state**: All 4 phases implemented. Full capture pipeline, 7-stage processing, hybrid search + Ask mode (Q&A), agent intelligence (daily briefs, resurface, deep scans, taxonomy evolution, notifications), extended capture (Chrome extension, IMAP email, file watcher, voice), knowledge graph visualization, entity/concept pages, and export (JSON + markdown).

## Specification Documents

- **mimir-blueprint.md** — Master spec: architecture, data model, processing pipeline, API design, agent behaviors, UI, deployment, and phased roadmap
- **mimir-ai-harness-addendum.md** — Provider-agnostic AI routing layer (Ollama, Anthropic, OpenAI, Google, local Whisper) with 4 operation types: embed, extract, reason, transcribe
- **mimir-calendar-addendum.md** — Calendar integration (Google Calendar, CalDAV, ICS, Outlook), conflict detection, meeting prep, time-aware resurfacing
- **mimir-messaging-bridge-addendum.md** — Chat-app capture/query interface (WhatsApp, Telegram, SMS, Discord, Signal, Slack, Mattermost) with intent detection

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI |
| Frontend | React, TypeScript, Vite |
| LLM | Ollama (default model: gemma4) |
| Embeddings | nomic-embed-text via Ollama (768-dim) |
| Vector DB | ChromaDB (embedded mode) |
| Relational DB | SQLite + sqlite-vec |
| Task scheduling | APScheduler (in-process) |
| Deployment | Docker Compose (target: Unraid) |
| Backend packages | pip via pyproject.toml |
| Frontend packages | npm via package.json |

## Build & Run Commands

```bash
# Full stack (Docker) — primary deployment method
docker-compose up --build
# Backend: http://localhost:3080, Frontend: http://localhost:3081, Ollama: http://localhost:11434
# Note: Ollama runs CPU-only by default; uncomment GPU section in docker-compose.yml for NVIDIA

# Backend dev (local)
cd backend
python -m venv venv && source venv/bin/activate
pip install -e .
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend dev (local, proxies /api to :8000)
cd frontend
npm install                     # generates package-lock.json (required for Docker builds)
npm run dev                     # Vite dev server on :3081

# TUI (terminal interface)
cd tui
pip install -e .
mimir                           # launch TUI (connects to backend at :3080)
mimir setup                     # interactive setup wizard
mimir --url http://host:3080    # override backend URL

# Tests
cd backend && pytest
```

## Architecture

### Core Flow
```
CAPTURE → NORMALIZE → CHUNK → EXTRACT → EMBED → LINK → SYNTHESIZE → INDEX
```

Each processing stage is idempotent and independently re-runnable.

### System Components

1. **Capture Gateway** (`backend/src/capture/`) — REST API endpoints at `/api/capture/*` for notes, URLs, files, clipboard, voice, email, highlights, batch. IMAP email polling (`email_watcher.py`), inbox file watcher (`file_watcher.py`, watchdog), voice transcription. All captures return < 500ms; processing is background-queued.
2. **Processing Pipeline** (`backend/src/processing/`) — 7-stage pipeline: normalize, chunk (400-token target, 50-token overlap), extract (entities/concepts via LLM), embed, link, synthesize, index.
3. **Knowledge Store** (`backend/src/knowledge/`) — ChromaDB for vectors, SQLite for relational data + FTS. Core entities: notes, concepts, entities, connections, tags, resurface_queue, agent_log.
4. **Agent Runtime** (`backend/src/agent/`) — Background scheduled jobs: daily brief generation (configurable time), connection deep scan (6h), resurface engine (5 trigger types: strong_connection, concept_cluster, entity_recurrence, spaced_repetition, follow_up), interest signal tracking (7-day decay half-life), taxonomy evolution (weekly merge/prune), webhook notifications (Mattermost, Slack, Discord, ntfy).
5. **Search Engine** (`backend/src/search/`) — Hybrid: vector similarity + graph traversal + FTS, reciprocal rank fusion. "Ask" mode: Q&A over knowledge base with LLM-generated answers citing specific notes.
6. **AI Harness** (`backend/src/harness/`) — Provider-agnostic abstraction routing 4 operation types (embed, extract, reason, transcribe) to configurable providers. Presets: local, hybrid, cloud, budget. Hot-reloadable via API.
7. **Web Dashboard** (`frontend/src/`) — Pages: Dashboard (daily brief + resurface items), Search (with Ask mode toggle), Browse (notes/concepts tree/entities tabs), Note View, Connections (force-directed graph), Entity/Concept detail pages, Settings (agent controls, activity log, harness config, export). Persistent CaptureBar. Mobile capture at `/capture`.
8. **Chrome Extension** (`extensions/chrome/`) — Manifest V3, popup for quick capture + save page URL, context menu "Save to Mimir", content script for text selection, configurable server URL + API key.
9. **Export** (`backend/src/api/export_router.py`) — JSON full backup, markdown zip archive, single note export.
10. **TUI** (`tui/mimir_tui/`) — Full Textual terminal app. Screens: Dashboard (stats + brief + resurface), Search (with Ask mode), Browse (notes/concepts/entities tabs), NoteDetail (markdown + sidebar), Capture (modal), Connections, Agent (controls + log), Settings (harness + export). Keybindings: 1-6 switch screens, c=capture, q=quit.
11. **Setup Wizard** (`tui/mimir_tui/wizard/`) — `mimir setup` command. 4 steps: Ollama connection + model pull, AI harness preset, data paths + .env generation, capture sources (IMAP/webhook/Chrome ext). Writes config to `~/.config/mimir/tui.json`.

### Key Design Decisions

- **SQLite over Postgres**: single-file, zero-config, sufficient for single-user scale
- **ChromaDB embedded**: no separate server process needed
- **APScheduler in-process**: avoids Redis/RabbitMQ dependency
- **Agent-driven taxonomy**: concepts are auto-generated, not user-defined
- **No chat interface by design**: Mimir resurfaces knowledge proactively, not via Q&A

### Implementation Phases

1. **Phase 1 (MVP)**: FastAPI + SQLite + ChromaDB + capture API + processing pipeline + search + basic dashboard + Docker Compose -- **DONE**
2. **Phase 2 (Agent)**: connection discovery + daily briefs + resurface engine + interest signals + taxonomy evolution + notifications -- **DONE**
3. **Phase 3 (Extended Capture)**: Chrome extension + IMAP email + file watcher + voice + mobile capture -- **DONE**
4. **Phase 4 (Knowledge Graph)**: graph visualization + taxonomy tree + entity pages + "Ask" mode + export -- **DONE**
