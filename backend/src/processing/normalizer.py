import logging
import re
from typing import Optional

logger = logging.getLogger("mimir.processing.normalizer")


async def normalize(
    raw_content: str, source_type: str, source_uri: Optional[str] = None
) -> tuple[str, int, int]:
    """Normalize raw content. Returns (processed_content, word_count, reading_time_seconds)."""

    content = raw_content

    # For URLs, fetch the page content
    if source_type == "url" and raw_content.startswith(("http://", "https://")):
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


def _strip_html(text: str) -> str:
    if "<" not in text:
        return text
    try:
        import bleach
        return bleach.clean(text, tags=[], strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", "", text)
