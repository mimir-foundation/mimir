"""File watcher — monitors /data/inbox/ for new files and auto-captures them."""

import asyncio
import logging
import os
import shutil
import threading
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger("mimir.capture.filewatcher")


class InboxHandler(FileSystemEventHandler):
    """Handles new files appearing in the inbox directory."""

    def __init__(self, inbox_path: str, documents_path: str, loop: asyncio.AbstractEventLoop):
        self.inbox_path = Path(inbox_path)
        self.documents_path = Path(documents_path)
        self.loop = loop
        self._processing = set()

    def on_created(self, event):
        if event.is_directory:
            return
        filepath = Path(event.src_path)
        if filepath.name.startswith("."):
            return
        # Debounce: wait for file to finish writing
        self.loop.call_soon_threadsafe(
            asyncio.ensure_future,
            self._handle_file(filepath),
        )

    async def _handle_file(self, filepath: Path):
        """Process a new file from the inbox."""
        if str(filepath) in self._processing:
            return
        self._processing.add(str(filepath))

        try:
            # Wait briefly for file to finish writing
            await asyncio.sleep(1)

            if not filepath.exists():
                return

            logger.info(f"New file in inbox: {filepath.name}")

            from src.knowledge import database as db
            from src.knowledge.models import SourceType, new_id
            from src.knowledge.document_store import DocumentStore
            from src.config import get_settings
            from datetime import datetime

            settings = get_settings()
            doc_store = DocumentStore(settings.documents_path)

            file_bytes = filepath.read_bytes()
            note_id = new_id()

            # Store the file
            doc_store.store_document(note_id, file_bytes, filepath.name)

            # Extract text
            content = _extract_text(file_bytes, filepath.name)

            now = datetime.utcnow().isoformat()
            await db.execute(
                """INSERT INTO notes (id, source_type, source_uri, title, raw_content,
                   created_at, updated_at, processing_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (note_id, SourceType.FILE, f"inbox:{filepath.name}", filepath.stem,
                 content, now, now),
            )

            # Move file out of inbox (or delete)
            try:
                filepath.unlink()
                logger.info(f"Processed and removed inbox file: {filepath.name}")
            except Exception as e:
                logger.warning(f"Could not remove inbox file {filepath.name}: {e}")

            logger.info(f"Auto-captured file: {filepath.name} -> {note_id}")

        except Exception as e:
            logger.error(f"Failed to process inbox file {filepath.name}: {e}")
        finally:
            self._processing.discard(str(filepath))


def _extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract text content from a file based on its extension."""
    lower = filename.lower()

    if lower.endswith(".pdf"):
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except Exception as e:
            return f"[PDF file: {filename}, extraction failed: {e}]"

    elif lower.endswith((".txt", ".md", ".markdown", ".csv", ".json", ".xml", ".html", ".log")):
        return file_bytes.decode("utf-8", errors="replace")

    elif lower.endswith(".docx"):
        try:
            import io
            from docx import Document
            doc = Document(io.BytesIO(file_bytes))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            return f"[DOCX file: {filename}, extraction failed: {e}]"

    else:
        return f"[File: {filename}, size: {len(file_bytes)} bytes]"


class FileWatcherService:
    """Manages the watchdog observer for the inbox directory."""

    def __init__(self):
        self.observer: Observer | None = None
        self._thread: threading.Thread | None = None

    def start(self, inbox_path: str, documents_path: str) -> None:
        """Start watching the inbox directory."""
        inbox = Path(inbox_path)
        inbox.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_event_loop()
        handler = InboxHandler(inbox_path, documents_path, loop)

        self.observer = Observer()
        self.observer.schedule(handler, str(inbox), recursive=False)
        self.observer.daemon = True
        self.observer.start()
        logger.info(f"File watcher started on: {inbox_path}")

    def stop(self) -> None:
        """Stop watching."""
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            logger.info("File watcher stopped")
