from datetime import datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


class SourceType(StrEnum):
    MANUAL = "manual"
    EMAIL = "email"
    URL = "url"
    FILE = "file"
    CLIPBOARD = "clipboard"
    VOICE = "voice"
    HIGHLIGHT = "highlight"
    TELEGRAM = "telegram"
    MATTERMOST = "mattermost"
    IMPORT = "import"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"


class ConnectionType(StrEnum):
    RELATED = "related"
    BUILDS_ON = "builds_on"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    INSPIRED_BY = "inspired_by"


class EntityType(StrEnum):
    PERSON = "person"
    COMPANY = "company"
    PROJECT = "project"
    PLACE = "place"
    BOOK = "book"
    TOOL = "tool"
    EVENT = "event"


class ContentType(StrEnum):
    REFERENCE = "reference"
    OPINION = "opinion"
    TUTORIAL = "tutorial"
    STORY = "story"
    IDEA = "idea"
    QUESTION = "question"
    QUOTE = "quote"
    DATA = "data"


# --- Core entities ---


class Note(BaseModel):
    id: str = Field(default_factory=new_id)
    source_type: str = SourceType.MANUAL
    source_uri: Optional[str] = None
    title: Optional[str] = None
    raw_content: str
    processed_content: Optional[str] = None
    synthesis: Optional[str] = None
    content_type: str = "text"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    processing_status: str = ProcessingStatus.PENDING
    processing_stage: Optional[str] = None
    retry_count: int = 0
    is_archived: bool = False
    is_starred: bool = False
    word_count: Optional[int] = None
    reading_time_seconds: Optional[int] = None


class Concept(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    note_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Entity(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    entity_type: str
    description: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Connection(BaseModel):
    id: str = Field(default_factory=new_id)
    source_note_id: str
    target_note_id: str
    connection_type: str = ConnectionType.RELATED
    strength: float = 0.5
    explanation: Optional[str] = None
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    surfaced: bool = False
    dismissed: bool = False


class Tag(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    color: Optional[str] = None


# --- Processing models ---


class Chunk(BaseModel):
    text: str
    chunk_index: int
    note_id: str
    token_count: int = 0


class EntityExtraction(BaseModel):
    name: str
    type: str
    role: Optional[str] = None


class ActionType(StrEnum):
    CALENDAR_EVENT = "calendar_event"
    REMINDER = "reminder"
    TASK = "task"
    CONTACT = "contact"
    FOLLOW_UP = "follow_up"


class ActionExtraction(BaseModel):
    action_type: str
    title: str = ""
    start: Optional[str] = None
    end: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    recurring: Optional[str] = None  # e.g. "weekly", "daily", "RRULE:..."
    due_date: Optional[str] = None
    contact_info: Optional[dict] = None


class ExtractionResult(BaseModel):
    suggested_title: Optional[str] = None
    concepts: list[str] = []
    entities: list[EntityExtraction] = []
    key_claims: list[str] = []
    content_type: str = "reference"
    temporal_relevance: str = "evergreen"
    expiry_hint: Optional[str] = None
    action_items: list[str] = []
    actions: list[ActionExtraction] = []


# --- API models ---


class CaptureRequest(BaseModel):
    content: str
    source_type: str = SourceType.MANUAL
    source_uri: Optional[str] = None
    title: Optional[str] = None
    tags: Optional[list[str]] = None
    context: Optional[str] = None
    timestamp: Optional[datetime] = None


class CaptureResponse(BaseModel):
    note_id: str
    status: str
    title: Optional[str] = None
    message: str


class UrlCaptureRequest(BaseModel):
    url: str
    context: Optional[str] = None
    tags: Optional[list[str]] = None


class HighlightCaptureRequest(BaseModel):
    content: str
    source_uri: str
    context: Optional[str] = None
    tags: Optional[list[str]] = None


class SearchFilters(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    source_type: Optional[str] = None
    concepts: Optional[list[str]] = None
    entities: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    content_type: Optional[str] = None


class SearchResult(BaseModel):
    note_id: str
    title: Optional[str] = None
    synthesis: Optional[str] = None
    score: float = 0.0
    highlights: Optional[str] = None
    concepts: list[str] = []
    source_type: str = ""
    created_at: Optional[datetime] = None


class NoteSummary(BaseModel):
    id: str
    title: Optional[str] = None
    synthesis: Optional[str] = None
    source_type: str
    content_type: str = "text"
    created_at: datetime
    is_starred: bool = False
    is_archived: bool = False
    word_count: Optional[int] = None
    processing_status: str = ProcessingStatus.PENDING
    concepts: list[str] = []
    tags: list[str] = []


class NoteDetail(BaseModel):
    id: str
    source_type: str
    source_uri: Optional[str] = None
    title: Optional[str] = None
    raw_content: str
    processed_content: Optional[str] = None
    synthesis: Optional[str] = None
    content_type: str = "text"
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None
    processing_status: str
    is_archived: bool = False
    is_starred: bool = False
    word_count: Optional[int] = None
    reading_time_seconds: Optional[int] = None
    concepts: list[dict] = []
    entities: list[dict] = []
    tags: list[dict] = []
    connections: list[dict] = []
