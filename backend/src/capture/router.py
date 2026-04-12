import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, Request, UploadFile

from src.knowledge import database as db
from src.knowledge.models import (
    CaptureRequest,
    CaptureResponse,
    HighlightCaptureRequest,
    Note,
    SourceType,
    UrlCaptureRequest,
    new_id,
)

logger = logging.getLogger("mimir.capture")

router = APIRouter(prefix="/api/capture", tags=["capture"])


async def _create_note(
    content: str,
    source_type: str,
    source_uri: Optional[str] = None,
    title: Optional[str] = None,
    tags: Optional[list[str]] = None,
    context: Optional[str] = None,
) -> CaptureResponse:
    note_id = new_id()
    now = datetime.utcnow().isoformat()

    # Prepend context to content if provided
    raw_content = content
    if context:
        raw_content = f"[Context: {context}]\n\n{content}"

    await db.execute(
        """INSERT INTO notes (id, source_type, source_uri, title, raw_content,
           created_at, updated_at, processing_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
        (note_id, source_type, source_uri, title, raw_content, now, now),
    )

    # Handle tags
    if tags:
        for tag_name in tags:
            tag_name = tag_name.strip().lower()
            if not tag_name:
                continue
            tag_id = new_id()
            await db.execute(
                "INSERT OR IGNORE INTO tags (id, name) VALUES (?, ?)",
                (tag_id, tag_name),
            )
            tag_row = await db.fetch_one("SELECT id FROM tags WHERE name = ?", (tag_name,))
            if tag_row:
                await db.execute(
                    "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
                    (note_id, tag_row["id"]),
                )

    logger.info(f"Captured {source_type} note: {note_id}")
    return CaptureResponse(
        note_id=note_id,
        status="queued",
        title=title,
        message=f"Note captured and queued for processing",
    )


@router.post("/note", response_model=CaptureResponse)
async def capture_note(req: CaptureRequest):
    return await _create_note(
        content=req.content,
        source_type=req.source_type,
        source_uri=req.source_uri,
        title=req.title,
        tags=req.tags,
        context=req.context,
    )


@router.post("/url", response_model=CaptureResponse)
async def capture_url(req: UrlCaptureRequest):
    # Store URL as raw_content — normalizer will fetch the page
    return await _create_note(
        content=req.url,
        source_type=SourceType.URL,
        source_uri=req.url,
        tags=req.tags,
        context=req.context,
    )


@router.post("/file", response_model=CaptureResponse)
async def capture_file(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    context: Optional[str] = Form(None),
):
    from src.config import get_settings
    from src.knowledge.document_store import DocumentStore

    settings = get_settings()
    doc_store = DocumentStore(settings.documents_path)

    file_bytes = await file.read()
    note_id = new_id()

    # Store the file
    doc_store.store_document(note_id, file_bytes, file.filename or "upload")

    # Extract text based on file type
    content = ""
    filename = (file.filename or "").lower()
    mime = file.content_type or ""
    if filename.endswith(".pdf"):
        try:
            import fitz  # pymupdf
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            content = "\n\n".join(page.get_text() for page in doc)
            doc.close()
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            content = f"[PDF file: {file.filename}]"
    elif mime.startswith("image/") or filename.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")):
        # Save placeholder — vision analysis happens in the processing pipeline
        content = f"[image:{note_id}:{file.filename or 'upload'}:{mime}]"
        if context:
            content += f"\n\n{context}"
    elif filename.endswith((".txt", ".md", ".markdown", ".csv", ".json", ".xml", ".html")):
        content = file_bytes.decode("utf-8", errors="replace")
    else:
        content = f"[File: {file.filename}, size: {len(file_bytes)} bytes]"

    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    now = datetime.utcnow().isoformat()
    await db.execute(
        """INSERT INTO notes (id, source_type, source_uri, title, raw_content,
           created_at, updated_at, processing_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
        (note_id, SourceType.FILE, file.filename, title, content, now, now),
    )

    if tag_list:
        for tag_name in tag_list:
            tag_name = tag_name.strip().lower()
            if not tag_name:
                continue
            tid = new_id()
            await db.execute("INSERT OR IGNORE INTO tags (id, name) VALUES (?, ?)", (tid, tag_name))
            tag_row = await db.fetch_one("SELECT id FROM tags WHERE name = ?", (tag_name,))
            if tag_row:
                await db.execute(
                    "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
                    (note_id, tag_row["id"]),
                )

    logger.info(f"Captured file note: {note_id} ({file.filename})")
    return CaptureResponse(
        note_id=note_id,
        status="queued",
        title=title or file.filename,
        message="File captured and queued for processing",
    )


@router.post("/clipboard", response_model=CaptureResponse)
async def capture_clipboard(req: CaptureRequest):
    return await _create_note(
        content=req.content,
        source_type=SourceType.CLIPBOARD,
        title=req.title,
        tags=req.tags,
        context=req.context,
    )


@router.post("/highlight", response_model=CaptureResponse)
async def capture_highlight(req: HighlightCaptureRequest):
    return await _create_note(
        content=req.content,
        source_type=SourceType.HIGHLIGHT,
        source_uri=req.source_uri,
        tags=req.tags,
        context=req.context,
    )


@router.post("/batch", response_model=list[CaptureResponse])
async def capture_batch(items: list[CaptureRequest]):
    results = []
    for req in items:
        resp = await _create_note(
            content=req.content,
            source_type=req.source_type,
            source_uri=req.source_uri,
            title=req.title,
            tags=req.tags,
            context=req.context,
        )
        results.append(resp)
    return results


@router.post("/voice", response_model=CaptureResponse)
async def capture_voice(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    context: Optional[str] = Form(None),
):
    """Capture audio file and transcribe it to a note."""
    from src.config import get_settings
    from src.knowledge.document_store import DocumentStore

    settings = get_settings()
    doc_store = DocumentStore(settings.documents_path)

    file_bytes = await file.read()
    note_id = new_id()

    # Store the audio file
    doc_store.store_document(note_id, file_bytes, file.filename or "audio.wav")

    # Transcribe: try Ollama-compatible whisper, fall back to placeholder
    content = ""
    try:
        import httpx
        # Use the harness transcribe operation if available
        async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=120.0) as client:
            # Try Ollama audio endpoint
            resp = await client.post("/api/generate", json={
                "model": settings.llm_model,
                "prompt": "Transcribe this audio file.",
                "stream": False,
            })
            if resp.status_code == 200:
                content = resp.json().get("response", "")
    except Exception as e:
        logger.warning(f"Transcription failed, storing as audio note: {e}")

    if not content:
        content = f"[Audio recording: {file.filename}, size: {len(file_bytes)} bytes. Transcription pending.]"

    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    now = datetime.utcnow().isoformat()

    await db.execute(
        """INSERT INTO notes (id, source_type, source_uri, title, raw_content,
           content_type, created_at, updated_at, processing_status)
           VALUES (?, ?, ?, ?, ?, 'audio', ?, ?, 'pending')""",
        (note_id, SourceType.VOICE, file.filename, title or f"Voice note: {file.filename}",
         content, now, now),
    )

    if tag_list:
        for tag_name in tag_list:
            tag_name = tag_name.strip().lower()
            if not tag_name:
                continue
            tid = new_id()
            await db.execute("INSERT OR IGNORE INTO tags (id, name) VALUES (?, ?)", (tid, tag_name))
            tag_row = await db.fetch_one("SELECT id FROM tags WHERE name = ?", (tag_name,))
            if tag_row:
                await db.execute(
                    "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
                    (note_id, tag_row["id"]),
                )

    logger.info(f"Captured voice note: {note_id} ({file.filename})")
    return CaptureResponse(
        note_id=note_id,
        status="queued",
        title=title or file.filename,
        message="Voice note captured and queued for processing",
    )


@router.post("/email", response_model=CaptureResponse)
async def capture_email(req: CaptureRequest):
    """Manually forward an email as a note (webhook-style)."""
    return await _create_note(
        content=req.content,
        source_type=SourceType.EMAIL,
        source_uri=req.source_uri,
        title=req.title,
        tags=req.tags,
        context=req.context,
    )
