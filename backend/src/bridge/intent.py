"""Intent detection for inbound bridge messages."""

import re

from src.bridge.models import InboundMessage, Intent, MessageType

# Slash command mapping
SLASH_COMMANDS: dict[str, Intent] = {
    "/search": Intent.SEARCH,
    "/s": Intent.SEARCH,
    "/ask": Intent.ASK,
    "/a": Intent.ASK,
    "/brief": Intent.DAILY_BRIEF,
    "/today": Intent.DAILY_BRIEF,
    "/recent": Intent.RECENT,
    "/star": Intent.STAR,
    "/tag": Intent.TAG,
    "/status": Intent.STATUS,
    "/help": Intent.HELP,
    "/confirm": Intent.CONFIRM,
    "/skip": Intent.SKIP,
}

# Question patterns that suggest ASK intent
QUESTION_STARTERS = re.compile(
    r"^(who|what|where|when|why|how)\b", re.IGNORECASE
)
QUESTION_MARKERS = re.compile(
    r"\b(my|I)\b.*\?$|^.*\?$", re.IGNORECASE | re.DOTALL
)
SEARCH_PATTERNS = re.compile(
    r"^(find my notes|do I have|search for)\b", re.IGNORECASE
)

URL_PATTERN = re.compile(r"https?://\S+")


def detect_intent(message: InboundMessage) -> Intent:
    """Detect the user's intent from an inbound message.

    Cascade:
    1. Slash commands
    2. Question patterns → ASK; search phrases → SEARCH
    3. Media type != TEXT → CAPTURE_MEDIA
    4. URL in text → CAPTURE_URL
    5. Default → CAPTURE_NOTE
    """
    text = (message.text or "").strip()

    # 1. Slash commands
    if text.startswith("/"):
        first_word = text.split()[0].lower()
        if first_word in SLASH_COMMANDS:
            return SLASH_COMMANDS[first_word]

    # 2. Question/search patterns
    if text:
        if SEARCH_PATTERNS.match(text):
            return Intent.SEARCH
        if QUESTION_STARTERS.match(text) and ("my" in text.lower() or "i " in text.lower() or text.endswith("?")):
            return Intent.ASK
        if text.endswith("?"):
            return Intent.ASK

    # 3. Non-text media
    if message.message_type != MessageType.TEXT:
        return Intent.CAPTURE_MEDIA

    # 4. URL
    if text and URL_PATTERN.search(text):
        return Intent.CAPTURE_URL

    # 5. Default
    return Intent.CAPTURE_NOTE


def strip_command(text: str, prefixes: list[str]) -> str:
    """Remove a command prefix from the text and return the query portion."""
    stripped = text.strip()
    for prefix in prefixes:
        if stripped.lower().startswith(prefix):
            return stripped[len(prefix):].strip()
    return stripped
