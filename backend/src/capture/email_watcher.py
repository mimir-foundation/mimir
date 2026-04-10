"""Email capture via IMAP polling."""

import email
import email.policy
import imaplib
import json
import logging
from datetime import datetime
from email.message import EmailMessage
from typing import Optional

from src.knowledge import database as db
from src.knowledge.models import SourceType, new_id

logger = logging.getLogger("mimir.capture.email")


class EmailWatcher:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        folder: str = "INBOX",
        auto_archive: bool = True,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.folder = folder
        self.auto_archive = auto_archive

    async def poll(self) -> list[str]:
        """Poll IMAP inbox for new emails. Returns list of created note IDs."""
        note_ids = []
        conn = None

        try:
            # Connect via standard imaplib (synchronous, but fast enough for polling)
            conn = imaplib.IMAP4_SSL(self.host, self.port)
            conn.login(self.user, self.password)
            conn.select(self.folder)

            # Search for unseen emails
            status, data = conn.search(None, "UNSEEN")
            if status != "OK" or not data[0]:
                return []

            message_ids = data[0].split()
            logger.info(f"Found {len(message_ids)} new emails")

            for msg_id in message_ids:
                try:
                    note_id = await self._process_email(conn, msg_id)
                    if note_id:
                        note_ids.append(note_id)

                        # Auto-archive (mark as read)
                        if self.auto_archive:
                            conn.store(msg_id, "+FLAGS", "\\Seen")
                except Exception as e:
                    logger.error(f"Failed to process email {msg_id}: {e}")

        except Exception as e:
            logger.error(f"IMAP polling failed: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                    conn.logout()
                except Exception:
                    pass

        return note_ids

    async def _process_email(self, conn: imaplib.IMAP4_SSL, msg_id: bytes) -> Optional[str]:
        """Parse an email and create a note from it."""
        status, data = conn.fetch(msg_id, "(RFC822)")
        if status != "OK":
            return None

        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email, policy=email.policy.default)

        subject = msg.get("Subject", "No Subject")
        sender = msg.get("From", "Unknown")
        date = msg.get("Date", "")
        message_id = msg.get("Message-ID", "")

        # Extract body
        body = ""
        html_body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode("utf-8", errors="replace")
                elif content_type == "text/html" and not body:
                    payload = part.get_payload(decode=True)
                    if payload:
                        html_body = payload.decode("utf-8", errors="replace")
        else:
            content_type = msg.get_content_type()
            payload = msg.get_payload(decode=True)
            if payload:
                if content_type == "text/plain":
                    body = payload.decode("utf-8", errors="replace")
                elif content_type == "text/html":
                    html_body = payload.decode("utf-8", errors="replace")

        # Prefer plain text, fall back to HTML
        content = body or html_body
        if not content:
            return None

        # Format as note
        raw_content = f"From: {sender}\nDate: {date}\nSubject: {subject}\n\n{content}"

        note_id = new_id()
        now = datetime.utcnow().isoformat()

        await db.execute(
            """INSERT INTO notes (id, source_type, source_uri, title, raw_content,
               created_at, updated_at, processing_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (note_id, SourceType.EMAIL, message_id, subject, raw_content, now, now),
        )

        logger.info(f"Captured email: {subject} -> {note_id}")

        # Handle attachments as separate notes
        if msg.is_multipart():
            for part in msg.walk():
                filename = part.get_filename()
                if filename:
                    await self._process_attachment(part, filename, note_id, subject)

        return note_id

    async def _process_attachment(
        self, part, filename: str, parent_note_id: str, subject: str
    ) -> Optional[str]:
        """Process an email attachment as a sub-note."""
        payload = part.get_payload(decode=True)
        if not payload:
            return None

        from src.config import get_settings
        from src.knowledge.document_store import DocumentStore

        settings = get_settings()
        doc_store = DocumentStore(settings.documents_path)

        att_note_id = new_id()
        doc_store.store_document(att_note_id, payload, filename)

        # Extract text for common types
        content = ""
        lower_name = filename.lower()
        if lower_name.endswith(".pdf"):
            try:
                import fitz
                doc = fitz.open(stream=payload, filetype="pdf")
                content = "\n\n".join(page.get_text() for page in doc)
                doc.close()
            except Exception:
                content = f"[PDF attachment: {filename}]"
        elif lower_name.endswith((".txt", ".md", ".csv", ".json")):
            content = payload.decode("utf-8", errors="replace")
        elif lower_name.endswith((".docx",)):
            try:
                import io
                from docx import Document
                doc = Document(io.BytesIO(payload))
                content = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except Exception:
                content = f"[DOCX attachment: {filename}]"
        else:
            content = f"[Attachment: {filename}, size: {len(payload)} bytes]"

        now = datetime.utcnow().isoformat()
        await db.execute(
            """INSERT INTO notes (id, source_type, source_uri, title, raw_content,
               created_at, updated_at, processing_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (att_note_id, SourceType.FILE, f"email-attachment:{parent_note_id}",
             f"{subject} — {filename}", content, now, now),
        )

        logger.info(f"Captured email attachment: {filename} -> {att_note_id}")
        return att_note_id


async def poll_email(app) -> None:
    """Scheduled job: poll IMAP for new emails."""
    settings_row = await db.fetch_one("SELECT value FROM settings WHERE key = 'capture'")
    if not settings_row:
        return

    try:
        config = json.loads(settings_row["value"])
    except (json.JSONDecodeError, TypeError):
        return

    if not config.get("email_enabled"):
        return

    from src.config import get_settings
    settings = get_settings()

    # Email settings come from env vars
    host = getattr(settings, "imap_host", None) or ""
    port = getattr(settings, "imap_port", 993)
    user = getattr(settings, "imap_user", None) or ""
    password = getattr(settings, "imap_password", None) or ""
    folder = getattr(settings, "imap_folder", "INBOX")

    if not all([host, user, password]):
        return

    watcher = EmailWatcher(
        host=host,
        port=int(port),
        user=user,
        password=password,
        folder=folder,
        auto_archive=config.get("auto_archive_email", True),
    )

    note_ids = await watcher.poll()
    if note_ids:
        logger.info(f"Email poll: captured {len(note_ids)} notes")
