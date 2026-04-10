"""Message handler — dispatches inbound messages to Mimir internals."""

import logging
from datetime import datetime

from src.bridge.adapters.base import PlatformAdapter
from src.bridge.intent import detect_intent, strip_command
from src.bridge.models import InboundMessage, Intent, OutboundMessage, Platform
from src.knowledge import database as db
from src.knowledge.models import SourceType, new_id

logger = logging.getLogger("mimir.bridge.handler")

HELP_TEXT = """**Mimir Messaging Bridge**

**Capture:** Just send text, URLs, images, audio, or files.
**Search:** `/search <query>` or `/s <query>`
**Ask:** `/ask <question>` or `/a <question>`
**Brief:** `/brief` or `/today`
**Recent:** `/recent`
**Star last:** `/star`
**Tag last:** `/tag <name>`
**Status:** `/status`
**Help:** `/help`

Questions ending with `?` are auto-detected as Ask queries."""


class MessageHandler:
    def __init__(self, harness, vector_store):
        self.harness = harness
        self.vector_store = vector_store

    async def handle(
        self, message: InboundMessage, adapter: PlatformAdapter
    ) -> OutboundMessage:
        """Detect intent, dispatch, log, and return a response."""
        intent = detect_intent(message)
        response_text = ""

        try:
            response_text = await self._dispatch(intent, message, adapter)
        except Exception as e:
            logger.error(f"Handler dispatch error: {e}", exc_info=True)
            response_text = f"Something went wrong: {e}"

        # Log to bridge_message_log
        await self._log_message(message, intent, response_text)

        return OutboundMessage(
            platform=message.platform,
            recipient_id=message.sender_id,
            text=response_text,
            reply_to_id=message.platform_message_id,
        )

    async def _dispatch(
        self, intent: Intent, message: InboundMessage, adapter: PlatformAdapter
    ) -> str:
        text = message.text or ""

        if intent == Intent.HELP:
            return HELP_TEXT

        if intent == Intent.STATUS:
            return await self._handle_status()

        if intent == Intent.DAILY_BRIEF:
            return await self._handle_brief()

        if intent == Intent.RECENT:
            return await self._handle_recent()

        if intent == Intent.SEARCH:
            query = strip_command(text, ["/search ", "/s "])
            return await self._handle_search(query)

        if intent == Intent.ASK:
            question = strip_command(text, ["/ask ", "/a "])
            return await self._handle_ask(question)

        if intent == Intent.STAR:
            return await self._handle_star(message.platform, message.sender_id)

        if intent == Intent.TAG:
            tag_name = strip_command(text, ["/tag "])
            return await self._handle_tag(
                message.platform, message.sender_id, tag_name
            )

        if intent == Intent.CAPTURE_MEDIA:
            return await self._handle_capture_media(message, adapter)

        if intent == Intent.CAPTURE_URL:
            return await self._handle_capture_url(message)

        # CAPTURE_NOTE (default)
        return await self._handle_capture_note(message)

    # --- Intent handlers ---

    async def _handle_capture_note(self, message: InboundMessage) -> str:
        source_type = (
            SourceType.TELEGRAM
            if message.platform == Platform.TELEGRAM
            else SourceType.MATTERMOST
        )
        from src.capture.router import _create_note

        resp = await _create_note(
            content=message.text,
            source_type=source_type,
            source_uri=f"bridge:{message.platform}:{message.platform_message_id}",
        )
        await self._update_session(message.platform, message.sender_id, resp.note_id)
        return f"Captured note: {resp.note_id[:8]}..."

    async def _handle_capture_url(self, message: InboundMessage) -> str:
        import re

        url_match = re.search(r"https?://\S+", message.text or "")
        url = url_match.group(0) if url_match else message.text
        extra = (message.text or "").replace(url, "").strip() if url_match else None

        from src.capture.router import _create_note

        resp = await _create_note(
            content=url,
            source_type=SourceType.URL,
            source_uri=url,
            context=extra or None,
        )
        await self._update_session(message.platform, message.sender_id, resp.note_id)
        return f"Captured URL: {url[:60]}..."

    async def _handle_capture_media(
        self, message: InboundMessage, adapter: PlatformAdapter
    ) -> str:
        if not message.media_url:
            return "No media found in message."

        media_bytes, mime = await adapter.download_media(message.media_url)

        # Audio: transcribe first
        content = ""
        if message.message_type == "audio":
            try:
                from src.harness import AIOperation

                content = await self.harness.complete(
                    operation=AIOperation.TRANSCRIBE,
                    prompt="",
                    audio_bytes=media_bytes,
                )
            except Exception as e:
                logger.warning(f"Transcription failed: {e}")
                content = f"[Audio: {len(media_bytes)} bytes, transcription failed]"
        if not content:
            content = message.caption or f"[Media: {mime}, {len(media_bytes)} bytes]"

        source_type = (
            SourceType.TELEGRAM
            if message.platform == Platform.TELEGRAM
            else SourceType.MATTERMOST
        )
        from src.capture.router import _create_note

        resp = await _create_note(
            content=content,
            source_type=source_type,
            source_uri=f"bridge:{message.platform}:{message.platform_message_id}",
        )
        await self._update_session(message.platform, message.sender_id, resp.note_id)
        return f"Captured media note: {resp.note_id[:8]}..."

    async def _handle_search(self, query: str) -> str:
        if not query:
            return "Usage: /search <query>"
        from src.search.engine import MimirSearch

        engine = MimirSearch(self.harness, self.vector_store)
        results = await engine.search(query, limit=5)
        if not results:
            return f"No results for: {query}"

        lines = [f"**Search: {query}**\n"]
        for i, r in enumerate(results, 1):
            title = r.title or "Untitled"
            snippet = (r.synthesis or "")[:100]
            lines.append(f"{i}. **{title}** ({r.score:.2f})\n   {snippet}")
        return "\n".join(lines)

    async def _handle_ask(self, question: str) -> str:
        if not question:
            return "Usage: /ask <question>"
        from src.search.engine import MimirSearch

        engine = MimirSearch(self.harness, self.vector_store)
        result = await engine.ask(question)
        answer = result.get("answer", "No answer.")
        sources = result.get("sources", [])
        source_text = ""
        if sources:
            titles = [s["title"] for s in sources[:3]]
            source_text = f"\n\n_Sources: {', '.join(titles)}_"
        return f"{answer}{source_text}"

    async def _handle_brief(self) -> str:
        from src.agent.daily_brief import get_latest_brief

        brief = await get_latest_brief()
        if not brief:
            return "No daily brief available yet."
        return brief["content"]

    async def _handle_recent(self) -> str:
        rows = await db.fetch_all(
            "SELECT id, title, source_type, created_at FROM notes ORDER BY created_at DESC LIMIT 5"
        )
        if not rows:
            return "No notes yet."
        lines = ["**Recent notes:**\n"]
        for r in rows:
            title = r["title"] or "Untitled"
            date = r["created_at"][:10] if r["created_at"] else ""
            lines.append(f"- **{title}** ({r['source_type']}, {date})")
        return "\n".join(lines)

    async def _handle_star(self, platform: str, sender_id: str) -> str:
        session = await db.fetch_one(
            "SELECT last_note_id FROM bridge_sessions WHERE platform = ? AND user_id = ?",
            (platform, sender_id),
        )
        if not session or not session["last_note_id"]:
            return "No recent note to star."
        note_id = session["last_note_id"]
        await db.execute("UPDATE notes SET is_starred = 1 WHERE id = ?", (note_id,))

        from src.agent.runtime import on_note_starred

        await on_note_starred(note_id, True)
        note = await db.fetch_one("SELECT title FROM notes WHERE id = ?", (note_id,))
        title = note["title"] if note else "Untitled"
        return f"Starred: {title}"

    async def _handle_tag(
        self, platform: str, sender_id: str, tag_name: str
    ) -> str:
        if not tag_name:
            return "Usage: /tag <name>"
        session = await db.fetch_one(
            "SELECT last_note_id FROM bridge_sessions WHERE platform = ? AND user_id = ?",
            (platform, sender_id),
        )
        if not session or not session["last_note_id"]:
            return "No recent note to tag."
        note_id = session["last_note_id"]
        tag_name = tag_name.strip().lower()
        tag_id = new_id()
        await db.execute(
            "INSERT OR IGNORE INTO tags (id, name) VALUES (?, ?)", (tag_id, tag_name)
        )
        tag_row = await db.fetch_one("SELECT id FROM tags WHERE name = ?", (tag_name,))
        if tag_row:
            await db.execute(
                "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
                (note_id, tag_row["id"]),
            )
        return f"Tagged with: {tag_name}"

    async def _handle_status(self) -> str:
        count = await db.fetch_one("SELECT COUNT(*) as cnt FROM notes")
        note_count = count["cnt"] if count else 0

        try:
            health = await self.harness.health()
            harness_status = "ok" if health else "degraded"
        except Exception:
            harness_status = "unknown"

        return (
            f"**Mimir Status**\n"
            f"Notes: {note_count}\n"
            f"AI Harness: {harness_status}"
        )

    # --- Session tracking ---

    async def _update_session(
        self, platform: str, user_id: str, note_id: str
    ) -> None:
        await db.execute(
            """INSERT INTO bridge_sessions (id, platform, user_id, last_note_id, last_activity)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(platform, user_id)
               DO UPDATE SET last_note_id = ?, last_activity = ?""",
            (
                new_id(),
                platform,
                user_id,
                note_id,
                datetime.utcnow().isoformat(),
                note_id,
                datetime.utcnow().isoformat(),
            ),
        )

    # --- Message logging ---

    async def _log_message(
        self,
        message: InboundMessage,
        intent: Intent,
        response_text: str,
    ) -> None:
        try:
            await db.execute(
                """INSERT INTO bridge_message_log
                   (id, platform, direction, sender_id, intent, text, media_url,
                    status, response_text, raw_payload)
                   VALUES (?, ?, 'inbound', ?, ?, ?, ?, 'ok', ?, ?)""",
                (
                    new_id(),
                    message.platform,
                    message.sender_id,
                    intent.value,
                    (message.text or "")[:500],
                    message.media_url,
                    response_text[:1000],
                    None,
                ),
            )
        except Exception as e:
            logger.warning(f"Failed to log bridge message: {e}")
