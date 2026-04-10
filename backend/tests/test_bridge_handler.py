"""Tests for bridge message handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.bridge.handler import MessageHandler
from src.bridge.models import InboundMessage, Intent, MessageType, Platform


@pytest.fixture
def mock_harness():
    harness = AsyncMock()
    harness.health = AsyncMock(return_value=True)
    return harness


@pytest.fixture
def mock_vector_store():
    return MagicMock()


@pytest.fixture
def mock_adapter():
    adapter = AsyncMock()
    adapter.platform = Platform.TELEGRAM
    adapter.format_text = MagicMock(side_effect=lambda x: x)
    adapter.download_media = AsyncMock(return_value=(b"fake", "image/png"))
    return adapter


@pytest.fixture
def handler(mock_harness, mock_vector_store):
    return MessageHandler(mock_harness, mock_vector_store)


def _msg(text: str = "", **kwargs) -> InboundMessage:
    defaults = {
        "platform": Platform.TELEGRAM,
        "sender_id": "user123",
        "platform_message_id": "msg456",
        "message_type": MessageType.TEXT,
        "text": text,
    }
    defaults.update(kwargs)
    return InboundMessage(**defaults)


class TestHandlerHelp:
    @pytest.mark.asyncio
    async def test_help_returns_help_text(self, handler, mock_adapter):
        msg = _msg("/help")
        with patch("src.bridge.handler.db") as mock_db:
            mock_db.execute = AsyncMock()
            mock_db.fetch_one = AsyncMock(return_value=None)
            resp = await handler.handle(msg, mock_adapter)
        assert "Mimir Messaging Bridge" in resp.text
        assert resp.recipient_id == "user123"


class TestHandlerStatus:
    @pytest.mark.asyncio
    async def test_status(self, handler, mock_adapter, mock_harness):
        msg = _msg("/status")
        with patch("src.bridge.handler.db") as mock_db:
            mock_db.execute = AsyncMock()
            mock_db.fetch_one = AsyncMock(return_value={"cnt": 42})
            resp = await handler.handle(msg, mock_adapter)
        assert "42" in resp.text
        assert "Mimir Status" in resp.text


class TestHandlerCapture:
    @pytest.mark.asyncio
    async def test_capture_note(self, handler, mock_adapter):
        msg = _msg("This is a new idea about knowledge graphs")
        with patch("src.bridge.handler.db") as mock_db, \
             patch("src.bridge.handler._create_note") as mock_create:
            mock_db.execute = AsyncMock()
            mock_db.fetch_one = AsyncMock(return_value=None)
            mock_resp = MagicMock()
            mock_resp.note_id = "abc123"

            # Patch the import inside handler
            with patch("src.capture.router._create_note", new=AsyncMock(return_value=mock_resp)):
                resp = await handler.handle(msg, mock_adapter)
        assert "abc123" in resp.text or "Captured" in resp.text


class TestHandlerRecent:
    @pytest.mark.asyncio
    async def test_recent(self, handler, mock_adapter):
        msg = _msg("/recent")
        fake_notes = [
            {"id": "1", "title": "Note A", "source_type": "manual", "created_at": "2024-01-01"},
            {"id": "2", "title": "Note B", "source_type": "url", "created_at": "2024-01-02"},
        ]
        with patch("src.bridge.handler.db") as mock_db:
            mock_db.execute = AsyncMock()
            mock_db.fetch_one = AsyncMock(return_value=None)
            mock_db.fetch_all = AsyncMock(return_value=fake_notes)
            resp = await handler.handle(msg, mock_adapter)
        assert "Note A" in resp.text
        assert "Note B" in resp.text


class TestHandlerBrief:
    @pytest.mark.asyncio
    async def test_brief_no_data(self, handler, mock_adapter):
        msg = _msg("/brief")
        with patch("src.bridge.handler.db") as mock_db, \
             patch("src.agent.daily_brief.get_latest_brief", new=AsyncMock(return_value=None)):
            mock_db.execute = AsyncMock()
            mock_db.fetch_one = AsyncMock(return_value=None)
            resp = await handler.handle(msg, mock_adapter)
        assert "No daily brief" in resp.text
