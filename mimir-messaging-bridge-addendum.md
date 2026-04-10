# MIMIR — Messaging Bridge (Blueprint Addendum)

## Purpose

Mimir needs to go where you already are. You're standing in line, overhear something interesting, have a thought in the shower, read something on your phone — you need to capture it *right now* without opening an app, logging in, or context-switching. The messaging bridge turns any chat app you already use into a zero-friction capture and query interface for Mimir.

**The bridge is bidirectional:**
- **Inbound:** Send Mimir a message → it captures it, processes it, done.
- **Outbound:** Mimir sends you daily briefs, connection alerts, and resurface nudges through the same channel.

---

## 1. ARCHITECTURE

### 1.1 High-Level Design

```
┌──────────────────────────────────────────────────────────────────┐
│                      MESSAGING BRIDGE                            │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐ │
│  │  WhatsApp   │  │  Telegram   │  │    SMS      │  │  Discord  │ │
│  │  Adapter    │  │  Adapter    │  │  Adapter    │  │  Adapter  │ │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬─────┘ │
│        │               │               │               │        │
│        └───────────┬────┴───────────────┴───────┬───────┘        │
│                    │                            │                │
│              ┌─────▼──────┐              ┌──────▼─────┐         │
│              │  Inbound    │              │  Outbound   │         │
│              │  Router     │              │  Dispatcher │         │
│              └─────┬──────┘              └──────▲─────┘         │
│                    │                            │                │
│  ┌─────────────────▼────────────────────────────┴──────────────┐ │
│  │                    MESSAGE HANDLER                           │ │
│  │                                                              │ │
│  │  Intent Detection → Command Router → Response Builder        │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                    │                            ▲                 │
│                    ▼                            │                 │
│           ┌────────────────────────────────────────┐             │
│           │          MIMIR CORE APIs                │             │
│           │   /capture  /search  /agent  /harness   │             │
│           └────────────────────────────────────────┘             │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 Design Principles

1. **Adapter pattern.** Each messaging platform is a thin adapter that normalizes messages into a common format. All logic lives in the shared handler.
2. **Stateless handlers.** The bridge doesn't maintain conversation state. Every message is self-contained. Mimir's knowledge store *is* the memory.
3. **Platform-native feel.** Responses use the formatting conventions of each platform (Telegram markdown, WhatsApp formatting, etc.) rather than one-size-fits-all.
4. **Graceful degradation.** If the LLM is unavailable, capture still works. If a platform webhook is down, messages queue and retry.

---

## 2. COMMON MESSAGE FORMAT

### 2.1 Normalized Message

```python
# src/bridge/models.py

from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class Platform(str, Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SMS = "sms"
    DISCORD = "discord"
    SIGNAL = "signal"
    SLACK = "slack"         # Personal Slack workspace
    MATTERMOST = "mattermost"

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    DOCUMENT = "document"
    VIDEO = "video"
    LOCATION = "location"
    CONTACT = "contact"

class InboundMessage(BaseModel):
    """Normalized inbound message from any platform."""
    platform: Platform
    platform_message_id: str         # Original message ID on the platform
    sender_id: str                   # Platform-specific user ID
    timestamp: datetime
    message_type: MessageType
    text: str | None = None          # Text content (if any)
    media_url: str | None = None     # URL to download media (if any)
    media_bytes: bytes | None = None # Raw media bytes (if already fetched)
    media_mime_type: str | None = None
    caption: str | None = None       # Caption on media messages
    location: dict | None = None     # {"lat": float, "lng": float} if location
    reply_to_id: str | None = None   # If replying to a previous message
    raw_payload: dict | None = None  # Original platform payload for debugging

class OutboundMessage(BaseModel):
    """Message to send back through a platform."""
    platform: Platform
    recipient_id: str
    text: str
    parse_mode: str | None = None    # "markdown" | "html" | None
    media_url: str | None = None     # Attach an image/file
    reply_to_id: str | None = None   # Reply to specific message
    buttons: list[dict] | None = None  # Platform-specific interactive buttons
```

---

## 3. INTENT DETECTION & COMMAND ROUTING

### 3.1 How Mimir Interprets Messages

When a message arrives, Mimir doesn't need a complex NLU system. Most messages fall into clear patterns. The intent detection is a simple cascade:

```python
# src/bridge/intent.py

from enum import Enum

class Intent(str, Enum):
    CAPTURE_NOTE = "capture_note"       # Default: just save this
    CAPTURE_URL = "capture_url"         # Message is/contains a URL
    CAPTURE_MEDIA = "capture_media"     # Image, audio, document
    SEARCH = "search"                   # Find something in the brain
    ASK = "ask"                         # Ask a question about saved knowledge
    DAILY_BRIEF = "daily_brief"         # Request today's brief
    STATUS = "status"                   # System health check
    HELP = "help"                       # Show available commands
    RECENT = "recent"                   # Show recent captures
    STAR = "star"                       # Star/bookmark a note
    TAG = "tag"                         # Add a tag to something

def detect_intent(message: InboundMessage) -> Intent:
    """
    Determine what the user wants based on message content.
    
    Rules (checked in order):
    
    1. Explicit commands (prefix with / or keyword):
       /search <query>     → SEARCH
       /ask <question>     → ASK
       /brief              → DAILY_BRIEF
       /recent             → RECENT
       /status             → STATUS
       /help               → HELP
       /star               → STAR (star the last captured note)
       /tag <tag>          → TAG (tag the last captured note)
    
    2. Question detection:
       "What did I save about..." → ASK
       "Find my notes on..."     → SEARCH
       "Do I have anything on..." → SEARCH
       Starts with question word + "my" or "I" → ASK
    
    3. Media messages:
       Image/audio/document attachment → CAPTURE_MEDIA
    
    4. URL detection:
       Contains http:// or https:// → CAPTURE_URL
    
    5. Default:
       Everything else → CAPTURE_NOTE
    
    The beauty of this system is that the DEFAULT is capture.
    You don't need to tell Mimir to save something. Just send it.
    """
```

### 3.2 Command Reference

```
CAPTURE (default — just send anything):
  "Meeting with Jake: discussed Q3 pricing, decided to raise by 10%"
  "https://example.com/great-article"
  [photo of whiteboard]
  [voice memo]
  [forwarded PDF]

SEARCH:
  /search pricing strategy
  /s dental implants
  "find my notes on React performance"

ASK:
  /ask what was Jake's opinion on pricing?
  /a how many books did I save about leadership?
  "what did I save about onboarding?"

BRIEF:
  /brief
  /today

RECENT:
  /recent
  /recent 5        (show last 5)

META:
  /star             (star the last captured note)
  /tag #dental      (tag the last capture)
  /status           (system health)
  /help             (show commands)
```

### 3.3 Natural Language Fallback

If the cascade doesn't match a clear intent, and the message looks like a question (ends with `?`, starts with who/what/where/when/why/how), use the harness REASON operation to classify:

```python
async def classify_ambiguous_intent(text: str, harness: HarnessRouter) -> Intent:
    """
    For messages that don't match explicit patterns, ask the LLM.
    
    Prompt:
    "Classify this message as one of: CAPTURE (save this info), SEARCH (find saved info),
     ASK (answer a question from saved knowledge). Message: '{text}'. 
     Respond with one word only."
    
    This is a single cheap LLM call using the EXTRACT operation (fast/local model).
    Only triggered for genuinely ambiguous messages.
    """
```

---

## 4. MESSAGE HANDLER

### 4.1 Core Handler

```python
# src/bridge/handler.py

class MessageHandler:
    """
    Processes inbound messages and generates responses.
    This is the brain of the bridge — platform-agnostic.
    """
    
    def __init__(self, capture_service, search_service, agent_service, harness):
        self.capture = capture_service
        self.search = search_service
        self.agent = agent_service
        self.harness = harness
        self._last_note_id: str | None = None  # Track for /star and /tag
    
    async def handle(self, message: InboundMessage) -> OutboundMessage:
        intent = detect_intent(message)
        
        match intent:
            case Intent.CAPTURE_NOTE:
                return await self._handle_capture_note(message)
            case Intent.CAPTURE_URL:
                return await self._handle_capture_url(message)
            case Intent.CAPTURE_MEDIA:
                return await self._handle_capture_media(message)
            case Intent.SEARCH:
                return await self._handle_search(message)
            case Intent.ASK:
                return await self._handle_ask(message)
            case Intent.DAILY_BRIEF:
                return await self._handle_brief(message)
            case Intent.RECENT:
                return await self._handle_recent(message)
            case Intent.STAR:
                return await self._handle_star(message)
            case Intent.TAG:
                return await self._handle_tag(message)
            case Intent.STATUS:
                return await self._handle_status(message)
            case Intent.HELP:
                return await self._handle_help(message)
    
    async def _handle_capture_note(self, message: InboundMessage) -> OutboundMessage:
        """
        Capture a text note. This is the most common path.
        Response should be instant and minimal.
        """
        note = await self.capture.create_note(
            content=message.text,
            source_type="message",
            source_uri=f"{message.platform.value}://{message.sender_id}/{message.platform_message_id}",
            context=None,
        )
        self._last_note_id = note.id
        
        # Short confirmation — don't be chatty
        return OutboundMessage(
            platform=message.platform,
            recipient_id=message.sender_id,
            text=f"✓ Captured. Processing.",
            reply_to_id=message.platform_message_id,
        )
    
    async def _handle_capture_url(self, message: InboundMessage) -> OutboundMessage:
        """Extract URL from message, capture it."""
        import re
        urls = re.findall(r'https?://\S+', message.text)
        url = urls[0] if urls else message.text.strip()
        
        # Any text besides the URL becomes context
        context = re.sub(r'https?://\S+', '', message.text).strip() or None
        
        note = await self.capture.create_from_url(
            url=url,
            context=context,
            tags=None,
        )
        self._last_note_id = note.id
        
        return OutboundMessage(
            platform=message.platform,
            recipient_id=message.sender_id,
            text=f"✓ Saved link. Fetching and processing.",
            reply_to_id=message.platform_message_id,
        )
    
    async def _handle_capture_media(self, message: InboundMessage) -> OutboundMessage:
        """Handle image, audio, or document captures."""
        media_bytes = message.media_bytes
        
        # If we have a URL but no bytes, fetch the media
        if not media_bytes and message.media_url:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(message.media_url)
                media_bytes = resp.content
        
        match message.message_type:
            case MessageType.AUDIO:
                # Transcribe first, then capture as note
                transcript = await self.harness.transcribe(
                    media_bytes, format=_guess_audio_format(message.media_mime_type)
                )
                note = await self.capture.create_note(
                    content=transcript,
                    source_type="voice",
                    source_uri=f"{message.platform.value}://voice/{message.platform_message_id}",
                    context=message.caption,
                )
                self._last_note_id = note.id
                # Show the transcription so user can verify
                preview = transcript[:200] + ("..." if len(transcript) > 200 else "")
                return OutboundMessage(
                    platform=message.platform,
                    recipient_id=message.sender_id,
                    text=f"✓ Voice captured:\n\n\"{preview}\"",
                    reply_to_id=message.platform_message_id,
                )
            
            case MessageType.IMAGE:
                note = await self.capture.create_from_file(
                    file_bytes=media_bytes,
                    filename=f"image_{message.platform_message_id}.jpg",
                    mime_type=message.media_mime_type or "image/jpeg",
                    context=message.caption,
                )
                self._last_note_id = note.id
                return OutboundMessage(
                    platform=message.platform,
                    recipient_id=message.sender_id,
                    text=f"✓ Image captured." + (f" Caption: \"{message.caption}\"" if message.caption else ""),
                    reply_to_id=message.platform_message_id,
                )
            
            case MessageType.DOCUMENT:
                note = await self.capture.create_from_file(
                    file_bytes=media_bytes,
                    filename=_extract_filename(message),
                    mime_type=message.media_mime_type or "application/octet-stream",
                    context=message.caption,
                )
                self._last_note_id = note.id
                return OutboundMessage(
                    platform=message.platform,
                    recipient_id=message.sender_id,
                    text=f"✓ Document captured. Processing.",
                    reply_to_id=message.platform_message_id,
                )
    
    async def _handle_search(self, message: InboundMessage) -> OutboundMessage:
        """Search the knowledge base and return top results."""
        query = _strip_command(message.text, ["/search", "/s", "find my notes on", "find notes about"])
        
        results = await self.search.search(query=query, limit=5)
        
        if not results:
            return OutboundMessage(
                platform=message.platform,
                recipient_id=message.sender_id,
                text=f"Nothing found for \"{query}\". Try different keywords?",
            )
        
        # Format results for chat
        lines = [f"Found {len(results)} results for \"{query}\":\n"]
        for i, r in enumerate(results, 1):
            date = r.created_at.strftime("%b %d")
            lines.append(f"{i}. *{r.title}* ({date})")
            if r.synthesis:
                lines.append(f"   {r.synthesis[:120]}...")
            lines.append("")
        
        return OutboundMessage(
            platform=message.platform,
            recipient_id=message.sender_id,
            text="\n".join(lines),
        )
    
    async def _handle_ask(self, message: InboundMessage) -> OutboundMessage:
        """Answer a question using the knowledge base."""
        question = _strip_command(message.text, ["/ask", "/a", "what did I save about"])
        
        answer = await self.search.ask(question=question)
        
        response_text = answer.text
        if answer.sources:
            source_titles = [s.title for s in answer.sources[:3]]
            response_text += f"\n\n_Sources: {', '.join(source_titles)}_"
        
        return OutboundMessage(
            platform=message.platform,
            recipient_id=message.sender_id,
            text=response_text,
        )
    
    async def _handle_brief(self, message: InboundMessage) -> OutboundMessage:
        """Send today's daily brief."""
        brief = await self.agent.get_daily_brief()
        
        return OutboundMessage(
            platform=message.platform,
            recipient_id=message.sender_id,
            text=brief.formatted_text,
        )
    
    async def _handle_recent(self, message: InboundMessage) -> OutboundMessage:
        """Show recently captured notes."""
        # Parse count from message (default 5)
        count = 5
        parts = message.text.strip().split()
        if len(parts) > 1 and parts[-1].isdigit():
            count = min(int(parts[-1]), 10)
        
        notes = await self.capture.get_recent(limit=count)
        
        lines = [f"Last {len(notes)} captures:\n"]
        for n in notes:
            date = n.created_at.strftime("%b %d %I:%M%p")
            status = "✓" if n.processing_status == "complete" else "⏳"
            title = n.title or n.raw_content[:50] + "..."
            lines.append(f"{status} *{title}*")
            lines.append(f"   {n.source_type} · {date}")
            lines.append("")
        
        return OutboundMessage(
            platform=message.platform,
            recipient_id=message.sender_id,
            text="\n".join(lines),
        )
    
    async def _handle_star(self, message: InboundMessage) -> OutboundMessage:
        """Star the most recently captured note."""
        if not self._last_note_id:
            return OutboundMessage(
                platform=message.platform,
                recipient_id=message.sender_id,
                text="Nothing to star yet. Capture something first.",
            )
        await self.capture.star_note(self._last_note_id)
        return OutboundMessage(
            platform=message.platform,
            recipient_id=message.sender_id,
            text="⭐ Starred.",
        )
    
    async def _handle_tag(self, message: InboundMessage) -> OutboundMessage:
        """Tag the most recently captured note."""
        tag_name = _strip_command(message.text, ["/tag"]).strip("#").strip()
        if not tag_name:
            return OutboundMessage(
                platform=message.platform,
                recipient_id=message.sender_id,
                text="Usage: /tag tagname",
            )
        if not self._last_note_id:
            return OutboundMessage(
                platform=message.platform,
                recipient_id=message.sender_id,
                text="Nothing to tag yet. Capture something first.",
            )
        await self.capture.tag_note(self._last_note_id, tag_name)
        return OutboundMessage(
            platform=message.platform,
            recipient_id=message.sender_id,
            text=f"Tagged #{tag_name}.",
        )
    
    async def _handle_status(self, message: InboundMessage) -> OutboundMessage:
        """System health check."""
        health = await self.harness.health()
        stats = await self.capture.get_stats()
        
        lines = [
            "Mimir Status:",
            f"  Notes: {stats.total_notes} ({stats.pending_processing} processing)",
            f"  Connections: {stats.total_connections}",
            f"  Concepts: {stats.total_concepts}",
            "",
            "AI Engine:",
        ]
        for op, is_healthy in health.items():
            status = "●" if is_healthy else "○"
            lines.append(f"  {status} {op}")
        
        return OutboundMessage(
            platform=message.platform,
            recipient_id=message.sender_id,
            text="\n".join(lines),
        )
    
    async def _handle_help(self, message: InboundMessage) -> OutboundMessage:
        """Show available commands."""
        return OutboundMessage(
            platform=message.platform,
            recipient_id=message.sender_id,
            text=(
                "*Mimir Commands*\n\n"
                "Just send anything to capture it.\n\n"
                "/search <query> — Find notes\n"
                "/ask <question> — Ask your brain\n"
                "/brief — Today's daily brief\n"
                "/recent [n] — Last n captures\n"
                "/star — Star last capture\n"
                "/tag <name> — Tag last capture\n"
                "/status — System health\n"
                "/help — This message"
            ),
        )
```

---

## 5. PLATFORM ADAPTERS

### 5.1 Adapter Interface

```python
# src/bridge/adapters/base.py

from abc import ABC, abstractmethod

class PlatformAdapter(ABC):
    """
    Each platform adapter handles:
    1. Receiving messages (webhook or polling)
    2. Normalizing them into InboundMessage
    3. Sending OutboundMessages using the platform's API
    4. Platform-specific formatting
    """
    
    platform: Platform
    
    @abstractmethod
    async def setup(self, app) -> None:
        """Register webhook routes or start polling."""
    
    @abstractmethod
    async def send(self, message: OutboundMessage) -> bool:
        """Send a message through this platform. Returns success."""
    
    @abstractmethod
    def format_text(self, text: str) -> str:
        """Convert generic markdown-ish text to platform-native formatting."""
    
    @abstractmethod
    async def download_media(self, media_ref: str) -> tuple[bytes, str]:
        """Download media from platform, return (bytes, mime_type)."""
```

### 5.2 Telegram Adapter

```python
# src/bridge/adapters/telegram.py

import httpx
from fastapi import Request

class TelegramAdapter(PlatformAdapter):
    """
    Telegram Bot API adapter.
    
    Setup:
    1. Create a bot via @BotFather on Telegram
    2. Get the bot token
    3. Set TELEGRAM_BOT_TOKEN in .env
    4. Mimir registers the webhook automatically on startup
    
    Features:
    - Text messages
    - Photos with captions
    - Voice messages (auto-transcribed)
    - Documents (PDF, etc.)
    - Inline keyboard buttons for search results
    - Markdown V2 formatting
    """
    
    platform = Platform.TELEGRAM
    
    def __init__(self, bot_token: str, webhook_base_url: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.webhook_base_url = webhook_base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def setup(self, app) -> None:
        """Register webhook with Telegram and add route to FastAPI."""
        
        # Register webhook endpoint
        @app.post("/bridge/telegram/webhook")
        async def telegram_webhook(request: Request):
            payload = await request.json()
            message = self._normalize(payload)
            if message:
                response = await self.handler.handle(message)
                response.text = self.format_text(response.text)
                await self.send(response)
            return {"ok": True}
        
        # Set webhook URL with Telegram
        webhook_url = f"{self.webhook_base_url}/bridge/telegram/webhook"
        await self.client.post(
            f"{self.base_url}/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["message"]}
        )
    
    def _normalize(self, payload: dict) -> InboundMessage | None:
        """Convert Telegram update to InboundMessage."""
        msg = payload.get("message")
        if not msg:
            return None
        
        message_type = MessageType.TEXT
        text = msg.get("text")
        media_url = None
        caption = msg.get("caption")
        
        if "photo" in msg:
            message_type = MessageType.IMAGE
            # Get highest resolution photo
            photo = max(msg["photo"], key=lambda p: p.get("file_size", 0))
            media_url = f"telegram_file:{photo['file_id']}"
            text = caption
        elif "voice" in msg or "audio" in msg:
            message_type = MessageType.AUDIO
            voice = msg.get("voice") or msg.get("audio")
            media_url = f"telegram_file:{voice['file_id']}"
            text = caption
        elif "document" in msg:
            message_type = MessageType.DOCUMENT
            media_url = f"telegram_file:{msg['document']['file_id']}"
            text = caption
        
        return InboundMessage(
            platform=Platform.TELEGRAM,
            platform_message_id=str(msg["message_id"]),
            sender_id=str(msg["from"]["id"]),
            timestamp=datetime.fromtimestamp(msg["date"]),
            message_type=message_type,
            text=text,
            media_url=media_url,
            caption=caption,
            media_mime_type=msg.get("document", {}).get("mime_type"),
            raw_payload=payload,
        )
    
    async def send(self, message: OutboundMessage) -> bool:
        """Send message via Telegram Bot API."""
        payload = {
            "chat_id": message.recipient_id,
            "text": message.text,
            "parse_mode": "MarkdownV2",
        }
        if message.reply_to_id:
            payload["reply_to_message_id"] = message.reply_to_id
        
        resp = await self.client.post(f"{self.base_url}/sendMessage", json=payload)
        return resp.status_code == 200
    
    async def download_media(self, media_ref: str) -> tuple[bytes, str]:
        """Download file from Telegram servers."""
        file_id = media_ref.replace("telegram_file:", "")
        
        # Get file path
        resp = await self.client.get(f"{self.base_url}/getFile?file_id={file_id}")
        file_path = resp.json()["result"]["file_path"]
        
        # Download file
        file_resp = await self.client.get(
            f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
        )
        
        # Guess mime type from path
        import mimetypes
        mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        
        return file_resp.content, mime
    
    def format_text(self, text: str) -> str:
        """Convert to Telegram MarkdownV2."""
        # Telegram MarkdownV2 requires escaping special chars
        # outside of formatting marks
        import re
        special_chars = r'_[]()~`>#+-=|{}.!'
        
        # Preserve *bold* and _italic_ formatting, escape the rest
        # This is simplified — production code needs a proper parser
        lines = text.split('\n')
        formatted = []
        for line in lines:
            # Escape special chars not part of formatting
            escaped = re.sub(r'([' + re.escape(special_chars) + r'])', r'\\\1', line)
            # Restore intended formatting
            escaped = escaped.replace('\\*', '*').replace('\\_', '_')
            formatted.append(escaped)
        
        return '\n'.join(formatted)
```

### 5.3 WhatsApp Adapter (via WhatsApp Business API / Cloud API)

```python
# src/bridge/adapters/whatsapp.py

import httpx
import hmac
import hashlib
from fastapi import Request, HTTPException

class WhatsAppAdapter(PlatformAdapter):
    """
    WhatsApp Cloud API adapter (Meta Business Platform).
    
    Setup:
    1. Create a Meta Developer account
    2. Create a WhatsApp Business App
    3. Get: Phone Number ID, Access Token, Verify Token
    4. Set webhook URL to {mimir_url}/bridge/whatsapp/webhook
    5. Subscribe to 'messages' webhook field
    
    For self-hosted alternative: use whatsapp-web.js bridge
    (see section 5.7 for the unofficial adapter).
    
    Features:
    - Text messages
    - Images with captions
    - Audio messages (voice notes)
    - Documents
    - Location sharing
    - Interactive list messages for search results
    """
    
    platform = Platform.WHATSAPP
    
    def __init__(self, phone_number_id: str, access_token: str,
                 verify_token: str, app_secret: str):
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.verify_token = verify_token
        self.app_secret = app_secret
        self.base_url = f"https://graph.facebook.com/v21.0/{phone_number_id}"
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Authorization": f"Bearer {access_token}"}
        )
    
    async def setup(self, app) -> None:
        """Register webhook routes."""
        
        # Webhook verification (GET)
        @app.get("/bridge/whatsapp/webhook")
        async def whatsapp_verify(request: Request):
            params = request.query_params
            mode = params.get("hub.mode")
            token = params.get("hub.verify_token")
            challenge = params.get("hub.challenge")
            
            if mode == "subscribe" and token == self.verify_token:
                return int(challenge)
            raise HTTPException(status_code=403)
        
        # Webhook handler (POST)
        @app.post("/bridge/whatsapp/webhook")
        async def whatsapp_webhook(request: Request):
            # Verify signature
            body = await request.body()
            signature = request.headers.get("x-hub-signature-256", "")
            expected = "sha256=" + hmac.new(
                self.app_secret.encode(), body, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise HTTPException(status_code=403)
            
            payload = await request.json()
            messages = self._extract_messages(payload)
            
            for message in messages:
                response = await self.handler.handle(message)
                response.text = self.format_text(response.text)
                await self.send(response)
            
            return {"ok": True}
    
    def _extract_messages(self, payload: dict) -> list[InboundMessage]:
        """Extract messages from WhatsApp webhook payload."""
        messages = []
        
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    messages.append(self._normalize(msg))
        
        return messages
    
    def _normalize(self, msg: dict) -> InboundMessage:
        """Convert WhatsApp message to InboundMessage."""
        msg_type = msg.get("type", "text")
        
        message_type = MessageType.TEXT
        text = None
        media_url = None
        caption = None
        location = None
        
        match msg_type:
            case "text":
                text = msg["text"]["body"]
            case "image":
                message_type = MessageType.IMAGE
                media_url = f"whatsapp_media:{msg['image']['id']}"
                caption = msg["image"].get("caption")
                text = caption
            case "audio":
                message_type = MessageType.AUDIO
                media_url = f"whatsapp_media:{msg['audio']['id']}"
            case "document":
                message_type = MessageType.DOCUMENT
                media_url = f"whatsapp_media:{msg['document']['id']}"
                caption = msg["document"].get("caption")
                text = caption
            case "location":
                message_type = MessageType.LOCATION
                location = {
                    "lat": msg["location"]["latitude"],
                    "lng": msg["location"]["longitude"],
                }
                text = msg["location"].get("name", f"Location: {location['lat']}, {location['lng']}")
        
        return InboundMessage(
            platform=Platform.WHATSAPP,
            platform_message_id=msg["id"],
            sender_id=msg["from"],
            timestamp=datetime.fromtimestamp(int(msg["timestamp"])),
            message_type=message_type,
            text=text,
            media_url=media_url,
            caption=caption,
            location=location,
            media_mime_type=msg.get(msg_type, {}).get("mime_type"),
            raw_payload=msg,
        )
    
    async def send(self, message: OutboundMessage) -> bool:
        """Send message via WhatsApp Cloud API."""
        payload = {
            "messaging_product": "whatsapp",
            "to": message.recipient_id,
            "type": "text",
            "text": {"body": message.text}
        }
        
        resp = await self.client.post(f"{self.base_url}/messages", json=payload)
        return resp.status_code == 200
    
    async def download_media(self, media_ref: str) -> tuple[bytes, str]:
        """Download media from WhatsApp servers."""
        media_id = media_ref.replace("whatsapp_media:", "")
        
        # Get media URL
        resp = await self.client.get(
            f"https://graph.facebook.com/v21.0/{media_id}"
        )
        media_url = resp.json()["url"]
        
        # Download
        file_resp = await self.client.get(media_url)
        mime = resp.json().get("mime_type", "application/octet-stream")
        
        return file_resp.content, mime
    
    def format_text(self, text: str) -> str:
        """WhatsApp uses its own simple formatting."""
        # WhatsApp: *bold*, _italic_, ~strikethrough~, ```code```
        # Our generic format uses *bold* which already matches
        return text
```

### 5.4 SMS Adapter (via Twilio)

```python
# src/bridge/adapters/sms.py

import httpx
from fastapi import Request, Form

class SMSAdapter(PlatformAdapter):
    """
    SMS adapter via Twilio.
    
    Setup:
    1. Create Twilio account
    2. Get a phone number
    3. Set webhook URL for incoming messages
    4. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
    
    Limitations:
    - Text only (MMS images supported but carrier-dependent)
    - 1600 char limit per message (auto-splits longer responses)
    - No formatting (bold, italic, etc.)
    - Higher latency than internet-based platforms
    
    Best for: absolute minimum-friction capture when all you have is
    a basic phone. Text your thought to Mimir's number and it's saved.
    """
    
    platform = Platform.SMS
    
    def __init__(self, account_sid: str, auth_token: str, phone_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.phone_number = phone_number
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}"
        self.client = httpx.AsyncClient(
            timeout=30.0,
            auth=(account_sid, auth_token),
        )
    
    async def setup(self, app) -> None:
        @app.post("/bridge/sms/webhook")
        async def sms_webhook(
            From: str = Form(...),
            Body: str = Form(...),
            MessageSid: str = Form(...),
            NumMedia: str = Form("0"),
        ):
            message = InboundMessage(
                platform=Platform.SMS,
                platform_message_id=MessageSid,
                sender_id=From,
                timestamp=datetime.utcnow(),
                message_type=MessageType.TEXT,
                text=Body,
            )
            
            # Handle MMS media if present
            if int(NumMedia) > 0:
                # Twilio provides MediaUrl0, MediaContentType0, etc.
                message.message_type = MessageType.IMAGE
                # Media handling simplified for blueprint
            
            response = await self.handler.handle(message)
            response.text = self.format_text(response.text)
            await self.send(response)
            
            # Return TwiML empty response (we send via API instead)
            return "<Response></Response>"
    
    async def send(self, message: OutboundMessage) -> bool:
        """Send SMS via Twilio API. Auto-splits long messages."""
        texts = self._split_message(message.text, max_len=1600)
        
        for text in texts:
            resp = await self.client.post(
                f"{self.base_url}/Messages.json",
                data={
                    "From": self.phone_number,
                    "To": message.recipient_id,
                    "Body": text,
                }
            )
            if resp.status_code not in (200, 201):
                return False
        return True
    
    def format_text(self, text: str) -> str:
        """Strip all formatting for SMS."""
        import re
        # Remove markdown formatting
        text = re.sub(r'\*(.+?)\*', r'\1', text)  # bold
        text = re.sub(r'_(.+?)_', r'\1', text)    # italic
        return text
    
    def _split_message(self, text: str, max_len: int = 1600) -> list[str]:
        """Split long messages at paragraph boundaries."""
        if len(text) <= max_len:
            return [text]
        
        chunks = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > max_len:
                chunks.append(current.strip())
                current = line + "\n"
            else:
                current += line + "\n"
        if current.strip():
            chunks.append(current.strip())
        
        return chunks
    
    async def download_media(self, media_ref: str) -> tuple[bytes, str]:
        raise NotImplementedError("SMS media download not implemented in v1")
```

### 5.5 Discord Adapter

```python
# src/bridge/adapters/discord.py

class DiscordAdapter(PlatformAdapter):
    """
    Discord Bot adapter for DM-based interaction.
    
    Setup:
    1. Create Discord Application at discord.com/developers
    2. Create a Bot user
    3. Set DISCORD_BOT_TOKEN
    4. Bot listens for DMs only (not server messages)
    
    Uses discord.py library via a background asyncio task.
    
    Features:
    - Text messages
    - Image/file attachments
    - Embed formatting for search results
    - Slash commands (/search, /ask, /brief)
    """
    
    platform = Platform.DISCORD
    
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        # Implementation uses discord.py
        # Runs as an asyncio task alongside FastAPI
    
    async def setup(self, app) -> None:
        """Start Discord bot as background task."""
        import discord
        
        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)
        
        @client.event
        async def on_message(msg):
            # Only respond to DMs, ignore own messages
            if msg.author.bot or not isinstance(msg.channel, discord.DMChannel):
                return
            
            message = InboundMessage(
                platform=Platform.DISCORD,
                platform_message_id=str(msg.id),
                sender_id=str(msg.author.id),
                timestamp=msg.created_at,
                message_type=MessageType.TEXT,
                text=msg.content,
            )
            
            # Handle attachments
            if msg.attachments:
                attachment = msg.attachments[0]
                if attachment.content_type and attachment.content_type.startswith("audio"):
                    message.message_type = MessageType.AUDIO
                elif attachment.content_type and attachment.content_type.startswith("image"):
                    message.message_type = MessageType.IMAGE
                else:
                    message.message_type = MessageType.DOCUMENT
                message.media_url = attachment.url
                message.media_mime_type = attachment.content_type
            
            response = await self.handler.handle(message)
            await msg.channel.send(response.text)
        
        # Start bot in background
        import asyncio
        asyncio.create_task(client.start(self.bot_token))
    
    async def send(self, message: OutboundMessage) -> bool:
        # Discord send is handled in on_message callback
        # For proactive messages (briefs), use the REST API
        pass
    
    def format_text(self, text: str) -> str:
        """Discord uses standard Markdown."""
        return text
    
    async def download_media(self, media_ref: str) -> tuple[bytes, str]:
        """Download from Discord CDN URL."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(media_ref)
            mime = resp.headers.get("content-type", "application/octet-stream")
            return resp.content, mime
```

### 5.6 Mattermost Adapter

```python
# src/bridge/adapters/mattermost.py

class MattermostAdapter(PlatformAdapter):
    """
    Mattermost adapter — perfect for Desmond's existing Mattermost on Unraid.
    Uses Mattermost Bot accounts + outgoing webhooks.
    
    Setup:
    1. Create a Bot Account in Mattermost admin
    2. Create a dedicated channel (e.g., "mimir")
    3. Set up an Outgoing Webhook pointing to {mimir_url}/bridge/mattermost/webhook
    4. Set MATTERMOST_URL, MATTERMOST_BOT_TOKEN
    
    Can also serve as the primary notification channel for daily briefs.
    """
    
    platform = Platform.MATTERMOST
    
    # Implementation follows same pattern as Telegram
    # Mattermost REST API: POST /api/v4/posts for sending
    # Incoming webhook for receiving
```

### 5.7 WhatsApp Web.js Adapter (Self-Hosted Alternative)

```python
# src/bridge/adapters/whatsapp_web.py

class WhatsAppWebAdapter(PlatformAdapter):
    """
    Self-hosted WhatsApp adapter using whatsapp-web.js.
    No Meta Business account needed — uses your personal WhatsApp.
    
    Runs as a separate Node.js sidecar container that:
    1. Opens a WhatsApp Web session (scan QR on first run)
    2. Listens for messages to the connected number
    3. Forwards them to Mimir's bridge API
    4. Sends responses back through WhatsApp Web
    
    Setup:
    1. Add the whatsapp-bridge sidecar to docker-compose.yml
    2. Scan QR code on first launch via the bridge's web UI
    3. Send messages to yourself or from a second phone
    
    Tradeoffs vs. official API:
    + Free (no Meta Business fees)
    + Uses your personal number
    + No business verification needed
    - Technically against WhatsApp ToS (low enforcement risk for personal use)
    - Session can expire, needs re-auth
    - No official support
    
    Docker sidecar:
    ```yaml
    whatsapp-bridge:
      image: node:20-slim
      container_name: mimir-whatsapp-bridge
      volumes:
        - ./extensions/whatsapp-bridge:/app
        - whatsapp-session:/app/.wwebjs_auth
      working_dir: /app
      command: node index.js
      environment:
        - MIMIR_BRIDGE_URL=http://mimir-backend:8000/bridge/whatsapp-web/webhook
      depends_on:
        - mimir-backend
    ```
    """
    
    platform = Platform.WHATSAPP
    # Implementation deferred to the Node.js sidecar
    # FastAPI side just receives normalized messages via internal webhook
```

---

## 6. OUTBOUND DISPATCHER

### 6.1 Proactive Messaging

The bridge isn't just for receiving. Mimir proactively sends messages through configured channels:

```python
# src/bridge/dispatcher.py

class OutboundDispatcher:
    """
    Sends proactive messages from Mimir to the user.
    Used by the agent for daily briefs, connection alerts, etc.
    """
    
    def __init__(self, adapters: dict[Platform, PlatformAdapter], config: BridgeConfig):
        self.adapters = adapters
        self.config = config
    
    async def send_daily_brief(self, brief: DailyBrief):
        """
        Send the daily brief through all configured outbound channels.
        
        Config determines which platforms receive briefs:
        {
            "outbound_channels": {
                "daily_brief": ["telegram", "mattermost"],
                "connection_alert": ["telegram"],
                "resurface": ["telegram"],
            }
        }
        """
        channels = self.config.outbound_channels.get("daily_brief", [])
        
        for platform_name in channels:
            platform = Platform(platform_name)
            adapter = self.adapters.get(platform)
            if not adapter:
                continue
            
            message = OutboundMessage(
                platform=platform,
                recipient_id=self.config.user_ids[platform_name],
                text=adapter.format_text(brief.formatted_text),
            )
            await adapter.send(message)
    
    async def send_connection_alert(self, connection: Connection):
        """Notify user of an interesting new connection found."""
        channels = self.config.outbound_channels.get("connection_alert", [])
        
        text = (
            f"🔗 Connection found!\n\n"
            f"*{connection.source_note.title}*\n"
            f"↔ *{connection.target_note.title}*\n\n"
            f"{connection.explanation}"
        )
        
        for platform_name in channels:
            platform = Platform(platform_name)
            adapter = self.adapters.get(platform)
            if adapter:
                await adapter.send(OutboundMessage(
                    platform=platform,
                    recipient_id=self.config.user_ids[platform_name],
                    text=adapter.format_text(text),
                ))
    
    async def send_resurface(self, item: ResurfaceItem):
        """Nudge user with a resurfaced note."""
        channels = self.config.outbound_channels.get("resurface", [])
        
        text = (
            f"💡 Resurface: *{item.note.title}*\n\n"
            f"{item.reason}\n\n"
            f"_{item.note.synthesis[:200]}_"
        )
        
        for platform_name in channels:
            platform = Platform(platform_name)
            adapter = self.adapters.get(platform)
            if adapter:
                await adapter.send(OutboundMessage(
                    platform=platform,
                    recipient_id=self.config.user_ids[platform_name],
                    text=adapter.format_text(text),
                ))
```

---

## 7. CONFIGURATION

### 7.1 Bridge Settings (stored in SQLite `settings` table)

```json
{
  "bridge": {
    "enabled_platforms": ["telegram", "mattermost"],
    
    "telegram": {
      "bot_token": "123456:ABC-...",
      "webhook_base_url": "https://mimir.yourdomain.com",
      "user_id": "123456789"
    },
    
    "whatsapp": {
      "mode": "cloud_api",
      "phone_number_id": "...",
      "access_token": "...",
      "verify_token": "...",
      "app_secret": "...",
      "user_phone": "+1234567890"
    },
    
    "whatsapp_web": {
      "enabled": false,
      "sidecar_url": "http://mimir-whatsapp-bridge:3000"
    },
    
    "sms": {
      "twilio_account_sid": "...",
      "twilio_auth_token": "...",
      "twilio_phone_number": "+1234567890",
      "user_phone": "+1234567890"
    },
    
    "discord": {
      "bot_token": "...",
      "user_id": "123456789"
    },
    
    "mattermost": {
      "url": "https://mattermost.yourdomain.com",
      "bot_token": "...",
      "channel_id": "...",
      "user_id": "..."
    },
    
    "outbound_channels": {
      "daily_brief": ["telegram", "mattermost"],
      "connection_alert": ["telegram"],
      "resurface": ["telegram"]
    },
    
    "security": {
      "allowed_sender_ids": {
        "telegram": ["123456789"],
        "whatsapp": ["+1234567890"],
        "sms": ["+1234567890"],
        "discord": ["123456789"],
        "mattermost": ["user_id_here"]
      }
    }
  }
}
```

### 7.2 Environment Variables

```env
# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_USER_ID=

# WhatsApp Cloud API
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_APP_SECRET=
WHATSAPP_USER_PHONE=

# SMS (Twilio)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
SMS_USER_PHONE=

# Discord
DISCORD_BOT_TOKEN=
DISCORD_USER_ID=

# Mattermost
MATTERMOST_URL=
MATTERMOST_BOT_TOKEN=
MATTERMOST_CHANNEL_ID=

# Bridge general
BRIDGE_WEBHOOK_BASE_URL=https://mimir.yourdomain.com
```

---

## 8. SECURITY

### 8.1 Sender Verification

**Critical: Mimir is a single-user system.** The bridge must only respond to the configured user, not anyone who messages the bot.

```python
# src/bridge/security.py

class BridgeSecurity:
    """
    Every inbound message is checked against the allowed sender list
    before being passed to the handler.
    """
    
    def __init__(self, config: BridgeConfig):
        self.allowed_senders = config.security.allowed_sender_ids
    
    def is_authorized(self, message: InboundMessage) -> bool:
        """Check if the sender is the authorized user."""
        platform = message.platform.value
        allowed = self.allowed_senders.get(platform, [])
        return message.sender_id in allowed
    
    async def handle_unauthorized(self, message: InboundMessage, adapter: PlatformAdapter):
        """Respond to unauthorized senders."""
        await adapter.send(OutboundMessage(
            platform=message.platform,
            recipient_id=message.sender_id,
            text="This is a private Mimir instance. Access denied.",
        ))
```

### 8.2 Webhook Verification

Each adapter verifies incoming webhooks using the platform's signature mechanism (HMAC for WhatsApp, token verification for Telegram, etc.). See individual adapter implementations above.

### 8.3 API Key Passthrough

If the main Mimir API requires an API key, the bridge passes it internally. Bridge-to-core communication is on the internal Docker network and doesn't traverse the internet.

---

## 9. BRIDGE SETTINGS UI

### 9.1 Settings Page Section: "Messaging"

```
┌──────────────────────────────────────────────────────────────┐
│  Messaging Bridge                                             │
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐│
│  │  Telegram                                        [ON ●]  ││
│  │  Bot: @MimirBrainBot                                      ││
│  │  Status: ● Connected                                      ││
│  │  Your Telegram ID: 123456789                              ││
│  │  [Configure] [Test Message] [Disconnect]                  ││
│  └──────────────────────────────────────────────────────────┘│
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐│
│  │  WhatsApp                                        [OFF ○] ││
│  │  Not configured                                           ││
│  │  Mode: [Cloud API ▼] [WhatsApp Web (self-hosted)]        ││
│  │  [Set Up]                                                 ││
│  └──────────────────────────────────────────────────────────┘│
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐│
│  │  SMS                                             [OFF ○] ││
│  │  Not configured                                           ││
│  │  [Set Up]                                                 ││
│  └──────────────────────────────────────────────────────────┘│
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐│
│  │  Discord                                         [OFF ○] ││
│  │  Not configured                                           ││
│  │  [Set Up]                                                 ││
│  └──────────────────────────────────────────────────────────┘│
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐│
│  │  Mattermost                                      [ON ●]  ││
│  │  Server: mattermost.thehound.app                          ││
│  │  Channel: #mimir                                          ││
│  │  Status: ● Connected                                      ││
│  │  [Configure] [Test Message] [Disconnect]                  ││
│  └──────────────────────────────────────────────────────────┘│
│                                                               │
│  Notifications:                                               │
│  Daily Brief →    [Telegram ✓] [Mattermost ✓]               │
│  Connections →    [Telegram ✓] [Mattermost ○]               │
│  Resurface →      [Telegram ✓] [Mattermost ○]               │
│                                                               │
│  [Save Notification Preferences]                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 10. UPDATED DIRECTORY STRUCTURE (Bridge Addition)

```
backend/src/
├── bridge/
│   ├── __init__.py
│   ├── models.py              # InboundMessage, OutboundMessage, Platform
│   ├── intent.py              # Intent detection and command parsing
│   ├── handler.py             # MessageHandler — core logic
│   ├── dispatcher.py          # OutboundDispatcher — proactive messaging
│   ├── security.py            # Sender verification
│   ├── router.py              # FastAPI router for bridge endpoints
│   └── adapters/
│       ├── __init__.py
│       ├── base.py            # PlatformAdapter ABC
│       ├── telegram.py
│       ├── whatsapp.py        # Cloud API
│       ├── whatsapp_web.py    # Self-hosted via whatsapp-web.js
│       ├── sms.py             # Twilio
│       ├── discord.py
│       └── mattermost.py
├── ...rest of backend unchanged

extensions/
├── chrome/                    # Browser extension (from main blueprint)
└── whatsapp-bridge/           # whatsapp-web.js Node.js sidecar
    ├── package.json
    ├── index.js
    └── Dockerfile
```

---

## 11. DOCKER COMPOSE UPDATE

Add to the existing `docker-compose.yml`:

```yaml
services:
  # ...existing services...
  
  # Optional: WhatsApp Web bridge sidecar
  whatsapp-bridge:
    build: ./extensions/whatsapp-bridge
    container_name: mimir-whatsapp-bridge
    restart: unless-stopped
    volumes:
      - whatsapp-session:/app/.wwebjs_auth
    environment:
      - MIMIR_BRIDGE_URL=http://mimir-backend:8000/bridge/whatsapp-web/webhook
      - MIMIR_API_KEY=${API_KEY}
    depends_on:
      - mimir-backend
    # Uncomment to enable
    # profiles: ["whatsapp-web"]

volumes:
  whatsapp-session:
```

---

## 12. BRIDGE API ENDPOINTS

```
# Webhook receivers (one per platform)
POST /bridge/telegram/webhook
GET  /bridge/whatsapp/webhook          # Verification
POST /bridge/whatsapp/webhook          # Messages
POST /bridge/whatsapp-web/webhook      # From sidecar
POST /bridge/sms/webhook               # Twilio
POST /bridge/mattermost/webhook

# Bridge management
GET  /api/bridge/status                # All platform connection status
GET  /api/bridge/config                # Current bridge configuration
PUT  /api/bridge/config                # Update bridge configuration
POST /api/bridge/test/{platform}       # Send a test message
GET  /api/bridge/log                   # Recent bridge message log
```

---

## 13. IMPLEMENTATION PRIORITY

Within the phased approach from the main blueprint, the bridge slots into **Phase 3 (Extended Capture)**:

**Phase 3a — Telegram first.** Telegram is the easiest to set up (free bot, simple webhook, great media support, no business account needed). Get one platform working end-to-end, then the adapter pattern makes adding others trivial.

**Phase 3b — Mattermost.** Already running on your Unraid. Natural fit for daily brief delivery alongside capture.

**Phase 3c — WhatsApp.** Either Cloud API (if you want official) or whatsapp-web.js sidecar (if you want self-hosted). Most people already have WhatsApp open, making it the highest-friction-reduction platform for many users.

**Phase 3d — SMS and Discord.** Nice-to-haves. SMS is the ultimate fallback (works without internet apps). Discord covers the gaming/community crowd.

Build order for Claude Code:
1. `bridge/models.py` and `bridge/intent.py` — message format and intent detection
2. `bridge/handler.py` — core message handling logic
3. `bridge/adapters/base.py` — adapter interface
4. `bridge/adapters/telegram.py` — first working adapter
5. `bridge/dispatcher.py` — outbound messaging
6. `bridge/security.py` — sender verification
7. `bridge/router.py` — FastAPI route registration
8. Wire into `main.py` startup
9. Add remaining adapters one at a time

---

## 14. INTERACTION EXAMPLES

### Example 1: Quick Capture (Telegram)

```
You:   Meeting with Jake - agreed to raise pricing 10% for Q3,
       need to update the proposal by Friday

Mimir: ✓ Captured. Processing.
```

*(Behind the scenes: note created, pipeline extracts entities [Jake, Q3], concepts [pricing, proposals], finds connection to your earlier note about pricing strategy, queues a follow-up resurface for Friday)*

### Example 2: Voice Capture (WhatsApp)

```
You:   [voice message, 15 seconds]

Mimir: ✓ Voice captured:

       "Just had an idea for Quick Convert — what if we offer a
       rush tier, same day turnaround for 2x the price. Labs would
       pay for it during crunch periods."
```

### Example 3: URL + Context (Telegram)

```
You:   https://example.com/article-about-saas-pricing
       this is relevant to the Quick Convert pricing discussion

Mimir: ✓ Saved link. Fetching and processing.
```

### Example 4: Search (Any Platform)

```
You:   /search dental pricing

Mimir: Found 4 results for "dental pricing":

       1. *Quick Convert Pricing Strategy* (Jan 15)
          You've been considering a 3-tier model with rush pricing...

       2. *Meeting with Jake - Q3 Pricing* (Mar 3)
          Agreed to raise pricing 10%, update proposal by Friday...

       3. *SaaS Pricing Article: Value-Based Approaches* (Mar 3)
          Article about anchoring pricing to customer value...

       4. *Competitor Analysis: 3Shape Pricing* (Dec 8)
          3Shape charges $X per scan, comparison notes...
```

### Example 5: Ask (Any Platform)

```
You:   /ask what was our decision on Quick Convert pricing?

Mimir: Based on your notes, you and Jake agreed in the March 3rd
       meeting to raise pricing by 10% for Q3. You also captured
       an article about value-based SaaS pricing that same day,
       and noted it was relevant to this decision. Your earlier
       pricing strategy note mentioned considering a 3-tier model
       with a rush option. The proposal update was due Friday.

       Sources: Meeting with Jake - Q3 Pricing, Quick Convert
       Pricing Strategy, SaaS Pricing Article
```

### Example 6: Daily Brief (Proactive, Morning)

```
Mimir: ☀️ Good morning, Desmond. Here's your brief for March 4:

       Yesterday you captured 3 notes, including a pricing article
       that connects to your Quick Convert strategy work from January.
       
       🔗 New connection: your note about "rush tier pricing" for
       Quick Convert links to a note from December about competitor
       3Shape's per-scan pricing model. Worth revisiting?
       
       ⏰ Reminder: you noted a proposal update due Friday for Jake.
       
       📅 This day last year: you were researching the Uganda adoption
       process and saved 2 articles about international requirements.
       
       What's on your mind today?
```

---

*This addendum should be read alongside the main Mimir blueprint and the AI Harness addendum. Feed all three documents to Claude Code together.*
