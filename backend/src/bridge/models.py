"""Messaging bridge models and enums."""

from datetime import datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class Platform(StrEnum):
    TELEGRAM = "telegram"
    MATTERMOST = "mattermost"


class MessageType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    DOCUMENT = "document"


class Intent(StrEnum):
    CAPTURE_NOTE = "capture_note"
    CAPTURE_URL = "capture_url"
    CAPTURE_MEDIA = "capture_media"
    SEARCH = "search"
    ASK = "ask"
    DAILY_BRIEF = "daily_brief"
    STATUS = "status"
    HELP = "help"
    RECENT = "recent"
    STAR = "star"
    TAG = "tag"


class InboundMessage(BaseModel):
    platform: str
    platform_message_id: str = ""
    sender_id: str = ""
    timestamp: Optional[datetime] = None
    message_type: str = MessageType.TEXT
    text: str = ""
    media_url: Optional[str] = None
    media_bytes: Optional[bytes] = None
    media_mime_type: Optional[str] = None
    caption: Optional[str] = None
    reply_to_id: Optional[str] = None
    raw_payload: Optional[dict] = None

    model_config = {"arbitrary_types_allowed": True}


class OutboundMessage(BaseModel):
    platform: str
    recipient_id: str
    text: str
    parse_mode: Optional[str] = None
    reply_to_id: Optional[str] = None
