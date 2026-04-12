"""Import endpoints — Notion, Obsidian, browser bookmarks."""

import io
import logging
import re
import zipfile
from datetime import datetime

from fastapi import APIRouter, File, UploadFile

from src.knowledge import database as db
from src.knowledge.models import SourceType, new_id

logger = logging.getLogger("mimir.api.import")

router = APIRouter(prefix="/api/import", tags=["import"])


def _parse_markdown_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML-ish frontmatter from markdown text.

    Returns (metadata_dict, body_text).
    """
    meta: dict = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    meta[key.strip().lower()] = val.strip().strip('"').strip("'")
            body = parts[2].strip()
    return meta, body


async def _create_note(title: str, content: str, source_type: str, source_uri: str = "") -> str:
    """Insert a note into the database, returning its ID."""
    note_id = new_id()
    now = datetime.utcnow().isoformat()
    await db.execute(
        """INSERT INTO notes (id, source_type, source_uri, title, raw_content,
           created_at, updated_at, processing_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
        (note_id, source_type, source_uri, title, content, now, now),
    )
    return note_id


@router.post("/notion")
async def import_notion(file: UploadFile = File(...)):
    """Import a Notion export (zip of markdown/csv files)."""
    data = await file.read()
    count = 0
    errors = 0

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                if not name.endswith(".md"):
                    continue
                try:
                    raw = zf.read(name).decode("utf-8", errors="replace")
                    meta, body = _parse_markdown_frontmatter(raw)
                    if not body.strip():
                        continue
                    # Notion filenames are like "Page Title abc123.md"
                    title = meta.get("title") or name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    # Strip Notion ID suffix (32 hex chars at end)
                    title = re.sub(r"\s+[0-9a-f]{32}$", "", title)
                    await _create_note(title, body, SourceType.IMPORT, f"notion:{name}")
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to import {name}: {e}")
                    errors += 1
    except zipfile.BadZipFile:
        return {"error": "Invalid zip file", "imported": 0}

    return {"imported": count, "errors": errors}


@router.post("/obsidian")
async def import_obsidian(file: UploadFile = File(...)):
    """Import an Obsidian vault export (zip of markdown files).

    Handles [[wikilinks]] by converting to plain text and inline #tags.
    """
    data = await file.read()
    count = 0
    errors = 0

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                if not name.endswith(".md"):
                    continue
                try:
                    raw = zf.read(name).decode("utf-8", errors="replace")
                    meta, body = _parse_markdown_frontmatter(raw)
                    if not body.strip():
                        continue

                    # Convert [[wikilinks]] to plain text
                    body = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), body)

                    # Extract inline #tags
                    tags = re.findall(r"(?:^|\s)#([a-zA-Z][\w/-]*)", body)

                    title = meta.get("title") or name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    note_id = await _create_note(title, body, SourceType.IMPORT, f"obsidian:{name}")

                    # Create tags
                    for tag_name in set(t.lower() for t in tags):
                        tid = new_id()
                        await db.execute("INSERT OR IGNORE INTO tags (id, name) VALUES (?, ?)", (tid, tag_name))
                        tag_row = await db.fetch_one("SELECT id FROM tags WHERE name = ?", (tag_name,))
                        if tag_row:
                            await db.execute(
                                "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
                                (note_id, tag_row["id"]),
                            )

                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to import {name}: {e}")
                    errors += 1
    except zipfile.BadZipFile:
        return {"error": "Invalid zip file", "imported": 0}

    return {"imported": count, "errors": errors}


@router.post("/bookmarks")
async def import_bookmarks(file: UploadFile = File(...)):
    """Import browser bookmarks (HTML export from Chrome/Firefox/Safari)."""
    from bs4 import BeautifulSoup

    data = await file.read()
    html = data.decode("utf-8", errors="replace")
    count = 0
    errors = 0

    try:
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("a", href=True):
            try:
                url = link["href"]
                if not url.startswith(("http://", "https://")):
                    continue
                title = link.get_text(strip=True) or url[:80]
                content = url
                # Include folder context if available
                parent_dl = link.find_parent("dl")
                if parent_dl:
                    header = parent_dl.find_previous_sibling("h3")
                    if header:
                        folder = header.get_text(strip=True)
                        content = f"{url}\n\nBookmark folder: {folder}"
                await _create_note(title, content, SourceType.URL, url)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to import bookmark: {e}")
                errors += 1
    except Exception as e:
        return {"error": f"Failed to parse bookmarks: {e}", "imported": 0}

    return {"imported": count, "errors": errors}
