"""Intent detection for inbound bridge messages."""

import re

from src.bridge.models import InboundMessage, Intent, MessageType

# Slash command mapping
SLASH_COMMANDS: dict[str, Intent] = {
    "/search": Intent.SEARCH,
    "/s": Intent.SEARCH,
    "/ask": Intent.ASK,
    "/a": Intent.ASK,
    "/save": Intent.SAVE,
    "/note": Intent.SAVE,
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

# Broad question starters — these strongly suggest a query, not a capture
QUERY_STARTERS = re.compile(
    r"^(who|what|where|when|why|how|is|are|do|does|did|can|could|"
    r"should|would|will|show|tell|find|list|get|explain|summarize|"
    r"describe|compare|give me|remind me)\b",
    re.IGNORECASE,
)

# Phrases that indicate a search intent
SEARCH_PATTERNS = re.compile(
    r"^(find my notes|do I have|search for|look up|look for|"
    r"anything about|anything on|notes about|notes on)\b",
    re.IGNORECASE,
)

# Throwaway / noise messages to ignore
NOISE_PATTERNS = re.compile(
    r"^(ok|okay|thanks|thank you|thx|ty|cool|nice|got it|great|yep|yes|no|nope|sure|hmm|hm|k|👍|👌|🙏|lol)$",
    re.IGNORECASE,
)

URL_PATTERN = re.compile(r"https?://\S+")

# Minimum word count to consider something "substantial" enough to be a note
CAPTURE_WORD_THRESHOLD = 15


def detect_intent(message: InboundMessage) -> Intent:
    """Detect the user's intent from an inbound message.

    Cascade:
    1. Slash commands (/search, /save, /ask, etc.)
    2. Non-text media → CAPTURE_MEDIA (always)
    3. URL in text → CAPTURE_URL (always)
    4. Noise / throwaway messages → IGNORE
    5. Reply to a bot message → ASK (follow-up conversation)
    6. Question patterns (broad) → ASK
    7. Search phrases → SEARCH
    8. Substantial text (15+ words) → CAPTURE_NOTE
    9. Short ambiguous text → ASK (default to query, not capture)
    """
    text = (message.text or "").strip()

    # 1. Slash commands
    if text.startswith("/"):
        first_word = text.split()[0].lower()
        if first_word in SLASH_COMMANDS:
            return SLASH_COMMANDS[first_word]

    # 2. Non-text media (photos, audio, documents always captured)
    if message.message_type != MessageType.TEXT:
        return Intent.CAPTURE_MEDIA

    # 3. URL (always capture)
    if text and URL_PATTERN.search(text):
        return Intent.CAPTURE_URL

    # 4. Noise / throwaway
    if NOISE_PATTERNS.match(text):
        return Intent.IGNORE

    # 5. Reply to bot message → follow-up query
    if message.reply_to_id:
        return Intent.ASK

    # 6. Question patterns (broad)
    if text:
        if text.endswith("?"):
            return Intent.ASK
        if QUERY_STARTERS.match(text):
            return Intent.ASK

    # 7. Search phrases
    if text and SEARCH_PATTERNS.match(text):
        return Intent.SEARCH

    # 8. Substantial text → capture as note
    word_count = len(text.split()) if text else 0
    if word_count >= CAPTURE_WORD_THRESHOLD:
        return Intent.CAPTURE_NOTE

    # 9. Short ambiguous text → default to ASK (query the knowledge base)
    if text:
        return Intent.ASK

    return Intent.IGNORE


def strip_command(text: str, prefixes: list[str]) -> str:
    """Remove a command prefix from the text and return the query portion."""
    stripped = text.strip()
    for prefix in prefixes:
        if stripped.lower().startswith(prefix):
            return stripped[len(prefix):].strip()
    return stripped
