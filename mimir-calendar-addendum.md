# MIMIR — Calendar Integration (Blueprint Addendum)

## Purpose

Your second brain knows what you've captured. Your calendar knows what you've committed to. Right now those are two separate worlds. This addendum connects them so Mimir can:

1. **Contextualize knowledge by time** — "What was I working on when I saved this?" / "What do I have coming up that relates to this note?"
2. **Detect conflicts proactively** — Before you double-book, Mimir catches it and tells you.
3. **Prepare you for what's next** — Before a meeting, Mimir surfaces everything you've captured that's relevant to the people, projects, or topics on the agenda.
4. **Track follow-through** — You captured "update proposal by Friday" → Mimir checks your calendar for Friday, sees no time blocked, and nudges you.

The calendar isn't just another data source. It's the **temporal spine** of your second brain — the thing that ties knowledge to action.

---

## 1. ARCHITECTURE

### 1.1 High-Level Design

```
┌────────────────────────────────────────────────────────────────────┐
│                     CALENDAR INTEGRATION                           │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │   Google      │  │   Apple /    │  │   Generic               │ │
│  │   Calendar    │  │   CalDAV     │  │   ICS Feed              │ │
│  │   Adapter     │  │   Adapter    │  │   Adapter               │ │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬──────────────┘ │
│         │                 │                      │                │
│         └────────┬────────┴──────────────────────┘                │
│                  │                                                │
│         ┌────────▼────────┐                                       │
│         │  Calendar Sync   │                                       │
│         │  Engine          │                                       │
│         │                  │                                       │
│         │ - Poll / Webhook │                                       │
│         │ - Normalize      │                                       │
│         │ - Diff & Update  │                                       │
│         └────────┬────────┘                                       │
│                  │                                                │
│         ┌────────▼────────┐         ┌───────────────────────────┐ │
│         │  Event Store     │────────▶│  Calendar Intelligence    │ │
│         │  (SQLite)        │         │                           │ │
│         │                  │◀────────│  - Conflict Detection     │ │
│         │  - Events        │         │  - Meeting Prep           │ │
│         │  - Calendars     │         │  - Time-Aware Resurfacing │ │
│         │  - Attendees     │         │  - Follow-Up Tracking     │ │
│         │  - Recurrences   │         │  - Availability Analysis  │ │
│         └─────────────────┘         └───────────────────────────┘ │
│                                              │                    │
│                                              ▼                    │
│                                     ┌─────────────────┐          │
│                                     │  MIMIR CORE     │          │
│                                     │  Agent / Bridge  │          │
│                                     │  / Dashboard     │          │
│                                     └─────────────────┘          │
└────────────────────────────────────────────────────────────────────┘
```

### 1.2 Design Principles

1. **Read-heavy, write-light.** Mimir reads your calendars constantly but only writes to them when you explicitly ask (e.g., "block time for this"). Mimir never modifies or deletes existing events.
2. **Multi-calendar aware.** Most people have 3-7 calendars (work, personal, family, kids' school, sports, church). Mimir sees all of them as one unified timeline. Conflicts between calendars are the most common and hardest to catch manually.
3. **Sync, don't depend.** Mimir maintains a local copy of all events. If a calendar provider is unreachable, Mimir still works from its cache. Calendar data is refreshed, not streamed.
4. **Privacy tiers.** Some calendars are sensitive (medical, personal). Users can mark calendars as "private" — Mimir tracks time blocks but doesn't process event details for knowledge linking.

---

## 2. DATA MODEL

### 2.1 Calendar Schema (SQLite)

```sql
-- Calendar sources (each Google Calendar, CalDAV calendar, ICS feed, etc.)
CREATE TABLE calendars (
    id TEXT PRIMARY KEY,                          -- UUID
    provider TEXT NOT NULL,                        -- 'google' | 'caldav' | 'ics' | 'outlook'
    provider_calendar_id TEXT,                     -- Provider's ID for this calendar
    name TEXT NOT NULL,                            -- "Work", "Personal", "Kids School"
    color TEXT,                                    -- Hex color for UI
    is_primary INTEGER DEFAULT 0,                  -- Is this the user's primary calendar?
    is_private INTEGER DEFAULT 0,                  -- If true, Mimir tracks time only, no content analysis
    sync_enabled INTEGER DEFAULT 1,
    last_synced_at DATETIME,
    sync_token TEXT,                               -- Provider's sync/delta token for incremental sync
    account_email TEXT,                            -- Which account this calendar belongs to
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Normalized events from all calendars
CREATE TABLE events (
    id TEXT PRIMARY KEY,                           -- UUID
    calendar_id TEXT NOT NULL REFERENCES calendars(id) ON DELETE CASCADE,
    provider_event_id TEXT,                        -- Provider's ID for this event
    title TEXT,
    description TEXT,
    location TEXT,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    all_day INTEGER DEFAULT 0,
    status TEXT DEFAULT 'confirmed',               -- 'confirmed' | 'tentative' | 'cancelled'
    visibility TEXT DEFAULT 'default',             -- 'default' | 'public' | 'private'
    recurrence_rule TEXT,                          -- RRULE string if recurring
    recurring_event_id TEXT,                       -- Parent event ID for recurrence instances
    
    -- Structured fields extracted from title/description
    meeting_type TEXT,                             -- 'meeting' | 'focus' | 'travel' | 'personal' | 'deadline' | 'reminder'
    
    -- Knowledge linking
    is_processed INTEGER DEFAULT 0,                -- Has the intelligence layer analyzed this?
    processed_at DATETIME,
    
    -- Change tracking
    etag TEXT,                                     -- Provider's etag for change detection
    raw_data JSON,                                 -- Original provider payload
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(calendar_id, provider_event_id)
);

-- Event attendees
CREATE TABLE event_attendees (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    email TEXT,
    name TEXT,
    status TEXT DEFAULT 'needs-action',            -- 'accepted' | 'declined' | 'tentative' | 'needs-action'
    is_organizer INTEGER DEFAULT 0,
    is_self INTEGER DEFAULT 0
);

-- Links between events and Mimir notes/entities
CREATE TABLE event_note_links (
    event_id TEXT REFERENCES events(id) ON DELETE CASCADE,
    note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    link_type TEXT NOT NULL,                        -- 'prep_material' | 'follow_up' | 'related' | 'action_item'
    relevance_score REAL DEFAULT 0.5,
    auto_generated INTEGER DEFAULT 1,              -- Was this link found by the agent or set by user?
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id, note_id)
);

CREATE TABLE event_entity_links (
    event_id TEXT REFERENCES events(id) ON DELETE CASCADE,
    entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    link_type TEXT DEFAULT 'attendee',              -- 'attendee' | 'topic' | 'location'
    PRIMARY KEY (event_id, entity_id)
);

-- Conflict detection results
CREATE TABLE calendar_conflicts (
    id TEXT PRIMARY KEY,
    event_a_id TEXT REFERENCES events(id) ON DELETE CASCADE,
    event_b_id TEXT REFERENCES events(id) ON DELETE CASCADE,
    conflict_type TEXT NOT NULL,                    -- 'overlap' | 'back_to_back' | 'travel_impossible' | 'double_book'
    severity TEXT NOT NULL,                         -- 'hard' (same time) | 'soft' (tight transition) | 'warning' (long day)
    description TEXT,                              -- Human-readable explanation
    resolved INTEGER DEFAULT 0,                    -- User has acknowledged/fixed
    detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_a_id, event_b_id)
);

-- Indexes
CREATE INDEX idx_events_time ON events(start_time, end_time);
CREATE INDEX idx_events_calendar ON events(calendar_id);
CREATE INDEX idx_events_status ON events(status) WHERE status != 'cancelled';
CREATE INDEX idx_attendees_email ON event_attendees(email);
CREATE INDEX idx_conflicts_unresolved ON calendar_conflicts(resolved) WHERE resolved = 0;
```

### 2.2 Normalized Event Model

```python
# src/calendar/models.py

from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class EventStatus(str, Enum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"

class MeetingType(str, Enum):
    MEETING = "meeting"
    FOCUS = "focus"
    TRAVEL = "travel"
    PERSONAL = "personal"
    DEADLINE = "deadline"
    REMINDER = "reminder"

class ConflictType(str, Enum):
    OVERLAP = "overlap"              # Two events at the same time
    BACK_TO_BACK = "back_to_back"    # No gap between events
    TRAVEL_IMPOSSIBLE = "travel_impossible"  # Different locations, not enough travel time
    DOUBLE_BOOK = "double_book"      # Same time, different calendars
    OVERLOADED_DAY = "overloaded_day"  # 8+ hours of meetings in one day

class ConflictSeverity(str, Enum):
    HARD = "hard"       # Must be resolved — true time overlap
    SOFT = "soft"       # Should be resolved — tight transitions
    WARNING = "warning" # Awareness — long day, overcommitted

class NormalizedEvent(BaseModel):
    """Platform-agnostic event representation."""
    id: str
    calendar_id: str
    calendar_name: str
    provider_event_id: str
    title: str | None
    description: str | None = None
    location: str | None = None
    start_time: datetime
    end_time: datetime
    all_day: bool = False
    status: EventStatus = EventStatus.CONFIRMED
    attendees: list["Attendee"] = []
    recurrence_rule: str | None = None
    is_private: bool = False          # From calendar-level privacy setting

class Attendee(BaseModel):
    email: str | None
    name: str | None
    status: str = "needs-action"
    is_organizer: bool = False

class CalendarConflict(BaseModel):
    event_a: NormalizedEvent
    event_b: NormalizedEvent
    conflict_type: ConflictType
    severity: ConflictSeverity
    description: str
```

---

## 3. CALENDAR ADAPTERS

### 3.1 Adapter Interface

```python
# src/calendar/adapters/base.py

from abc import ABC, abstractmethod

class CalendarAdapter(ABC):
    """
    Each calendar provider implements this interface.
    Adapters handle authentication, API specifics, and normalization.
    """
    
    provider_name: str
    
    @abstractmethod
    async def authenticate(self, credentials: dict) -> bool:
        """Verify credentials and establish connection."""
    
    @abstractmethod
    async def list_calendars(self) -> list[dict]:
        """List all calendars accessible by this account."""
    
    @abstractmethod
    async def sync_events(
        self,
        calendar_id: str,
        sync_token: str | None = None,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
    ) -> "SyncResult":
        """
        Fetch events, with incremental sync if sync_token is provided.
        Returns new/updated/deleted events + new sync token.
        """
    
    @abstractmethod
    async def create_event(self, calendar_id: str, event: NormalizedEvent) -> str:
        """Create an event. Returns provider event ID."""
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the connection is alive."""

class SyncResult(BaseModel):
    events: list[NormalizedEvent]        # New and updated events
    deleted_event_ids: list[str]         # Events that were deleted
    next_sync_token: str | None          # Token for next incremental sync
    full_sync_required: bool = False     # If true, token was invalid, did full sync
```

### 3.2 Google Calendar Adapter

```python
# src/calendar/adapters/google_calendar.py

import httpx
from datetime import datetime, timedelta

class GoogleCalendarAdapter(CalendarAdapter):
    """
    Google Calendar API v3 adapter.
    
    Authentication: OAuth 2.0
    
    Setup flow:
    1. User clicks "Connect Google Calendar" in Settings
    2. Mimir redirects to Google OAuth consent screen
    3. User grants calendar read (+ optional write) access
    4. Google redirects back with auth code
    5. Mimir exchanges code for access + refresh tokens
    6. Tokens stored encrypted in settings DB
    
    Required scopes:
    - https://www.googleapis.com/auth/calendar.readonly    (read events)
    - https://www.googleapis.com/auth/calendar.events      (optional: create events)
    
    Setup requirements:
    - Google Cloud project with Calendar API enabled
    - OAuth 2.0 client ID (Web application type)
    - Redirect URI: {mimir_url}/api/calendar/google/callback
    """
    
    provider_name = "google"
    
    def __init__(self, client_id: str, client_secret: str,
                 redirect_uri: str, tokens: dict | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.tokens = tokens  # {"access_token": ..., "refresh_token": ..., "expires_at": ...}
        self.base_url = "https://www.googleapis.com/calendar/v3"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    def get_auth_url(self, state: str = "") -> str:
        """Generate OAuth consent URL for the user to visit."""
        from urllib.parse import urlencode
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/calendar.readonly",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    
    async def exchange_code(self, code: str) -> dict:
        """Exchange auth code for tokens."""
        resp = await self.client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }
        )
        resp.raise_for_status()
        data = resp.json()
        self.tokens = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_at": datetime.utcnow().timestamp() + data["expires_in"],
        }
        return self.tokens
    
    async def _ensure_valid_token(self):
        """Refresh access token if expired."""
        if not self.tokens:
            raise RuntimeError("Not authenticated")
        
        if datetime.utcnow().timestamp() >= self.tokens["expires_at"] - 60:
            resp = await self.client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "refresh_token": self.tokens["refresh_token"],
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                }
            )
            resp.raise_for_status()
            data = resp.json()
            self.tokens["access_token"] = data["access_token"]
            self.tokens["expires_at"] = datetime.utcnow().timestamp() + data["expires_in"]
            # Persist updated tokens
            await self._save_tokens()
    
    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an authenticated API request."""
        await self._ensure_valid_token()
        resp = await self.client.request(
            method,
            f"{self.base_url}{path}",
            headers={"Authorization": f"Bearer {self.tokens['access_token']}"},
            **kwargs,
        )
        resp.raise_for_status()
        return resp.json()
    
    async def authenticate(self, credentials: dict) -> bool:
        """Verify stored tokens work."""
        try:
            await self._ensure_valid_token()
            await self._request("GET", "/users/me/calendarList", params={"maxResults": 1})
            return True
        except Exception:
            return False
    
    async def list_calendars(self) -> list[dict]:
        """List all calendars for this Google account."""
        data = await self._request("GET", "/users/me/calendarList")
        return [
            {
                "provider_calendar_id": cal["id"],
                "name": cal["summary"],
                "color": cal.get("backgroundColor"),
                "is_primary": cal.get("primary", False),
                "access_role": cal.get("accessRole"),
            }
            for cal in data.get("items", [])
        ]
    
    async def sync_events(
        self,
        calendar_id: str,
        sync_token: str | None = None,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
    ) -> SyncResult:
        """
        Incremental sync using Google's syncToken.
        
        First sync: fetches all events from time_min to time_max.
        Subsequent syncs: uses syncToken to get only changes.
        """
        params = {"singleEvents": "true", "maxResults": 2500}
        
        if sync_token:
            # Incremental sync
            params["syncToken"] = sync_token
        else:
            # Full sync
            if time_min:
                params["timeMin"] = time_min.isoformat() + "Z"
            else:
                # Default: sync from 30 days ago
                params["timeMin"] = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"
            if time_max:
                params["timeMax"] = time_max.isoformat() + "Z"
            else:
                # Default: sync up to 90 days ahead
                params["timeMax"] = (datetime.utcnow() + timedelta(days=90)).isoformat() + "Z"
            params["orderBy"] = "startTime"
        
        events = []
        deleted_ids = []
        next_page_token = None
        next_sync_token = None
        full_sync_required = False
        
        while True:
            if next_page_token:
                params["pageToken"] = next_page_token
            
            try:
                data = await self._request("GET", f"/calendars/{calendar_id}/events", params=params)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 410:
                    # Sync token expired — need full sync
                    return SyncResult(
                        events=[], deleted_event_ids=[],
                        next_sync_token=None, full_sync_required=True,
                    )
                raise
            
            for item in data.get("items", []):
                if item.get("status") == "cancelled":
                    deleted_ids.append(item["id"])
                else:
                    events.append(self._normalize_event(item, calendar_id))
            
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                next_sync_token = data.get("nextSyncToken")
                break
        
        return SyncResult(
            events=events,
            deleted_event_ids=deleted_ids,
            next_sync_token=next_sync_token,
            full_sync_required=full_sync_required,
        )
    
    def _normalize_event(self, item: dict, calendar_id: str) -> NormalizedEvent:
        """Convert Google Calendar event to NormalizedEvent."""
        start = item.get("start", {})
        end = item.get("end", {})
        
        all_day = "date" in start
        
        if all_day:
            start_time = datetime.fromisoformat(start["date"])
            end_time = datetime.fromisoformat(end["date"])
        else:
            start_time = datetime.fromisoformat(start["dateTime"])
            end_time = datetime.fromisoformat(end["dateTime"])
        
        attendees = []
        for att in item.get("attendees", []):
            attendees.append(Attendee(
                email=att.get("email"),
                name=att.get("displayName"),
                status=att.get("responseStatus", "needsAction"),
                is_organizer=att.get("organizer", False),
            ))
        
        return NormalizedEvent(
            id="",  # Set by event store
            calendar_id=calendar_id,
            calendar_name="",  # Resolved by sync engine
            provider_event_id=item["id"],
            title=item.get("summary"),
            description=item.get("description"),
            location=item.get("location"),
            start_time=start_time,
            end_time=end_time,
            all_day=all_day,
            status=EventStatus(item.get("status", "confirmed")),
            attendees=attendees,
            recurrence_rule=item.get("recurrence", [None])[0] if item.get("recurrence") else None,
        )
    
    async def create_event(self, calendar_id: str, event: NormalizedEvent) -> str:
        """Create a new event on Google Calendar."""
        body = {
            "summary": event.title,
            "description": event.description,
            "location": event.location,
            "start": {"dateTime": event.start_time.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": event.end_time.isoformat(), "timeZone": "UTC"},
        }
        data = await self._request("POST", f"/calendars/{calendar_id}/events", json=body)
        return data["id"]
    
    async def health_check(self) -> bool:
        return await self.authenticate({})
```

### 3.3 CalDAV Adapter (Apple Calendar, Fastmail, Nextcloud, etc.)

```python
# src/calendar/adapters/caldav_adapter.py

class CalDAVAdapter(CalendarAdapter):
    """
    CalDAV adapter — works with any CalDAV-compliant server.
    
    Covers:
    - Apple Calendar (iCloud: caldav.icloud.com)
    - Fastmail
    - Nextcloud
    - Radicale
    - Baikal
    - Any self-hosted CalDAV server
    
    Authentication:
    - Basic auth (username + app-specific password)
    - For iCloud: requires app-specific password from appleid.apple.com
    
    Setup:
    1. Enter CalDAV server URL
    2. Enter username and app-specific password
    3. Mimir discovers available calendars via PROPFIND
    4. User selects which calendars to sync
    
    Library: caldav (Python CalDAV client)
    Install: pip install caldav
    
    Sync strategy:
    - CalDAV doesn't have a syncToken like Google
    - Use ctag (calendar tag) to detect if calendar has changed
    - If ctag changed, use etag on individual events to find what changed
    - For initial sync, fetch all events in time range
    """
    
    provider_name = "caldav"
    
    def __init__(self, server_url: str, username: str, password: str):
        self.server_url = server_url
        self.username = username
        self.password = password
        self._client = None
        self._principal = None
    
    async def _get_client(self):
        """Lazy-initialize CalDAV client."""
        if self._client is None:
            import caldav
            import asyncio
            
            # caldav library is synchronous, run in thread pool
            def connect():
                client = caldav.DAVClient(
                    url=self.server_url,
                    username=self.username,
                    password=self.password,
                )
                principal = client.principal()
                return client, principal
            
            self._client, self._principal = await asyncio.to_thread(connect)
        return self._client, self._principal
    
    async def authenticate(self, credentials: dict) -> bool:
        try:
            await self._get_client()
            return True
        except Exception:
            return False
    
    async def list_calendars(self) -> list[dict]:
        """Discover calendars via CalDAV PROPFIND."""
        import asyncio
        _, principal = await self._get_client()
        
        def fetch():
            calendars = principal.calendars()
            return [
                {
                    "provider_calendar_id": str(cal.url),
                    "name": cal.name or "Unnamed Calendar",
                    "color": getattr(cal, 'color', None),
                    "is_primary": False,
                }
                for cal in calendars
            ]
        
        return await asyncio.to_thread(fetch)
    
    async def sync_events(
        self,
        calendar_id: str,
        sync_token: str | None = None,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
    ) -> SyncResult:
        """
        Sync events from CalDAV server.
        
        sync_token here is the ctag. If it hasn't changed, no sync needed.
        If it has changed, we do a date-range search and diff against local.
        """
        import asyncio
        import caldav
        from icalendar import Calendar as iCalendar
        
        _, principal = await self._get_client()
        
        def fetch():
            cal = caldav.Calendar(client=self._client, url=calendar_id)
            
            # Check ctag
            ctag = cal.get_properties(["{http://calendarserver.org/ns/}getctag"])
            current_ctag = list(ctag.values())[0] if ctag else None
            
            if sync_token and current_ctag == sync_token:
                # No changes
                return SyncResult(
                    events=[], deleted_event_ids=[],
                    next_sync_token=current_ctag,
                )
            
            # Fetch events in range
            t_min = time_min or (datetime.utcnow() - timedelta(days=30))
            t_max = time_max or (datetime.utcnow() + timedelta(days=90))
            
            raw_events = cal.date_search(start=t_min, end=t_max, expand=True)
            
            events = []
            for raw in raw_events:
                parsed = iCalendar.from_ical(raw.data)
                for component in parsed.walk():
                    if component.name == "VEVENT":
                        events.append(_ical_to_normalized(component, calendar_id))
            
            return SyncResult(
                events=events,
                deleted_event_ids=[],  # CalDAV doesn't report deletes in search
                next_sync_token=current_ctag,
            )
        
        return await asyncio.to_thread(fetch)
    
    async def create_event(self, calendar_id: str, event: NormalizedEvent) -> str:
        """Create event via CalDAV."""
        import asyncio
        import caldav
        from icalendar import Calendar as iCalendar, Event as iEvent
        
        def create():
            cal = caldav.Calendar(client=self._client, url=calendar_id)
            
            ical = iCalendar()
            ical.add("prodid", "-//Mimir//EN")
            ical.add("version", "2.0")
            
            vevent = iEvent()
            vevent.add("summary", event.title)
            vevent.add("dtstart", event.start_time)
            vevent.add("dtend", event.end_time)
            if event.description:
                vevent.add("description", event.description)
            if event.location:
                vevent.add("location", event.location)
            
            ical.add_component(vevent)
            
            created = cal.save_event(ical.to_ical().decode())
            return str(created.url)
        
        return await asyncio.to_thread(create)
    
    async def health_check(self) -> bool:
        return await self.authenticate({})


def _ical_to_normalized(component, calendar_id: str) -> NormalizedEvent:
    """Convert an icalendar VEVENT component to NormalizedEvent."""
    start = component.get("dtstart").dt
    end = component.get("dtend").dt if component.get("dtend") else start + timedelta(hours=1)
    
    all_day = not hasattr(start, "hour")
    if all_day:
        start = datetime.combine(start, datetime.min.time())
        end = datetime.combine(end, datetime.min.time())
    
    attendees = []
    raw_attendees = component.get("attendee", [])
    if not isinstance(raw_attendees, list):
        raw_attendees = [raw_attendees]
    for att in raw_attendees:
        email = str(att).replace("mailto:", "")
        attendees.append(Attendee(
            email=email,
            name=att.params.get("CN", email),
            status=att.params.get("PARTSTAT", "NEEDS-ACTION").lower(),
        ))
    
    return NormalizedEvent(
        id="",
        calendar_id=calendar_id,
        calendar_name="",
        provider_event_id=str(component.get("uid", "")),
        title=str(component.get("summary", "")),
        description=str(component.get("description", "")) if component.get("description") else None,
        location=str(component.get("location", "")) if component.get("location") else None,
        start_time=start,
        end_time=end,
        all_day=all_day,
        status=EventStatus.CONFIRMED,
        attendees=attendees,
        recurrence_rule=str(component.get("rrule")) if component.get("rrule") else None,
    )
```

### 3.4 ICS Feed Adapter

```python
# src/calendar/adapters/ics_feed.py

class ICSFeedAdapter(CalendarAdapter):
    """
    Read-only adapter for ICS/iCal URL feeds.
    
    Covers:
    - Public calendars (sports schedules, holidays, school calendars)
    - Shared calendar links (Google "get shareable link")
    - Webcal:// feeds
    - Any .ics URL
    
    No authentication — just a URL that returns iCalendar data.
    Read-only: cannot create events.
    
    Sync strategy:
    - Fetch the full ICS file on each sync (typically small)
    - Parse all events and diff against local store
    - Poll interval configurable (default: every 30 minutes)
    """
    
    provider_name = "ics"
    
    def __init__(self, feed_url: str):
        self.feed_url = feed_url.replace("webcal://", "https://")
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def authenticate(self, credentials: dict) -> bool:
        try:
            resp = await self.client.head(self.feed_url)
            return resp.status_code == 200
        except Exception:
            return False
    
    async def list_calendars(self) -> list[dict]:
        """ICS feeds are a single calendar."""
        return [{
            "provider_calendar_id": self.feed_url,
            "name": "ICS Feed",
            "is_primary": False,
        }]
    
    async def sync_events(self, calendar_id: str, **kwargs) -> SyncResult:
        """Fetch and parse the entire ICS feed."""
        from icalendar import Calendar as iCalendar
        
        resp = await self.client.get(self.feed_url)
        resp.raise_for_status()
        
        parsed = iCalendar.from_ical(resp.content)
        events = []
        
        for component in parsed.walk():
            if component.name == "VEVENT":
                events.append(_ical_to_normalized(component, calendar_id))
        
        # ICS feeds don't have sync tokens — always full sync
        return SyncResult(
            events=events,
            deleted_event_ids=[],
            next_sync_token=None,
        )
    
    async def create_event(self, calendar_id: str, event: NormalizedEvent) -> str:
        raise NotImplementedError("ICS feeds are read-only")
    
    async def health_check(self) -> bool:
        return await self.authenticate({})
```

### 3.5 Microsoft Outlook/365 Adapter

```python
# src/calendar/adapters/outlook.py

class OutlookAdapter(CalendarAdapter):
    """
    Microsoft Graph API adapter for Outlook/Office 365 calendars.
    
    Authentication: OAuth 2.0 (Microsoft Identity Platform)
    
    Setup:
    1. Register app in Azure AD (portal.azure.com)
    2. Add Calendars.Read (and optionally Calendars.ReadWrite) permission
    3. Set redirect URI: {mimir_url}/api/calendar/outlook/callback
    4. User authenticates via Microsoft OAuth flow
    
    Required scopes:
    - Calendars.Read
    - Calendars.ReadWrite (optional, for creating events)
    - offline_access (for refresh tokens)
    
    Sync: Uses Microsoft's delta query for incremental sync.
    """
    
    provider_name = "outlook"
    
    def __init__(self, client_id: str, client_secret: str,
                 redirect_uri: str, tokens: dict | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.tokens = tokens
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    # OAuth flow mirrors Google Calendar adapter pattern
    # Delta sync uses: GET /me/calendarView/delta
    # Normalization maps Microsoft event schema to NormalizedEvent
    
    # Implementation follows same patterns as GoogleCalendarAdapter
    # with Microsoft Graph API specifics
```

---

## 4. SYNC ENGINE

### 4.1 Sync Orchestrator

```python
# src/calendar/sync_engine.py

class CalendarSyncEngine:
    """
    Manages periodic synchronization of all connected calendars.
    
    Sync schedule:
    - Active calendars: every 5 minutes
    - Inactive calendars (no events in next 7 days): every 30 minutes
    - ICS feeds: every 30 minutes
    - Manual sync: on-demand via API or UI button
    
    After each sync, triggers the Calendar Intelligence layer
    to check for new conflicts, meeting prep needs, etc.
    """
    
    def __init__(self, db, adapters: dict[str, CalendarAdapter], intelligence: "CalendarIntelligence"):
        self.db = db
        self.adapters = adapters
        self.intelligence = intelligence
    
    async def sync_all(self):
        """Sync all enabled calendars."""
        calendars = await self.db.get_enabled_calendars()
        
        for cal in calendars:
            try:
                adapter = self.adapters[cal.provider]
                
                result = await adapter.sync_events(
                    calendar_id=cal.provider_calendar_id,
                    sync_token=cal.sync_token,
                )
                
                if result.full_sync_required:
                    # Token expired, do full sync
                    result = await adapter.sync_events(
                        calendar_id=cal.provider_calendar_id,
                        sync_token=None,
                    )
                
                # Apply changes to local store
                await self._apply_sync_result(cal, result)
                
                # Update sync token
                await self.db.update_calendar_sync(
                    calendar_id=cal.id,
                    sync_token=result.next_sync_token,
                )
                
            except Exception as e:
                await self.db.log_sync_error(cal.id, str(e))
        
        # After sync, run intelligence checks
        await self.intelligence.run_post_sync_checks()
    
    async def _apply_sync_result(self, calendar, result: SyncResult):
        """Upsert events and remove deleted ones."""
        for event in result.events:
            event.calendar_name = calendar.name
            event.is_private = calendar.is_private
            await self.db.upsert_event(calendar.id, event)
        
        for deleted_id in result.deleted_event_ids:
            await self.db.delete_event_by_provider_id(calendar.id, deleted_id)
```

---

## 5. CALENDAR INTELLIGENCE

This is where Mimir's calendar integration becomes more than a sync tool. The intelligence layer is what makes it a second brain feature.

### 5.1 Conflict Detection

```python
# src/calendar/intelligence.py

class CalendarIntelligence:
    """
    Proactive calendar analysis that runs after every sync
    and on a schedule.
    """
    
    def __init__(self, db, harness: HarnessRouter, dispatcher):
        self.db = db
        self.harness = harness
        self.dispatcher = dispatcher
    
    async def run_post_sync_checks(self):
        """Run all intelligence checks after a calendar sync."""
        await self.detect_conflicts()
        await self.prepare_upcoming_meetings()
        await self.check_follow_up_deadlines()
        await self.analyze_availability()
    
    async def detect_conflicts(self):
        """
        Find scheduling conflicts across ALL calendars.
        
        This is the killer feature for multi-calendar users.
        Your work calendar doesn't know about your church calendar.
        Your spouse's shared calendar doesn't know about your 1:1s.
        Mimir sees everything.
        
        Conflict types:
        
        1. OVERLAP (hard)
           Two non-all-day events at the same time on different calendars.
           "You have 'Team Standup' (Work) and 'Dentist Appointment' (Personal)
            both at 10:00 AM on Thursday."
        
        2. DOUBLE_BOOK (hard)
           Two events at the same time on the SAME calendar.
           Usually means one was accepted by mistake.
        
        3. BACK_TO_BACK (soft)
           Less than 15 minutes between end of one event and start of next.
           "You have 3 minutes between 'Client Call' ending and 'Team Sync' starting."
        
        4. TRAVEL_IMPOSSIBLE (soft)
           Two events at different physical locations with insufficient travel time.
           Uses simple distance estimation: different cities = need 2+ hours,
           different addresses same city = need 30+ minutes.
        
        5. OVERLOADED_DAY (warning)
           More than 6 hours of meetings in a single day.
           "You have 7.5 hours of meetings on Wednesday. No focus time."
        """
        
        # Look ahead 14 days
        window_start = datetime.utcnow()
        window_end = window_start + timedelta(days=14)
        
        events = await self.db.get_events_in_range(
            start=window_start, end=window_end,
            exclude_cancelled=True, exclude_all_day=True,
        )
        
        new_conflicts = []
        
        # Check all pairs for overlap
        for i, event_a in enumerate(events):
            for event_b in events[i+1:]:
                # Skip if same event (recurrence instances can duplicate)
                if event_a.provider_event_id == event_b.provider_event_id:
                    continue
                
                conflict = self._check_pair_conflict(event_a, event_b)
                if conflict:
                    # Check if we already know about this conflict
                    existing = await self.db.get_conflict(event_a.id, event_b.id)
                    if not existing:
                        new_conflicts.append(conflict)
        
        # Check for overloaded days
        day_loads = self._calculate_day_loads(events)
        for day, hours in day_loads.items():
            if hours > 6:
                # Create a warning (not tied to specific event pair)
                pass
        
        # Store new conflicts and notify
        for conflict in new_conflicts:
            await self.db.store_conflict(conflict)
            await self._notify_conflict(conflict)
    
    def _check_pair_conflict(
        self, a: NormalizedEvent, b: NormalizedEvent
    ) -> CalendarConflict | None:
        """Check if two events conflict."""
        
        # Time overlap check
        overlap = a.start_time < b.end_time and b.start_time < a.end_time
        
        if overlap:
            if a.calendar_id == b.calendar_id:
                conflict_type = ConflictType.DOUBLE_BOOK
            else:
                conflict_type = ConflictType.OVERLAP
            
            return CalendarConflict(
                event_a=a,
                event_b=b,
                conflict_type=conflict_type,
                severity=ConflictSeverity.HARD,
                description=(
                    f"'{a.title}' ({a.calendar_name}) and "
                    f"'{b.title}' ({b.calendar_name}) overlap on "
                    f"{a.start_time.strftime('%A %b %d')} "
                    f"({a.start_time.strftime('%I:%M%p')}-{a.end_time.strftime('%I:%M%p')} "
                    f"vs {b.start_time.strftime('%I:%M%p')}-{b.end_time.strftime('%I:%M%p')})"
                ),
            )
        
        # Back-to-back check (within 15 minutes)
        gap_ab = (b.start_time - a.end_time).total_seconds()
        gap_ba = (a.start_time - b.end_time).total_seconds()
        
        min_gap = min(
            gap_ab if gap_ab > 0 else float('inf'),
            gap_ba if gap_ba > 0 else float('inf'),
        )
        
        if 0 < min_gap < 900:  # Less than 15 minutes
            return CalendarConflict(
                event_a=a if a.start_time < b.start_time else b,
                event_b=b if a.start_time < b.start_time else a,
                conflict_type=ConflictType.BACK_TO_BACK,
                severity=ConflictSeverity.SOFT,
                description=(
                    f"Only {int(min_gap // 60)} minutes between "
                    f"'{a.title}' ending and '{b.title}' starting."
                ),
            )
        
        # Travel check (if both have locations)
        if a.location and b.location and 0 < min_gap < 7200:
            if self._locations_need_travel_time(a.location, b.location, min_gap):
                return CalendarConflict(
                    event_a=a if a.start_time < b.start_time else b,
                    event_b=b if a.start_time < b.start_time else a,
                    conflict_type=ConflictType.TRAVEL_IMPOSSIBLE,
                    severity=ConflictSeverity.SOFT,
                    description=(
                        f"'{a.title}' at {a.location} and '{b.title}' at {b.location} "
                        f"are at different locations with only {int(min_gap // 60)} minutes between."
                    ),
                )
        
        return None
    
    def _locations_need_travel_time(self, loc_a: str, loc_b: str, gap_seconds: float) -> bool:
        """
        Simple heuristic: if locations are different strings and gap < 30 min,
        flag it. For v2, use geocoding + routing API for real travel times.
        """
        if loc_a.strip().lower() == loc_b.strip().lower():
            return False
        # Different locations with < 30 min gap
        return gap_seconds < 1800
    
    def _calculate_day_loads(self, events: list[NormalizedEvent]) -> dict[str, float]:
        """Calculate total meeting hours per day."""
        loads = {}
        for event in events:
            day = event.start_time.strftime("%Y-%m-%d")
            duration_hours = (event.end_time - event.start_time).total_seconds() / 3600
            loads[day] = loads.get(day, 0) + duration_hours
        return loads
```

### 5.2 Meeting Prep

```python
    async def prepare_upcoming_meetings(self):
        """
        For meetings in the next 24 hours, find relevant notes.
        
        This is the "second brain for meetings" feature.
        
        For each upcoming meeting, Mimir looks at:
        1. Attendees → match against entities (people) in the knowledge base
        2. Meeting title/description → semantic search against notes
        3. Previous meetings with same attendees → find follow-ups
        
        Result: a "meeting prep" packet attached to the event,
        surfaced in the daily brief and/or via messaging bridge.
        """
        
        # Get meetings in next 24 hours
        now = datetime.utcnow()
        upcoming = await self.db.get_events_in_range(
            start=now,
            end=now + timedelta(hours=24),
            exclude_cancelled=True,
            exclude_all_day=True,
        )
        
        for event in upcoming:
            # Skip if already processed recently
            if event.is_processed and (now - event.processed_at).total_seconds() < 3600:
                continue
            
            # Skip private calendar events (no content analysis)
            if event.is_private:
                continue
            
            prep_notes = []
            
            # 1. Search by attendees
            for attendee in event.attendees:
                if attendee.is_self:
                    continue
                # Find entity by email or name
                entity = await self.db.find_entity_by_email_or_name(
                    email=attendee.email, name=attendee.name
                )
                if entity:
                    # Get notes linked to this entity
                    related_notes = await self.db.get_notes_by_entity(entity.id, limit=5)
                    for note in related_notes:
                        prep_notes.append({
                            "note": note,
                            "reason": f"Related to {attendee.name or attendee.email}",
                            "link_type": "attendee",
                        })
                    # Link entity to event
                    await self.db.link_event_entity(event.id, entity.id, "attendee")
            
            # 2. Search by meeting title/description
            if event.title:
                search_query = event.title
                if event.description:
                    search_query += " " + event.description[:200]
                
                search_results = await self.search.search(query=search_query, limit=5)
                for result in search_results:
                    # Avoid duplicates from attendee search
                    if not any(p["note"].id == result.note_id for p in prep_notes):
                        prep_notes.append({
                            "note": result,
                            "reason": f"Related to meeting topic",
                            "link_type": "related",
                        })
            
            # 3. Store links and mark processed
            for prep in prep_notes[:10]:  # Cap at 10 prep notes per meeting
                await self.db.link_event_note(
                    event_id=event.id,
                    note_id=prep["note"].id,
                    link_type=prep["link_type"],
                    relevance_score=getattr(prep["note"], "score", 0.5),
                )
            
            await self.db.mark_event_processed(event.id)
```

### 5.3 Follow-Up & Deadline Tracking

```python
    async def check_follow_up_deadlines(self):
        """
        Cross-reference notes with action items against the calendar.
        
        Scenarios this catches:
        
        1. Note says "proposal due Friday" → checks if you have time
           blocked on Friday for the proposal. If not, nudges you.
        
        2. Note says "follow up with Jake next week" → checks if
           you have a meeting with Jake (by attendee match) next week.
           If not, suggests scheduling one.
        
        3. Meeting happened yesterday with Jake → surfaces notes captured
           with Jake as an entity, asks "any follow-ups from yesterday's
           meeting with Jake?"
        """
        
        # Get notes with unresolved action items
        action_notes = await self.db.get_notes_with_action_items(resolved=False)
        
        for note in action_notes:
            for action in note.action_items:
                # Use LLM to extract deadline if present
                deadline_info = await self._extract_deadline(action, note)
                
                if deadline_info and deadline_info.get("date"):
                    target_date = deadline_info["date"]
                    
                    # Check if there's time blocked for this
                    day_events = await self.db.get_events_for_day(target_date)
                    has_focus_time = any(
                        e.meeting_type == MeetingType.FOCUS or
                        (e.title and any(kw in e.title.lower() for kw in
                         action.lower().split()[:3]))
                        for e in day_events
                    )
                    
                    if not has_focus_time:
                        await self.dispatcher.send_resurface(ResurfaceItem(
                            note=note,
                            reason=(
                                f"Action item: \"{action}\" — target date is "
                                f"{target_date.strftime('%A %b %d')} but you don't "
                                f"have time blocked for it."
                            ),
                            queue_type="follow_up",
                            priority=0.8,
                        ))
        
        # Check for recent meetings needing follow-up
        yesterday_start = datetime.utcnow().replace(hour=0, minute=0) - timedelta(days=1)
        yesterday_end = yesterday_start + timedelta(days=1)
        
        yesterday_meetings = await self.db.get_events_in_range(
            start=yesterday_start, end=yesterday_end,
            exclude_cancelled=True, exclude_all_day=True,
        )
        
        for meeting in yesterday_meetings:
            if len(meeting.attendees) > 1:  # Had other people
                # Check if any notes were captured around meeting time
                meeting_notes = await self.db.get_notes_near_time(
                    time=meeting.start_time,
                    window_hours=2,
                )
                
                if not meeting_notes:
                    # No notes captured around this meeting — prompt
                    attendee_names = [a.name or a.email for a in meeting.attendees if not a.is_self]
                    await self.dispatcher.send_resurface(ResurfaceItem(
                        note=None,
                        reason=(
                            f"You met with {', '.join(attendee_names[:3])} yesterday "
                            f"(\"{meeting.title}\") but didn't capture any notes. "
                            f"Any follow-ups?"
                        ),
                        queue_type="follow_up",
                        priority=0.6,
                    ))
```

### 5.4 Time-Aware Resurfacing

```python
    async def time_aware_resurface(self):
        """
        Enhance the daily brief with calendar context.
        
        Called by the daily brief generator to add calendar-aware sections:
        
        1. TODAY'S PREP: For each meeting today, show relevant notes
        2. CONFLICTS: Any unresolved scheduling conflicts
        3. DEADLINES: Action items with deadlines this week
        4. FOCUS TIME: How much unscheduled time you have today
        5. THIS WEEK: High-level view of busy vs. free days
        """
        
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
        today_end = today_start + timedelta(days=1)
        week_end = today_start + timedelta(days=7)
        
        # Today's events with prep
        today_events = await self.db.get_events_in_range(
            start=today_start, end=today_end,
            exclude_cancelled=True,
        )
        
        meeting_preps = []
        for event in today_events:
            if event.all_day:
                continue
            linked_notes = await self.db.get_event_note_links(event.id)
            if linked_notes:
                meeting_preps.append({
                    "event": event,
                    "notes": linked_notes[:3],  # Top 3 most relevant
                })
        
        # Unresolved conflicts
        conflicts = await self.db.get_unresolved_conflicts(
            start=today_start, end=week_end,
        )
        
        # Calculate focus time
        total_meeting_minutes = sum(
            (e.end_time - e.start_time).total_seconds() / 60
            for e in today_events if not e.all_day
        )
        # Assume 10-hour day
        focus_minutes = max(0, 600 - total_meeting_minutes)
        
        # Week overview
        week_events = await self.db.get_events_in_range(
            start=today_start, end=week_end,
            exclude_cancelled=True, exclude_all_day=True,
        )
        day_loads = self._calculate_day_loads(week_events)
        
        return CalendarBriefSection(
            meeting_preps=meeting_preps,
            conflicts=conflicts,
            focus_minutes_today=focus_minutes,
            total_meetings_today=len([e for e in today_events if not e.all_day]),
            week_loads=day_loads,
        )
```

### 5.5 Availability Analysis

```python
    async def analyze_availability(self):
        """
        Understand the user's schedule patterns for smarter nudges.
        
        Tracks:
        - Typical meeting-heavy days (M-Th heavy, F light?)
        - Usual focus time blocks (mornings free? afternoons packed?)
        - Recurring patterns (every Monday has standup at 9)
        
        Used for:
        - Smarter follow-up timing: "You have a 2-hour block on Thursday
          morning — good time to work on that proposal"
        - Overcommitment warnings: "This week has 35 hours of meetings,
          20% more than your average"
        - Suggesting when to schedule focus time
        """
        
        # Analyze last 4 weeks
        now = datetime.utcnow()
        four_weeks_ago = now - timedelta(weeks=4)
        
        events = await self.db.get_events_in_range(
            start=four_weeks_ago, end=now,
            exclude_cancelled=True, exclude_all_day=True,
        )
        
        # Calculate patterns
        patterns = {
            "avg_meetings_per_day": {},       # By weekday
            "avg_meeting_hours_per_day": {},   # By weekday
            "typical_free_blocks": [],         # Common open times
            "busiest_day": None,
            "lightest_day": None,
            "avg_weekly_meeting_hours": 0,
        }
        
        # ... pattern calculation logic ...
        
        await self.db.store_setting("calendar_patterns", patterns)
        return patterns
```

---

## 6. ENHANCED DAILY BRIEF

The daily brief from the main blueprint gains a calendar section:

```
☀️ Good morning, Desmond. Here's your brief for March 4:

📅 TODAY'S SCHEDULE (4 meetings, ~3.5 hours of focus time)
  9:00  Team Standup (30 min)
  10:30 Jake — Q3 Pricing Review (1 hr)
        📎 You saved 3 notes on pricing strategy
        📎 Last week you captured a SaaS pricing article marked "relevant to Quick Convert"
  1:00  Quick Convert Partner Sync (45 min)
  3:30  Board prep — First Choice Women's Center (1 hr)

⚠️ CONFLICT: Thursday 2pm
  "Dental Lab Call" (Work) overlaps with "Caleb's Soccer Practice" (Family)
  These are on different calendars — one needs to move.

📝 RECENTLY CAPTURED: 3 notes yesterday...
🔗 CONNECTIONS: Your note about rush tier pricing links to...
⏰ DEADLINE: "Update proposal for Jake" — due Friday. No time blocked yet.

What's on your mind today?
```

---

## 7. CALENDAR API ENDPOINTS

```
# OAuth flows
GET  /api/calendar/google/auth              # Redirect to Google OAuth
GET  /api/calendar/google/callback           # OAuth callback
GET  /api/calendar/outlook/auth              # Redirect to Microsoft OAuth
GET  /api/calendar/outlook/callback           # OAuth callback

# Calendar management
GET  /api/calendar/sources                   # List all connected calendar sources
POST /api/calendar/sources                   # Add a new calendar source
DELETE /api/calendar/sources/{id}            # Disconnect a calendar source
PUT  /api/calendar/sources/{id}              # Update settings (privacy, sync, etc.)

# Calendar discovery
GET  /api/calendar/sources/{id}/calendars    # List available calendars from a source
POST /api/calendar/sources/{id}/calendars    # Select which calendars to sync

# Events
GET  /api/calendar/events?start=&end=&calendar_id=  # Get events in time range
GET  /api/calendar/events/{id}                       # Get single event with prep notes
GET  /api/calendar/events/{id}/prep                  # Get meeting prep notes for an event

# Manual actions
POST /api/calendar/sync                      # Trigger manual sync of all calendars
POST /api/calendar/events/create             # Create an event (requires write access)
  Body: { calendar_id, title, start_time, end_time, description?, location? }

# Conflicts
GET  /api/calendar/conflicts?resolved=false  # Get unresolved conflicts
POST /api/calendar/conflicts/{id}/resolve    # Mark a conflict as resolved

# Intelligence
GET  /api/calendar/availability?date=        # Get availability for a specific day
GET  /api/calendar/patterns                  # Get schedule pattern analysis
GET  /api/calendar/today                     # Today's enriched schedule with prep
GET  /api/calendar/week                      # This week overview with load analysis
```

---

## 8. CALENDAR SETTINGS UI

### 8.1 Settings Page Section: "Calendars"

```
┌─────────────────────────────────────────────────────────────────┐
│  Calendar Connections                                            │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Google Calendar                              [Connected ●] │ │
│  │  Account: desmond@gmail.com                                 │ │
│  │  Syncing 4 of 6 calendars:                                  │ │
│  │    ✓ Work Calendar          🔓 Full access                  │ │
│  │    ✓ Personal               🔒 Time only (private)          │ │
│  │    ✓ Family Shared          🔓 Full access                  │ │
│  │    ✓ Church Events          🔓 Full access                  │ │
│  │    ○ Birthdays              (not synced)                    │ │
│  │    ○ Holidays               (not synced)                    │ │
│  │  Last sync: 2 minutes ago                                   │ │
│  │  [Manage Calendars] [Sync Now] [Disconnect]                 │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Apple Calendar (iCloud)                      [Connected ●] │ │
│  │  Account: desmond@icloud.com                                │ │
│  │  Syncing 2 calendars                                        │ │
│  │  Last sync: 5 minutes ago                                   │ │
│  │  [Manage Calendars] [Sync Now] [Disconnect]                 │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  ICS Feed: Kids' School Calendar              [Connected ●] │ │
│  │  URL: https://school.example.com/calendar.ics               │ │
│  │  Last sync: 28 minutes ago                                  │ │
│  │  [Edit] [Sync Now] [Remove]                                 │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  [+ Connect Google Calendar]                                     │
│  [+ Connect Apple / CalDAV Calendar]                             │
│  [+ Connect Outlook / Office 365]                                │
│  [+ Add ICS Feed URL]                                            │
│                                                                  │
│  ─────────────────────────────────────────────────────────────── │
│                                                                  │
│  Calendar Intelligence:                                          │
│  ✓ Conflict detection              [ON]                         │
│  ✓ Meeting prep (surface notes)    [ON]                         │
│  ✓ Follow-up tracking              [ON]                         │
│  ✓ Overloaded day warnings         [ON]                         │
│  ○ Auto-create focus blocks        [OFF]                        │
│                                                                  │
│  Back-to-back threshold:   [15] minutes                         │
│  Overloaded day threshold: [6] hours of meetings                │
│  Meeting prep lookahead:   [24] hours                           │
│  Conflict scan lookahead:  [14] days                            │
│                                                                  │
│  [Save Settings]                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Dashboard Calendar Widget

```
┌─────────────────────────────────────────────────────────────────┐
│  Today — Wednesday, March 4                                      │
│                                                                  │
│  ┌── 9:00 ──────────────────────────────────────────────────┐   │
│  │  Team Standup                          Work Calendar  30m │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌── 10:30 ─────────────────────────────────────────────────┐   │
│  │  Jake — Q3 Pricing Review              Work Calendar  1hr │   │
│  │  📎 3 prep notes available                          [View] │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ── 11:30 - 1:00  FOCUS TIME (1.5 hrs) ──                      │
│                                                                  │
│  ┌── 1:00 ──────────────────────────────────────────────────┐   │
│  │  Quick Convert Partner Sync            Work Calendar  45m │   │
│  │  📎 1 prep note available                           [View] │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ── 1:45 - 3:30  FOCUS TIME (1.75 hrs) ──                      │
│                                                                  │
│  ┌── 3:30 ──────────────────────────────────────────────────┐   │
│  │  Board Prep — FCWC                     Church Calendar 1hr│   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ⚠️ 1 conflict this week                              [Review] │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. MESSAGING BRIDGE INTEGRATION

Calendar intelligence sends notifications through the existing messaging bridge:

```python
async def _notify_conflict(self, conflict: CalendarConflict):
    """Send conflict alert through messaging bridge."""
    
    text = (
        f"⚠️ Calendar Conflict\n\n"
        f"*{conflict.event_a.title}* ({conflict.event_a.calendar_name})\n"
        f"{conflict.event_a.start_time.strftime('%a %b %d %I:%M%p')} - "
        f"{conflict.event_a.end_time.strftime('%I:%M%p')}\n\n"
        f"conflicts with\n\n"
        f"*{conflict.event_b.title}* ({conflict.event_b.calendar_name})\n"
        f"{conflict.event_b.start_time.strftime('%a %b %d %I:%M%p')} - "
        f"{conflict.event_b.end_time.strftime('%I:%M%p')}\n\n"
        f"{conflict.description}"
    )
    
    await self.dispatcher.send_by_type("connection_alert", text)
```

**Bridge commands gain calendar access:**

```
New commands:
  /today             → Today's schedule with prep notes
  /week              → This week's overview
  /conflicts         → Unresolved calendar conflicts
  /free tomorrow     → Available time slots tomorrow
```

---

## 10. UPDATED DIRECTORY STRUCTURE

```
backend/src/
├── calendar/
│   ├── __init__.py
│   ├── models.py                 # NormalizedEvent, CalendarConflict, etc.
│   ├── sync_engine.py            # CalendarSyncEngine
│   ├── intelligence.py           # CalendarIntelligence (conflicts, prep, follow-up)
│   ├── router.py                 # FastAPI routes for calendar API
│   └── adapters/
│       ├── __init__.py
│       ├── base.py               # CalendarAdapter ABC, SyncResult
│       ├── google_calendar.py    # Google Calendar API v3
│       ├── caldav_adapter.py     # CalDAV (Apple, Fastmail, Nextcloud)
│       ├── outlook.py            # Microsoft Graph API
│       └── ics_feed.py           # Read-only ICS URL feeds
├── ...rest of backend unchanged
```

---

## 11. ENVIRONMENT VARIABLES

Add to `.env.example`:

```env
# Google Calendar OAuth
GOOGLE_CALENDAR_CLIENT_ID=
GOOGLE_CALENDAR_CLIENT_SECRET=

# Microsoft Outlook OAuth (optional)
OUTLOOK_CLIENT_ID=
OUTLOOK_CLIENT_SECRET=

# CalDAV / Apple Calendar (optional)
CALDAV_SERVER_URL=
CALDAV_USERNAME=
CALDAV_PASSWORD=

# Calendar Intelligence
CALENDAR_SYNC_INTERVAL=300              # seconds (default 5 min)
CALENDAR_CONFLICT_LOOKAHEAD_DAYS=14
CALENDAR_PREP_LOOKAHEAD_HOURS=24
CALENDAR_BACK_TO_BACK_THRESHOLD_MIN=15
CALENDAR_OVERLOADED_THRESHOLD_HOURS=6
```

---

## 12. IMPLEMENTATION PRIORITY

The calendar integration fits into **Phase 2 (Agent Intelligence)** of the main blueprint, since it's fundamentally an agent behavior — proactive analysis, not passive storage.

**Step 1: Google Calendar adapter + sync engine.** Most common calendar. OAuth flow, incremental sync, event store. Get events flowing into SQLite.

**Step 2: Conflict detection.** This is the immediate-value feature. Multi-calendar users get value from day one.

**Step 3: Meeting prep.** Connect events to notes via attendee/topic matching. This is where calendar meets second brain.

**Step 4: Daily brief integration.** Add calendar section to existing daily brief.

**Step 5: Bridge commands.** `/today`, `/conflicts`, `/free` in Telegram/WhatsApp.

**Step 6: CalDAV adapter.** Covers Apple Calendar and self-hosted solutions.

**Step 7: Follow-up tracking.** Cross-reference action items with calendar.

**Step 8: ICS feeds + Outlook.** Extended coverage.

**Step 9: Availability analysis.** Pattern detection over time.

---

## 13. PRIVACY CONSIDERATIONS

- **Calendar data stays local.** Events are synced to SQLite on your server. Never sent to third parties.
- **Private calendars.** Mark any calendar as "private" — Mimir sees time blocks only, no titles, descriptions, or attendees. Useful for medical, personal, or sensitive calendars. Conflicts are still detected (time overlap), but meeting prep is skipped.
- **OAuth tokens encrypted at rest.** Google/Outlook refresh tokens stored with AES encryption in the settings DB.
- **Minimal scopes.** Request read-only access by default. Write access (for creating focus blocks) is optional and explicitly requested.
- **No attendee data leaves the system.** Attendee emails are used only for entity matching within your own knowledge base. Never shared externally.

---

*This addendum should be read alongside the main Mimir blueprint, the AI Harness addendum, and the Messaging Bridge addendum. Feed all four documents to Claude Code together.*
