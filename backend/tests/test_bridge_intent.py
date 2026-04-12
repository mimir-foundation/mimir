"""Tests for bridge intent detection."""

import pytest

from src.bridge.intent import detect_intent, strip_command
from src.bridge.models import InboundMessage, Intent, MessageType, Platform


def _msg(text: str = "", message_type: str = MessageType.TEXT, media_url: str = None, reply_to_id: str = None) -> InboundMessage:
    return InboundMessage(
        platform=Platform.TELEGRAM,
        sender_id="123",
        text=text,
        message_type=message_type,
        media_url=media_url,
        reply_to_id=reply_to_id,
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

    def test_save(self):
        assert detect_intent(_msg("/save Meeting notes from today")) == Intent.SAVE

    def test_note(self):
        assert detect_intent(_msg("/note Important idea about X")) == Intent.SAVE

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

    def test_confirm(self):
        assert detect_intent(_msg("/confirm abc123")) == Intent.CONFIRM

    def test_skip(self):
        assert detect_intent(_msg("/skip abc123")) == Intent.SKIP


# --- Questions → ASK ---

class TestQuestionPatterns:
    def test_question_mark(self):
        assert detect_intent(_msg("what do I know about Python?")) == Intent.ASK

    def test_how_question(self):
        assert detect_intent(_msg("how does my auth middleware work?")) == Intent.ASK

    def test_question_mark_only(self):
        assert detect_intent(_msg("anything about LLMs?")) == Intent.ASK

    def test_tell_me(self):
        assert detect_intent(_msg("tell me about distributed systems")) == Intent.ASK

    def test_show_me(self):
        assert detect_intent(_msg("show me notes on RAG")) == Intent.ASK

    def test_explain(self):
        assert detect_intent(_msg("explain transformers")) == Intent.ASK

    def test_summarize(self):
        assert detect_intent(_msg("summarize my meeting notes")) == Intent.ASK

    def test_find(self):
        assert detect_intent(_msg("find my notes about docker")) == Intent.SEARCH

    def test_do_i_have(self):
        assert detect_intent(_msg("do I have anything on React hooks?")) == Intent.ASK

    def test_is_question(self):
        assert detect_intent(_msg("is there a connection between RAG and fine-tuning")) == Intent.ASK


# --- Short ambiguous text → ASK (not capture) ---

class TestShortText:
    def test_short_text_defaults_to_ask(self):
        assert detect_intent(_msg("transformers")) == Intent.ASK

    def test_few_words_ask(self):
        assert detect_intent(_msg("knowledge graph stuff")) == Intent.ASK

    def test_short_phrase(self):
        assert detect_intent(_msg("latest meeting notes")) == Intent.ASK


# --- Noise → IGNORE ---

class TestNoise:
    def test_thanks(self):
        assert detect_intent(_msg("thanks")) == Intent.IGNORE

    def test_ok(self):
        assert detect_intent(_msg("ok")) == Intent.IGNORE

    def test_thumbs_up(self):
        assert detect_intent(_msg("👍")) == Intent.IGNORE

    def test_cool(self):
        assert detect_intent(_msg("cool")) == Intent.IGNORE


# --- Replies → ASK (follow-up) ---

class TestReplies:
    def test_reply_to_bot(self):
        assert detect_intent(_msg("tell me more", reply_to_id="99")) == Intent.ASK

    def test_reply_short(self):
        assert detect_intent(_msg("and what about the second point", reply_to_id="99")) == Intent.ASK


# --- Substantial text → CAPTURE_NOTE ---

class TestSubstantialCapture:
    def test_long_text_captured(self):
        long_text = "Meeting with John about the API redesign. We discussed migrating to GraphQL with a Q3 timeline. John will own the schema design and I will handle the resolver layer and testing."
        assert detect_intent(_msg(long_text)) == Intent.CAPTURE_NOTE


# --- Media always captured ---

class TestMedia:
    def test_image(self):
        assert detect_intent(_msg(message_type=MessageType.IMAGE, media_url="file_123")) == Intent.CAPTURE_MEDIA

    def test_audio(self):
        assert detect_intent(_msg(message_type=MessageType.AUDIO, media_url="file_456")) == Intent.CAPTURE_MEDIA

    def test_document(self):
        assert detect_intent(_msg(message_type=MessageType.DOCUMENT, media_url="file_789")) == Intent.CAPTURE_MEDIA


# --- URL always captured ---

class TestURL:
    def test_url_only(self):
        assert detect_intent(_msg("https://example.com/article")) == Intent.CAPTURE_URL

    def test_url_with_context(self):
        assert detect_intent(_msg("Great article https://example.com/post")) == Intent.CAPTURE_URL


# --- strip_command ---

class TestStripCommand:
    def test_strip_search(self):
        assert strip_command("/search machine learning", ["/search ", "/s "]) == "machine learning"

    def test_strip_save(self):
        assert strip_command("/save Meeting notes", ["/save ", "/note "]) == "Meeting notes"

    def test_no_match(self):
        assert strip_command("hello world", ["/search "]) == "hello world"
