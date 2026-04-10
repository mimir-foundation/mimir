"""Export API — markdown archive and JSON backup."""

import io
import json
import logging
import zipfile
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.knowledge import database as db

logger = logging.getLogger("mimir.api.export")

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/json")
async def export_json():
    """Full database export as JSON."""
    notes = await db.fetch_all("SELECT * FROM notes ORDER BY created_at")
    concepts = await db.fetch_all("SELECT * FROM concepts ORDER BY name")
    entities = await db.fetch_all("SELECT * FROM entities ORDER BY name")
    connections = await db.fetch_all("SELECT * FROM connections ORDER BY discovered_at")
    tags = await db.fetch_all("SELECT * FROM tags ORDER BY name")
    note_concepts = await db.fetch_all("SELECT * FROM note_concepts")
    note_entities = await db.fetch_all("SELECT * FROM note_entities")
    note_tags = await db.fetch_all("SELECT * FROM note_tags")
    settings = await db.fetch_all("SELECT * FROM settings")

    # Parse JSON settings values
    parsed_settings = {}
    for s in settings:
        try:
            parsed_settings[s["key"]] = json.loads(s["value"])
        except (json.JSONDecodeError, TypeError):
            parsed_settings[s["key"]] = s["value"]

    export_data = {
        "exported_at": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "notes": notes,
        "concepts": concepts,
        "entities": entities,
        "connections": connections,
        "tags": tags,
        "note_concepts": note_concepts,
        "note_entities": note_entities,
        "note_tags": note_tags,
        "settings": parsed_settings,
    }

    content = json.dumps(export_data, indent=2, default=str)

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=mimir-export-{datetime.utcnow().strftime('%Y%m%d')}.json"},
    )


@router.get("/markdown")
async def export_markdown():
    """Export all notes as a zip of markdown files."""
    notes = await db.fetch_all(
        "SELECT * FROM notes WHERE is_archived = 0 ORDER BY created_at"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for note in notes:
            # Build markdown content
            title = note["title"] or "Untitled"
            safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:80]
            date = note["created_at"][:10] if note["created_at"] else "unknown"
            filename = f"{date}_{safe_title}.md"

            # Get concepts and tags
            concepts = await db.fetch_all(
                "SELECT c.name FROM concepts c JOIN note_concepts nc ON c.id = nc.concept_id WHERE nc.note_id = ?",
                (note["id"],),
            )
            tags = await db.fetch_all(
                "SELECT t.name FROM tags t JOIN note_tags nt ON t.id = nt.tag_id WHERE nt.note_id = ?",
                (note["id"],),
            )

            # Build frontmatter
            lines = [
                "---",
                f"title: \"{title}\"",
                f"date: {note['created_at']}",
                f"source_type: {note['source_type']}",
            ]
            if note["source_uri"]:
                lines.append(f"source: {note['source_uri']}")
            if concepts:
                lines.append(f"concepts: [{', '.join(c['name'] for c in concepts)}]")
            if tags:
                lines.append(f"tags: [{', '.join(t['name'] for t in tags)}]")
            if note["is_starred"]:
                lines.append("starred: true")
            lines.append("---")
            lines.append("")

            # Synthesis
            if note["synthesis"]:
                lines.append(f"> {note['synthesis']}")
                lines.append("")

            # Content
            content = note["processed_content"] or note["raw_content"] or ""
            lines.append(content)

            md_content = "\n".join(lines)
            zf.writestr(f"notes/{filename}", md_content.encode("utf-8"))

        # Add an index file
        index_lines = ["# Mimir Export\n", f"Exported: {datetime.utcnow().isoformat()}\n",
                       f"Total notes: {len(notes)}\n\n## Notes\n"]
        for note in notes:
            title = note["title"] or "Untitled"
            date = note["created_at"][:10] if note["created_at"] else ""
            index_lines.append(f"- [{title}] ({date}) — {note['source_type']}")
        zf.writestr("INDEX.md", "\n".join(index_lines).encode("utf-8"))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=mimir-export-{datetime.utcnow().strftime('%Y%m%d')}.zip"},
    )


@router.get("/note/{note_id}")
async def export_note(note_id: str):
    """Export a single note as markdown."""
    note = await db.fetch_one("SELECT * FROM notes WHERE id = ?", (note_id,))
    if not note:
        return {"error": "Note not found"}

    title = note["title"] or "Untitled"
    content = note["processed_content"] or note["raw_content"] or ""

    concepts = await db.fetch_all(
        "SELECT c.name FROM concepts c JOIN note_concepts nc ON c.id = nc.concept_id WHERE nc.note_id = ?",
        (note_id,),
    )

    md = f"# {title}\n\n"
    if note["synthesis"]:
        md += f"> {note['synthesis']}\n\n"
    if concepts:
        md += f"**Concepts:** {', '.join(c['name'] for c in concepts)}\n\n"
    md += content

    return StreamingResponse(
        io.BytesIO(md.encode("utf-8")),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={note_id}.md"},
    )
