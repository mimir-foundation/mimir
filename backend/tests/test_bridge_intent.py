"""Tests for bridge intent detection."""

import pytest

from src.bridge.intent import detect_intent, strip_command
from src.bridge.models import InboundMessage, Intent, MessageType, Platform


def _msg(text: str = "", message_type: str = MessageType.TEXT, media_url: str = None) -> InboundMessage:
    return InboundMessage(
        platform=Platform.TELEGRAM,
        sender_id="123",
        text=text,
        message_type=message_type,
        media_url=media_url,
    )


# --- Slash commands ---

class TestSlashCommands:
    def test_search(self):
        assert detect_intent(_msg("/search machine learning")) == Intent.SEARCH

    def test_search_short(self):
        assert detect_intent(_msg("/s transformers")) == Intent.SEARCH

    def test_ask(self):
        assert detect_intent(_msg("/ask what is attention?")) == Intent.ASK

    def test_ask_short(self):
        assert detect_intent(_msg("/a how does RAG work?")) == Intent.ASK

    def test_brief(self):
        assert detect_intent(_msg("/brief")) == Intent.DAILY_BRIEF

    def test_today(self):
        assert detect_intent(_msg("/today")) == Intent.DAILY_BRIEF

    def test_recent(self):
        assert detect_intent(_msg("/recent")) == Intent.RECENT

    def test_star(self):
        assert detect_intent(_msg("/star")) == Intent.STAR

    def test_tag(self):
        assert detect_intent(_msg("/tag important")) == Intent.TAG

    def test_status(self):
        assert detect_intent(_msg("/status")) == Intent.STATUS

    def test_help(self):
        assert detect_intent(_msg("/help")) == Intent.HELP


# --- Question patterns ---

class TestQuestionPatterns:
    def test_what_question(self):
        assert detect_intent(_msg("What do I know about Python?")) == Intent.ASK

    def test_how_question(self):
        assert detect_intent(_msg("How does my auth middleware work?")) == Intent.ASK

    def test_question_mark_only(self):
        assert detect_intent(_msg("anything about LLMs?")) == Intent.ASK

    def test_search_pattern(self):
        assert detect_intent(_msg("find my notes about docker")) == Intent.SEARCH

    def test_do_i_have(self):
        assert detect_intent(_msg("do I have anything on React hooks?")) == Intent.SEARCH


# --- Media ---

class TestMedia:
    def test_image(self):
        assert detect_intent(_msg(message_type=MessageType.IMAGE, media_url="file_123")) == Intent.CAPTURE_MEDIA

    def test_audio(self):
        assert detect_intent(_msg(message_type=MessageType.AUDIO, media_url="file_456")) == Intent.CAPTURE_MEDIA

    def test_document(self):
        assert detect_intent(_msg(message_type=MessageType.DOCUMENT, media_url="file_789")) == Intent.CAPTURE_MEDIA


# --- URL ---

class TestURL:
    def test_url_only(self):
        assert detect_intent(_msg("https://example.com/article")) == Intent.CAPTURE_URL

    def test_url_with_context(self):
        assert detect_intent(_msg("Great article https://example.com/post")) == Intent.CAPTURE_URL


# --- Default ---

class TestDefault:
    def test_plain_text(self):
        assert detect_intent(_msg("Meeting with John about the new API design")) == Intent.CAPTURE_NOTE

    def test_empty(self):
        assert detect_intent(_msg("")) == Intent.CAPTURE_NOTE


# --- strip_command ---

class TestStripCommand:
    def test_strip_search(self):
        assert strip_command("/search machine learning", ["/search ", "/s "]) == "machine learning"

    def test_strip_short(self):
        assert strip_command("/s transformers", ["/search ", "/s "]) == "transformers"

    def test_no_match(self):
        assert strip_command("hello world", ["/search "]) == "hello world"

    def test_strip_preserves_rest(self):
        assert strip_command("/ask what is attention?", ["/ask ", "/a "]) == "what is attention?"
