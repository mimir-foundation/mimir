# MIMIR — Self-Hosted Second Brain Agent

## Blueprint & Technical Specification v1.0

**Purpose:** A self-hosted AI agent whose sole function is to be a persistent, self-organizing second brain. Mimir ingests everything you throw at it, organizes it without your input, connects ideas across time, and resurfaces the right knowledge at the right moment — proactively.

**Target Runtime:** Docker Compose stack on Unraid (primary), with a portable `docker-compose.yml` for any Linux host.

**Design Philosophy:** Zero-friction capture. Zero-maintenance organization. Agent-driven resurfacing. Local-first, private by default.

---

## 1. SYSTEM ARCHITECTURE

### 1.1 High-Level Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MIMIR SYSTEM                                 │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────────┐│
│  │   CAPTURE    │──▶│  PROCESSING  │──▶│     KNOWLEDGE STORE      ││
│  │   GATEWAY    │   │   PIPELINE   │   │                          ││
│  │              │   │              │   │  ┌────────┐ ┌──────────┐ ││
│  │ - REST API   │   │ - Chunking   │   │  │Vector  │ │Graph DB  │ ││
│  │ - Web UI     │   │ - Embedding  │   │  │Store   │ │(SQLite)  │ ││
│  │ - Email      │   │ - Extraction │   │  │Chroma  │ │          │ ││
│  │ - File Watch │   │ - Linking    │   │  └────────┘ └──────────┘ ││
│  │ - Clipboard  │   │ - Synthesis  │   │                          ││
│  │ - Browser Ext│   │              │   │  ┌────────────────────┐  ││
│  └──────────────┘   └──────────────┘   │  │  Document Store    │  ││
│                                        │  │  (filesystem/meta) │  ││
│  ┌──────────────┐   ┌──────────────┐   │  └────────────────────┘  ││
│  │  RESURFACE   │   │    AGENT     │   └──────────────────────────┘│
│  │   ENGINE     │◀──│   RUNTIME    │                               │
│  │              │   │              │                               │
│  │ - Daily Brief│   │ - Ollama LLM │                               │
│  │ - JIT Recall │   │ - Task Queue │                               │
│  │ - Connections│   │ - Scheduler  │                               │
│  │ - Spaced Rep │   │              │                               │
│  └──────────────┘   └──────────────┘                               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │                      WEB DASHBOARD                               ││
│  │  Search | Browse | Daily Brief | Connections | Settings          ││
│  └──────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Runtime** | Python 3.12+ (FastAPI) | Async-native, rich ML/NLP ecosystem |
| **LLM Backend** | Ollama (gemma3 default, swappable) | Local, no API keys, model-agnostic |
| **Vector Store** | ChromaDB | Embedded mode, no separate server needed, good Python integration |
| **Graph/Relational DB** | SQLite + sqlite-vec | Zero-config, single-file, portable, surprisingly performant |
| **Task Queue** | APScheduler (in-process) | No Redis/RabbitMQ dependency for v1 |
| **Web UI** | React (Vite) | Fast, component-based, good for the dashboard pattern |
| **Containerization** | Docker Compose | Single `docker-compose up` deployment |
| **File Storage** | Mounted volume (`/data`) | Raw originals + processed artifacts |
| **Embedding Model** | `nomic-embed-text` via Ollama | Runs locally alongside the LLM, 768-dim, excellent quality |

### 1.3 Directory Structure

```
mimir/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── src/
│   │   ├── main.py                  # FastAPI app entry
│   │   ├── config.py                # Settings via pydantic-settings
│   │   ├── capture/
│   │   │   ├── __init__.py
│   │   │   ├── router.py            # /api/capture/* endpoints
│   │   │   ├── email_watcher.py     # IMAP polling for forwarded emails
│   │   │   ├── file_watcher.py      # Watchdog on /data/inbox/
│   │   │   └── browser_extension.py # Receives from browser ext
│   │   ├── processing/
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py          # Main orchestration
│   │   │   ├── chunker.py           # Smart text chunking
│   │   │   ├── extractor.py         # Metadata, entities, concepts
│   │   │   ├── embedder.py          # Ollama embedding calls
│   │   │   ├── linker.py            # Graph relationship builder
│   │   │   └── synthesizer.py       # LLM summary/synthesis generation
│   │   ├── knowledge/
│   │   │   ├── __init__.py
│   │   │   ├── vector_store.py      # ChromaDB wrapper
│   │   │   ├── graph_store.py       # SQLite graph (nodes + edges)
│   │   │   ├── document_store.py    # File metadata + raw storage
│   │   │   └── models.py            # Pydantic models for all entities
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── runtime.py           # Agent loop + scheduler
│   │   │   ├── resurface.py         # Proactive resurfacing logic
│   │   │   ├── daily_brief.py       # Daily digest generator
│   │   │   ├── connection_finder.py # Cross-note link discovery
│   │   │   └── prompts.py           # All LLM prompt templates
│   │   ├── search/
│   │   │   ├── __init__.py
│   │   │   └── engine.py            # Hybrid search (vector + graph + FTS)
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── search_router.py     # /api/search/*
│   │       ├── browse_router.py     # /api/browse/*
│   │       ├── agent_router.py      # /api/agent/* (briefs, connections)
│   │       └── settings_router.py   # /api/settings/*
│   └── tests/
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx        # Home: recent + daily brief
│   │   │   ├── Search.tsx           # Semantic search interface
│   │   │   ├── Browse.tsx           # Browse by topic/tag/timeline
│   │   │   ├── NoteView.tsx         # Single note + connections
│   │   │   ├── Connections.tsx      # Graph visualization
│   │   │   └── Settings.tsx         # Config page
│   │   ├── components/
│   │   │   ├── CaptureBar.tsx       # Quick-capture input (always visible)
│   │   │   ├── NoteCard.tsx         # Note preview card
│   │   │   ├── ConnectionGraph.tsx  # D3/force-directed graph
│   │   │   ├── DailyBrief.tsx       # Daily digest display
│   │   │   └── SearchResults.tsx    # Search result list
│   │   └── lib/
│   │       └── api.ts               # API client
│   └── public/
├── extensions/
│   └── chrome/                      # Browser extension for web clipping
│       ├── manifest.json
│       ├── popup.html
│       ├── content.js
│       └── background.js
└── data/                            # Docker volume mount point
    ├── inbox/                       # Drop files here for auto-ingest
    ├── documents/                   # Processed originals
    ├── chroma/                      # ChromaDB persistence
    └── mimir.db                     # SQLite database
```

---

## 2. DATA MODEL

### 2.1 Core Entities (SQLite Schema)

```sql
-- Every piece of knowledge is a "Note"
-- Notes are the atomic unit. Everything becomes a note.
CREATE TABLE notes (
    id TEXT PRIMARY KEY,                    -- UUID
    source_type TEXT NOT NULL,              -- 'manual' | 'email' | 'url' | 'file' | 'clipboard' | 'voice' | 'highlight'
    source_uri TEXT,                        -- Original URL, file path, email ID, etc.
    title TEXT,                             -- Extracted or generated title
    raw_content TEXT NOT NULL,              -- Original content as captured
    processed_content TEXT,                 -- Cleaned/normalized content
    synthesis TEXT,                         -- LLM-generated 1-paragraph distillation
    content_type TEXT DEFAULT 'text',       -- 'text' | 'image' | 'pdf' | 'audio' | 'bookmark'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME,                 -- When the pipeline finished
    processing_status TEXT DEFAULT 'pending', -- 'pending' | 'processing' | 'complete' | 'error'
    is_archived INTEGER DEFAULT 0,
    is_starred INTEGER DEFAULT 0,
    word_count INTEGER,
    reading_time_seconds INTEGER
);

-- Concepts are the taxonomy Mimir builds organically
CREATE TABLE concepts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,              -- Normalized concept name
    description TEXT,                       -- LLM-generated description
    parent_id TEXT REFERENCES concepts(id), -- Hierarchical taxonomy (optional)
    note_count INTEGER DEFAULT 0,           -- Denormalized for perf
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many: which concepts appear in which notes
CREATE TABLE note_concepts (
    note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    concept_id TEXT REFERENCES concepts(id) ON DELETE CASCADE,
    relevance_score REAL DEFAULT 1.0,       -- 0.0-1.0, how central this concept is to the note
    PRIMARY KEY (note_id, concept_id)
);

-- Entities are specific named things (people, places, companies, projects)
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,              -- 'person' | 'company' | 'project' | 'place' | 'book' | 'tool' | 'event'
    description TEXT,
    metadata JSON,                         -- Flexible additional fields
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, entity_type)
);

-- Many-to-many: which entities are mentioned in which notes
CREATE TABLE note_entities (
    note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    context TEXT,                           -- Snippet of how the entity appears in the note
    PRIMARY KEY (note_id, entity_id)
);

-- Connections are relationships between notes that Mimir discovers
CREATE TABLE connections (
    id TEXT PRIMARY KEY,
    source_note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    target_note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    connection_type TEXT NOT NULL,          -- 'related' | 'builds_on' | 'contradicts' | 'supports' | 'inspired_by'
    strength REAL DEFAULT 0.5,             -- 0.0-1.0
    explanation TEXT,                      -- LLM-generated explanation of why they're connected
    discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    surfaced INTEGER DEFAULT 0,            -- Has the user seen this connection?
    dismissed INTEGER DEFAULT 0,           -- User said "not useful"
    UNIQUE(source_note_id, target_note_id)
);

-- Tags are user-created labels (vs concepts which are agent-created)
CREATE TABLE tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT                              -- Hex color for UI
);

CREATE TABLE note_tags (
    note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    tag_id TEXT REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, tag_id)
);

-- Resurface queue: things the agent wants to show you
CREATE TABLE resurface_queue (
    id TEXT PRIMARY KEY,
    queue_type TEXT NOT NULL,               -- 'daily_brief' | 'connection_alert' | 'spaced_rep' | 'follow_up'
    note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    connection_id TEXT REFERENCES connections(id),
    reason TEXT NOT NULL,                   -- Why this is being surfaced
    priority REAL DEFAULT 0.5,             -- 0.0-1.0
    scheduled_for DATETIME,                -- When to show it
    delivered INTEGER DEFAULT 0,           -- Has it been shown?
    clicked INTEGER DEFAULT 0,             -- Did the user engage?
    dismissed INTEGER DEFAULT 0,           -- Did the user dismiss?
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Agent activity log for transparency
CREATE TABLE agent_log (
    id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,              -- 'process_note' | 'find_connections' | 'generate_brief' | 'resurface'
    details JSON,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    status TEXT DEFAULT 'running',          -- 'running' | 'complete' | 'error'
    error_message TEXT
);

-- User preferences and settings
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value JSON NOT NULL
);

-- Full-text search index
CREATE VIRTUAL TABLE notes_fts USING fts5(
    title,
    raw_content,
    synthesis,
    content='notes',
    content_rowid='rowid'
);
```

### 2.2 Vector Store Schema (ChromaDB)

```python
# Single collection with rich metadata for filtering
collection_name = "mimir_notes"

# Each chunk gets embedded with metadata:
{
    "id": "note_uuid__chunk_0",           # note ID + chunk index
    "document": "chunk text content",
    "embedding": [0.1, 0.2, ...],         # 768-dim from nomic-embed-text
    "metadata": {
        "note_id": "uuid",
        "chunk_index": 0,
        "source_type": "url",
        "created_at": "2025-01-15T10:30:00Z",
        "concepts": "productivity,note-taking,pkm",  # comma-separated for filtering
        "entities": "Tiago Forte,Building a Second Brain",
        "word_count": 245
    }
}
```

---

## 3. CAPTURE GATEWAY

### 3.1 Capture API Endpoints

```
POST /api/capture/note          # Manual text note
POST /api/capture/url           # URL to fetch and process
POST /api/capture/file          # File upload (PDF, image, doc, etc.)
POST /api/capture/clipboard     # Clipboard text dump
POST /api/capture/voice         # Audio file for transcription
POST /api/capture/email         # Webhook for forwarded emails
POST /api/capture/highlight     # Text highlight with source URL
POST /api/capture/batch         # Multiple items at once
```

### 3.2 Capture Request Schema

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CaptureRequest(BaseModel):
    content: str                          # The thing being captured
    source_type: str = "manual"           # How it arrived
    source_uri: Optional[str] = None      # Where it came from
    title: Optional[str] = None           # User-provided title (optional)
    tags: Optional[list[str]] = None      # User-provided tags (optional)
    context: Optional[str] = None         # User's note about why they saved it
    timestamp: Optional[datetime] = None  # Override capture time

class CaptureResponse(BaseModel):
    note_id: str
    status: str                           # 'queued' | 'processing' | 'complete'
    title: Optional[str]                  # Generated title if not provided
    message: str
```

### 3.3 Capture Behaviors

**URL Capture:**
1. Accept URL → extract full page content via `readability` (Python: `readability-lxml` or `trafilatura`)
2. Extract: title, author, publish date, main content, images
3. Store raw HTML + cleaned markdown
4. Queue for processing pipeline

**File Capture:**
1. Accept upload → store original in `/data/documents/{note_id}/`
2. Extract text based on type:
   - PDF → `pymupdf` (fitz)
   - DOCX → `python-docx`
   - Images → OCR via `pytesseract` or description via Ollama vision
   - Audio → `faster-whisper` for transcription
3. Queue for processing pipeline

**Email Capture:**
1. Poll IMAP inbox on schedule (configurable, default every 5 min)
2. Parse email: subject → title, body → content, attachments → sub-notes
3. Auto-archive the email after capture (configurable)

**File Watch Capture:**
1. `watchdog` monitors `/data/inbox/`
2. Any new file triggers file capture pipeline
3. Move to `/data/documents/` after processing

**Browser Extension Capture:**
1. Chrome extension with popup for:
   - Save full page
   - Save selection (highlighted text)
   - Save URL as bookmark with auto-extract
2. Sends to `POST /api/capture/highlight` or `/url`
3. Context menu integration: right-click → "Save to Mimir"

### 3.4 Capture UX Principle

**Every capture path must complete in < 500ms from the user's perspective.** The response is always "got it, processing in background." The user never waits for LLM processing during capture. Queue everything.

---

## 4. PROCESSING PIPELINE

### 4.1 Pipeline Stages

```
CAPTURE → NORMALIZE → CHUNK → EXTRACT → EMBED → LINK → SYNTHESIZE → INDEX
```

Each stage is idempotent and can be re-run independently.

### 4.2 Stage Details

#### Stage 1: Normalize

```python
def normalize(note: Note) -> Note:
    """
    Clean and standardize the raw content.
    - Strip HTML if present (keep markdown structure)
    - Normalize whitespace
    - Detect language
    - Estimate reading time
    - Set word count
    """
```

#### Stage 2: Chunk

```python
def chunk(note: Note) -> list[Chunk]:
    """
    Split content into semantic chunks for embedding.

    Strategy:
    - Short notes (< 500 words): single chunk = whole note
    - Medium notes (500-2000 words): paragraph-level chunks with overlap
    - Long notes (2000+ words): section-level chunks with 2-sentence overlap

    Each chunk: 200-800 tokens target, with 50-token overlap between chunks.
    Preserve paragraph boundaries. Never split mid-sentence.
    """
```

#### Stage 3: Extract

```python
def extract(note: Note) -> ExtractionResult:
    """
    Use LLM to extract structured information.

    Prompt the LLM to identify:
    1. concepts: List of 3-10 topic/concept tags (from existing taxonomy when possible,
       new ones when genuinely novel)
    2. entities: Named people, companies, places, books, tools, projects
       with their type and relationship to the content
    3. key_claims: 1-5 core assertions or ideas (for connection-finding later)
    4. content_type_hint: Is this a reference, opinion, tutorial, story, idea, question?
    5. temporal_relevance: Is this time-sensitive? When does it expire?
    6. action_items: Any implicit or explicit todos

    Returns ExtractionResult with all structured data.
    """
```

**Extraction Prompt Template:**

```
You are a knowledge librarian. Analyze the following content and extract structured metadata.

CONTENT:
{note.processed_content}

SOURCE TYPE: {note.source_type}
{f"USER CONTEXT: {note.context}" if note.context else ""}

Respond in JSON only:
{
  "suggested_title": "concise descriptive title if none exists",
  "concepts": ["concept1", "concept2"],
  "entities": [
    {"name": "...", "type": "person|company|project|place|book|tool|event", "role": "how they relate to this content"}
  ],
  "key_claims": ["core idea 1", "core idea 2"],
  "content_type": "reference|opinion|tutorial|story|idea|question|quote|data",
  "temporal_relevance": "evergreen|time-sensitive|historical",
  "expiry_hint": "null or ISO date if time-sensitive",
  "action_items": ["implicit or explicit todo"]
}
```

#### Stage 4: Embed

```python
def embed(chunks: list[Chunk]) -> list[EmbeddedChunk]:
    """
    Generate embeddings via Ollama.

    POST http://ollama:11434/api/embeddings
    {
        "model": "nomic-embed-text",
        "prompt": chunk.text
    }

    Store in ChromaDB with metadata from extraction stage.
    """
```

#### Stage 5: Link

```python
def link(note: Note, extraction: ExtractionResult) -> list[Connection]:
    """
    Find and create connections to existing notes.

    Strategy (in order):
    1. Entity overlap: Notes sharing the same entities (high signal)
    2. Concept overlap: Notes sharing 2+ concepts (medium signal)
    3. Semantic similarity: Top-5 nearest neighbors in vector space
       with similarity > 0.75 (variable signal, needs LLM validation)

    For candidates found via semantic similarity, use LLM to validate
    and classify the connection type:
    - 'related': Same topic area
    - 'builds_on': New note extends ideas from old note
    - 'contradicts': Notes present opposing views
    - 'supports': New note provides evidence for old note's claims
    - 'inspired_by': Loose thematic connection

    Only create connections with strength > 0.5 after LLM validation.
    """
```

**Link Validation Prompt:**

```
You are a knowledge connector. Given two pieces of content, determine if and how they are meaningfully connected.

NOTE A (new):
Title: {note_a.title}
Content: {note_a.synthesis or note_a.processed_content[:500]}
Concepts: {note_a.concepts}

NOTE B (existing):
Title: {note_b.title}
Content: {note_b.synthesis or note_b.processed_content[:500]}
Concepts: {note_b.concepts}

Are these meaningfully connected beyond surface-level topic overlap?
If yes, respond in JSON:
{
  "connected": true,
  "type": "related|builds_on|contradicts|supports|inspired_by",
  "strength": 0.0-1.0,
  "explanation": "One sentence explaining the connection"
}
If not meaningfully connected:
{"connected": false}
```

#### Stage 6: Synthesize

```python
def synthesize(note: Note, extraction: ExtractionResult, connections: list[Connection]) -> str:
    """
    Generate a 1-paragraph synthesis of the note.

    This is the "second brain" voice — it should read like YOUR notes,
    not like a Wikipedia summary. Casual, direct, focused on why this
    matters and how it connects to what you already know.

    If connections were found, mention them naturally:
    "This connects to your earlier note about X..."
    """
```

**Synthesis Prompt:**

```
You are the user's second brain. Write a 2-4 sentence synthesis of this content.
Write in second person ("you"), casual tone, focused on the key insight and why it matters.
If there are connections to existing notes, weave them in naturally.

CONTENT:
{note.processed_content[:1500]}

KEY CLAIMS: {extraction.key_claims}

CONNECTED NOTES:
{formatted_connections or "None found yet."}

Write the synthesis. No preamble. Just the synthesis paragraph.
```

#### Stage 7: Index

```python
def index(note: Note):
    """
    Update all search indices:
    1. SQLite FTS5 for full-text search
    2. Update concept counts
    3. Update entity references
    4. Mark note as processing_status='complete'
    """
```

### 4.3 Pipeline Error Handling

- Each stage stores its output independently
- If a stage fails, the note is marked with `processing_status='error'` and the error logged
- A retry mechanism runs every 15 minutes for errored notes (max 3 retries)
- The LLM stages (Extract, Link, Synthesize) have timeouts of 60 seconds each
- If Ollama is unavailable, notes queue up and process when it comes back

---

## 5. AGENT BEHAVIORS

### 5.1 Agent Runtime Loop

The agent is NOT a chatbot. It's a background worker that performs scheduled and event-driven tasks.

```python
class MimirAgent:
    """
    The agent runs on a schedule and reacts to events.
    It never blocks the user. Everything is async.
    """

    # Scheduled tasks
    schedules = {
        "process_queue":     "every 30 seconds",   # Process pending captures
        "find_connections":  "every 6 hours",       # Deep scan for new connections
        "generate_brief":   "daily at configured time (default 7:00 AM)",
        "prune_stale":      "weekly",               # Archive old resurface items
        "rebuild_taxonomy":  "weekly",               # Re-cluster concepts
    }

    # Event-driven tasks
    events = {
        "on_note_processed": ["find_immediate_connections", "check_resurface_triggers"],
        "on_search":         ["log_interest_signal"],
        "on_note_viewed":    ["update_relevance_scores"],
        "on_connection_dismissed": ["adjust_connection_model"],
    }
```

### 5.2 Daily Brief Generation

```python
def generate_daily_brief(self) -> DailyBrief:
    """
    The daily brief is a short digest delivered at the user's preferred time.
    Think of it as a "morning newspaper" for your own knowledge.

    Sections:
    1. RECENTLY CAPTURED: What you saved yesterday/since last brief (max 5)
    2. CONNECTIONS FOUND: New links between your notes (max 3)
    3. RESURFACE: Old notes relevant to recent activity (max 3)
    4. DANGLING THREADS: Things you saved but never revisited (max 2)
    5. THIS DAY LAST YEAR: Notes from ~365 days ago (if any)

    Delivery channels (configurable):
    - Dashboard widget (always)
    - Email digest
    - Webhook (Mattermost, Slack, ntfy, etc.)
    """
```

**Brief Generation Prompt:**

```
You are Mimir, a personal knowledge assistant. Write a brief daily digest.
Be conversational and concise. Use the user's name if known.

TODAY'S DATE: {date}

RECENTLY CAPTURED ({count} notes):
{recent_notes_summaries}

NEW CONNECTIONS FOUND:
{new_connections}

RESURFACED NOTES (relevant to recent activity):
{resurface_items}

DANGLING THREADS (saved but never revisited, 30+ days old):
{dangling_items}

THIS DAY LAST YEAR:
{historical_items or "Nothing from this date."}

Write a friendly 150-300 word digest. Lead with the most interesting
connection or resurface. Don't list everything — curate. End with one
question or prompt that might spark the user's thinking.
```

### 5.3 Connection Discovery

```python
def find_connections_deep_scan(self):
    """
    Periodic deep scan for connections that the real-time linker might miss.

    Strategy:
    1. Get all notes from last 7 days
    2. For each, find top-10 semantic neighbors across ALL notes
    3. Filter to pairs that don't already have a connection
    4. Use LLM to validate each candidate
    5. Create connections for validated pairs
    6. Queue high-strength connections for resurface

    Rate limiting: Max 50 LLM calls per deep scan to bound cost/time.
    Process highest-similarity candidates first.
    """
```

### 5.4 Resurface Engine

```python
def check_resurface_triggers(self, note: Note):
    """
    After processing a new note, check if it should trigger
    resurfacing of old notes.

    Triggers:
    1. STRONG_CONNECTION: New note has connection strength > 0.8 to an old note
       → Surface the old note with "This relates to something you just saved"

    2. CONCEPT_CLUSTER: New note pushes a concept past a threshold
       (e.g., 5th note about "pricing strategy")
       → Surface all notes in that concept cluster with
         "You keep coming back to this topic — here's everything you've captured"

    3. ENTITY_RECURRENCE: Same entity appears in notes > 30 days apart
       → Surface the old note with "You encountered {entity} again"

    4. SPACED_REPETITION: Notes marked as 'starred' get resurfaced on
       increasing intervals (1, 3, 7, 14, 30, 60, 90 days)
       → Surface with "Revisit: {title}"

    5. FOLLOW_UP: Notes with action_items that haven't been marked complete
       after 7 days → Surface with "Still on your mind? {action_item}"
    """
```

### 5.5 Interest Signals

```python
def log_interest_signal(self, event_type: str, note_id: str = None, query: str = None):
    """
    Track what the user is interested in RIGHT NOW.
    This informs resurfacing and brief generation.

    Signals:
    - Search queries → what topics are on their mind
    - Notes viewed → what they're revisiting
    - Notes starred → explicit importance marker
    - Captures → what they're currently consuming
    - Time spent on note → depth of engagement

    These signals decay over time (half-life of 7 days).
    Recent interests weight resurfacing heavily.
    """
```

### 5.6 Taxonomy Evolution

```python
def rebuild_taxonomy(self):
    """
    Weekly task to reorganize the concept hierarchy.

    Steps:
    1. Get all concepts with their note counts
    2. Merge near-duplicate concepts (embedding similarity > 0.92)
       Example: "note-taking" and "note taking" → merge
    3. Identify parent-child relationships via LLM
       Example: "React" is a child of "JavaScript frameworks"
    4. Prune concepts with 0 notes
    5. Identify emerging clusters (concepts growing fast)

    The taxonomy is never imposed — it emerges from the user's actual
    knowledge patterns. This is a key differentiator from tools that
    require you to define categories upfront.
    """
```

---

## 6. SEARCH ENGINE

### 6.1 Hybrid Search

```python
class MimirSearch:
    """
    Search combines three strategies, weighted and merged.
    """

    async def search(self, query: str, filters: SearchFilters = None) -> list[SearchResult]:
        """
        1. SEMANTIC: Embed query → find nearest chunks in ChromaDB
           - Returns relevance scores 0-1
           - Weight: 0.5

        2. FULL-TEXT: FTS5 search on title, content, synthesis
           - BM25 scoring
           - Weight: 0.3

        3. GRAPH: Find notes connected to query concepts/entities
           - Expand from matched entities/concepts through connections
           - Weight: 0.2

        Merge results using reciprocal rank fusion (RRF).
        Return top-20 notes with merged scores.

        Optional filters:
        - date range
        - source type
        - concepts (include/exclude)
        - entities
        - tags
        - content type
        """

    async def ask(self, question: str) -> AskResponse:
        """
        Natural language Q&A over the knowledge base.

        1. Search for relevant notes (top 10)
        2. Feed notes as context to LLM
        3. Generate answer with citations to specific notes

        This is the "what did I save about X?" interface.
        """
```

**Ask Prompt:**

```
You are the user's second brain. Answer their question using ONLY the
knowledge they have previously captured. If you don't have enough
information in the provided notes, say so honestly.

QUESTION: {question}

RELEVANT NOTES:
{formatted_notes_with_ids}

Answer the question. Cite specific notes by their title in brackets like [Note Title].
If the notes contain conflicting information, mention both perspectives.
Keep it concise.
```

---

## 7. WEB DASHBOARD

### 7.1 Pages

**Dashboard (Home)**
- Quick capture bar (always at top, CMD+K to focus)
- Today's daily brief (collapsible card)
- Recent captures (last 10)
- New connections found (unseen)
- Pinned/starred notes

**Search**
- Single search bar with semantic search
- Filter sidebar: date, source type, concepts, tags
- Results show: title, synthesis preview, source, date, matching concepts
- "Ask" mode toggle: switch from search results to Q&A answer

**Browse**
- Concept cloud / tree view (the organic taxonomy)
- Timeline view (chronological)
- Source view (grouped by where things came from)
- Entity view (browse by people, projects, companies)

**Note View**
- Full note content (markdown rendered)
- Synthesis card at top
- Concepts and entities as chips
- Connections panel on the right (linked notes with explanations)
- Source link (if URL)
- Edit capability (modify content, add tags, star, archive)

**Connections**
- Force-directed graph visualization of notes and connections
- Click a node to see the note
- Filter by concept, entity, date range, connection type
- Cluster view: see topic groupings

**Settings**
- Ollama model selection
- Brief delivery time and channel
- Email capture config (IMAP settings)
- Notification webhook URLs
- Export / backup controls
- API key management (for the capture API)

### 7.2 Quick Capture Bar

This is the most important UI element. It's always visible and supports:

```
Type or paste anything...          [Capture]

Supports:
- Plain text → manual note
- URL → auto-fetches and processes
- Pasted rich text → strips formatting, captures as markdown
- Keyboard shortcut: CMD+K to focus from anywhere
```

---

## 8. API REFERENCE

### 8.1 Capture

```
POST /api/capture/note
  Body: { content: str, title?: str, tags?: str[], context?: str }
  Response: { note_id: str, status: "queued" }

POST /api/capture/url
  Body: { url: str, context?: str, tags?: str[] }
  Response: { note_id: str, status: "queued" }

POST /api/capture/file
  Body: multipart/form-data with file + optional context/tags
  Response: { note_id: str, status: "queued" }
```

### 8.2 Search

```
GET /api/search?q={query}&mode=search|ask&source_type=&concepts=&after=&before=&limit=20
  Response: { results: SearchResult[], total: int }
  SearchResult: { note_id, title, synthesis, score, highlights, concepts, source_type, created_at }

GET /api/search/ask?q={question}
  Response: { answer: str, sources: NoteReference[], confidence: float }
```

### 8.3 Browse

```
GET /api/notes/{note_id}
  Response: full Note with connections, concepts, entities

GET /api/notes?sort=recent|starred|most_connected&limit=20&offset=0
  Response: { notes: NoteSummary[], total: int }

GET /api/concepts
  Response: { concepts: ConceptTree[] }

GET /api/entities?type=person|company|project
  Response: { entities: Entity[] }

GET /api/connections?note_id={id}&type=&min_strength=0.5
  Response: { connections: Connection[] }
```

### 8.4 Agent

```
GET /api/agent/brief?date={YYYY-MM-DD}
  Response: { brief: DailyBrief, generated_at: datetime }

GET /api/agent/resurface
  Response: { items: ResurfaceItem[] }  # Undelivered items

POST /api/agent/resurface/{id}/dismiss
  Response: { ok: true }

POST /api/agent/resurface/{id}/click
  Response: { ok: true }

GET /api/agent/activity
  Response: { log: AgentLogEntry[] }  # What the agent has been doing
```

### 8.5 Settings

```
GET /api/settings
PUT /api/settings
  Body: { key: str, value: any }
```

---

## 9. DOCKER COMPOSE

```yaml
version: "3.8"

services:
  mimir-backend:
    build: ./backend
    container_name: mimir-backend
    restart: unless-stopped
    ports:
      - "3080:8000"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - DATABASE_PATH=/data/mimir.db
      - CHROMA_PATH=/data/chroma
      - DOCUMENTS_PATH=/data/documents
      - INBOX_PATH=/data/inbox
      - EMBEDDING_MODEL=nomic-embed-text
      - LLM_MODEL=gemma3
      - BRIEF_TIME=07:00
      - LOG_LEVEL=info
    volumes:
      - ${DATA_PATH:-./data}:/data
    depends_on:
      - ollama

  mimir-frontend:
    build: ./frontend
    container_name: mimir-frontend
    restart: unless-stopped
    ports:
      - "3081:80"
    depends_on:
      - mimir-backend

  ollama:
    image: ollama/ollama:latest
    container_name: mimir-ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ${OLLAMA_MODELS_PATH:-./ollama-models}:/root/.ollama
    # Uncomment for GPU passthrough:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

  # Optional: use your existing Ollama instance instead
  # Just set OLLAMA_BASE_URL=http://192.168.4.45:11434 in mimir-backend
  # and remove the ollama service from this file.
```

**.env.example:**

```
# Paths
DATA_PATH=./data
OLLAMA_MODELS_PATH=./ollama-models

# Models
LLM_MODEL=gemma3
EMBEDDING_MODEL=nomic-embed-text

# Daily brief
BRIEF_TIME=07:00
BRIEF_WEBHOOK_URL=          # Optional: Mattermost/Slack/ntfy URL

# Email capture (optional)
IMAP_HOST=
IMAP_PORT=993
IMAP_USER=
IMAP_PASSWORD=
IMAP_FOLDER=INBOX
IMAP_POLL_INTERVAL=300      # seconds

# Security
API_KEY=                    # Set this to secure your capture API
```

---

## 10. CONFIGURATION & SETTINGS

### 10.1 Default Settings (stored in SQLite)

```json
{
  "general": {
    "instance_name": "Mimir",
    "timezone": "America/New_York",
    "language": "en"
  },
  "agent": {
    "brief_enabled": true,
    "brief_time": "07:00",
    "brief_delivery": ["dashboard"],
    "connection_scan_interval_hours": 6,
    "max_llm_calls_per_scan": 50,
    "resurface_enabled": true,
    "spaced_rep_enabled": true,
    "spaced_rep_intervals_days": [1, 3, 7, 14, 30, 60, 90]
  },
  "processing": {
    "llm_model": "gemma3",
    "embedding_model": "nomic-embed-text",
    "chunk_target_tokens": 400,
    "chunk_overlap_tokens": 50,
    "connection_similarity_threshold": 0.75,
    "connection_strength_minimum": 0.5,
    "max_concepts_per_note": 10,
    "max_entities_per_note": 15
  },
  "capture": {
    "email_enabled": false,
    "file_watch_enabled": true,
    "auto_archive_email": true
  },
  "notifications": {
    "webhook_url": null,
    "webhook_type": "generic"
  }
}
```

---

## 11. CHROME EXTENSION

### 11.1 Manifest

```json
{
  "manifest_version": 3,
  "name": "Mimir Capture",
  "version": "1.0.0",
  "description": "Save anything to your Mimir second brain",
  "permissions": ["activeTab", "contextMenus", "storage"],
  "action": {
    "default_popup": "popup.html",
    "default_icon": "icon48.png"
  },
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [{
    "matches": ["<all_urls>"],
    "js": ["content.js"]
  }]
}
```

### 11.2 Features

- **Popup:** Quick note capture + save current page URL
- **Context menu:** Right-click selected text → "Save to Mimir"
- **Keyboard shortcut:** Alt+M → open capture popup
- **Settings:** Mimir server URL + API key

---

## 12. IMPLEMENTATION PHASES

### Phase 1: Core (MVP)
Build the foundation that makes Mimir useful immediately.

- [ ] FastAPI backend with SQLite + ChromaDB
- [ ] Capture API (manual notes, URLs, file upload)
- [ ] Processing pipeline (all 7 stages)
- [ ] Hybrid search (semantic + FTS)
- [ ] Basic web dashboard (capture bar, search, note view)
- [ ] Docker Compose deployment
- [ ] Ollama integration for LLM + embeddings

**Milestone: "Save anything, find everything" works end-to-end.**

### Phase 2: Agent Intelligence
Add the behaviors that make it a true second brain.

- [ ] Connection discovery (real-time + deep scan)
- [ ] Daily brief generation
- [ ] Resurface engine (all 5 trigger types)
- [ ] Interest signal tracking
- [ ] Agent activity log + transparency UI
- [ ] Notification webhooks (Mattermost, ntfy)

**Milestone: Mimir proactively tells you things you need to know.**

### Phase 3: Extended Capture
Make capture truly zero-friction.

- [ ] Chrome extension
- [ ] Email capture (IMAP polling)
- [ ] File watcher (inbox folder)
- [ ] Voice capture with transcription
- [ ] Mobile-friendly capture page

**Milestone: Every capture path takes < 5 seconds of user effort.**

### Phase 4: Knowledge Graph & Polish
Make the connections visible and the experience delightful.

- [ ] Interactive graph visualization
- [ ] Concept taxonomy tree view
- [ ] Entity pages (everything you know about a person/project)
- [ ] "Ask" mode (Q&A over your knowledge base)
- [ ] Export (markdown archive, JSON backup)
- [ ] Taxonomy evolution (auto-merge, hierarchy building)

**Milestone: The graph is navigable and reveals insights you didn't expect.**

---

## 13. KEY DESIGN DECISIONS

### Why SQLite over Postgres?
Single-file database. Zero configuration. Portable. Backup is `cp mimir.db mimir.db.bak`. For a single-user knowledge base, SQLite handles millions of rows effortlessly. If Mimir ever needs multi-user, Postgres is a straightforward migration since we're using standard SQL.

### Why ChromaDB over Qdrant/Weaviate?
Embedded mode — no separate server process. Runs in the same Python process as the backend. For v1, this simplifies deployment enormously. The interface is simple enough that swapping to Qdrant later is a clean migration.

### Why Ollama instead of direct model loading?
Ollama handles model management, GGUF quantization, GPU allocation, and provides a clean HTTP API. Users can share a single Ollama instance across Mimir and other projects (like your existing homelab Ollama). It also makes model swapping trivial — change one env var.

### Why not a chat interface?
Mimir is not a chatbot. The "ask" feature exists for Q&A retrieval, but the core interaction model is: capture → agent processes → agent resurfaces → you engage. Adding a chat interface would muddy the purpose and invite scope creep toward yet another AI assistant. The constraint is the product.

### Why agent-driven taxonomy instead of user-defined?
Because user-defined taxonomies die. People create them with great intentions and then stop using them within weeks because the cost of categorizing every input exceeds the value. Mimir's taxonomy is emergent — it watches what you actually capture and builds categories from patterns. This is how human memory works.

---

## 14. SECURITY CONSIDERATIONS

- **API Key auth** for all capture endpoints (simple bearer token for v1)
- **No external network calls** except to Ollama and optional IMAP/webhooks
- **All data on local disk** — the Docker volume is the single source of truth
- **No telemetry, no analytics, no phoning home**
- **CORS restricted** to the frontend origin
- **Sanitize all HTML** before storage (prevent XSS in note rendering)
- **Rate limit** capture endpoints to prevent abuse if exposed to the internet

---

## 15. PERFORMANCE TARGETS

| Metric | Target |
|--------|--------|
| Capture response time | < 500ms |
| Search results returned | < 1 second |
| Note processing (full pipeline) | < 30 seconds per note |
| Daily brief generation | < 2 minutes |
| Connection deep scan (1000 notes) | < 15 minutes |
| Dashboard load | < 2 seconds |
| Storage per 1000 notes | ~50-100 MB (text-heavy) |

---

*This blueprint is designed to be fed directly to Claude Code for implementation. Start with Phase 1. Each phase is independently deployable and valuable.*
