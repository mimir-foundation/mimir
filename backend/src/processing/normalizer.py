import logging
import re
from typing import Optional

logger = logging.getLogger("mimir.processing.normalizer")

# Pattern for media placeholders: [image:note_id:filename:mime] or [audio:note_id:filename:mime]
_MEDIA_PLACEHOLDER = re.compile(r"^\[(image|audio):([a-f0-9-]+):([^:]+):([^\]]+)\]")


async def normalize(
    raw_content: str, source_type: str, source_uri: Optional[str] = None,
    harness=None, note_id: Optional[str] = None,
) -> tuple[str, int, int]:
    """Normalize raw content. Returns (processed_content, word_count, reading_time_seconds)."""

    content = raw_content

    # For media placeholders, run vision/transcription analysis
    media_match = _MEDIA_PLACEHOLDER.match(content.strip())
    if media_match and harness:
        media_type, file_note_id, filename, mime = media_match.groups()
        # Extract any user caption after the placeholder
        caption = content[media_match.end():].strip()
        analyzed = await _analyze_media(media_type, file_note_id, filename, mime, caption, harness)
        if analyzed:
            content = analyzed

    # For URLs, fetch the page content
    elif source_type == "url" and raw_content.startswith(("http://", "https://")):
        content = await _fetch_url(raw_content)

    # Strip HTML
    content = _strip_html(content)

    # Normalize whitespace
    content = re.sub(r"\n{3,}", "\n\n", content)
    content = re.sub(r"[ \t]+", " ", content)
    content = content.strip()

    word_count = len(content.split())
    reading_time = max(1, word_count // 200)

    return content, word_count, reading_time


async def _fetch_url(url: str) -> str:
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_links=False,
                include_images=False,
                include_tables=True,
            )
            if text:
                return text
    except Exception as e:
        logger.warning(f"trafilatura failed for {url}: {e}")

    # Fallback: basic fetch
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return _strip_html(resp.text)
    except Exception as e:
        logger.error(f"URL fetch failed for {url}: {e}")
        return f"[Failed to fetch URL: {url}]"


async def _analyze_media(
    media_type: str, note_id: str, filename: str, mime: str,
    caption: str, harness,
) -> Optional[str]:
    """Load a stored media file and analyze it via AI harness."""
    from src.config import get_settings
    from src.knowledge.document_store import DocumentStore

    settings = get_settings()
    doc_store = DocumentStore(settings.documents_path)
    files = doc_store.get_document_files(note_id)
    if not files:
        logger.warning(f"No stored files found for note {note_id}")
        return None

    file_path = files[0]
    file_bytes = file_path.read_bytes()

    if media_type == "image":
        try:
            from src.harness import AIOperation
            vision_prompt = (
                "Analyze this image for a personal knowledge base. "
                "Describe what you see in detail. If there is text in the image, transcribe it fully. "
                "If it's a screenshot, document, diagram, or whiteboard, explain its content and meaning. "
                "If it's a photo of a place, person, or object, describe it."
            )
            if caption:
                vision_prompt += f"\n\nUser's note: {caption}"
            result = await harness.complete(
                operation=AIOperation.REASON,
                prompt=vision_prompt,
                images=[file_bytes],
                max_tokens=1000,
            )
            if result and result.strip():
                if caption:
                    return f"[Context: {caption}]\n\n{result.strip()}"
                return result.strip()
        except Exception as e:
            logger.error(f"Vision analysis failed for {note_id}: {e}")

    elif media_type == "audio":
        try:
            from src.harness import AIOperation
            result = await harness.complete(
                operation=AIOperation.TRANSCRIBE,
                prompt="",
                audio_bytes=file_bytes,
            )
            if result and result.strip():
                return result.strip()
        except Exception as e:
            logger.error(f"Audio transcription failed for {note_id}: {e}")

    return None


def _strip_html(text: str) -> str:
    if "<" not in text:
        return text
    try:
        import bleach
        return bleach.clean(text, tags=[], strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", "", text)
