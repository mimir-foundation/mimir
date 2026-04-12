"""Dispatch stage — detect actionable content and execute actions."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from src.knowledge import database as db
from src.knowledge.models import ActionExtraction, ExtractionResult, new_id

logger = logging.getLogger("mimir.processing.dispatcher")


async def dispatch_actions(
    note_id: str, extraction: ExtractionResult, harness=None,
) -> int:
    """Process extracted actions: store them and auto-dispatch safe ones.

    Returns the number of actions created.
    """
    if not extraction.actions:
        return 0

    count = 0
    for action in extraction.actions:
        if not action.title:
            continue

        action_id = new_id()
        payload = action.model_dump(exclude_none=True)

        # Recurring events require confirmation — save as pending
        # One-off events auto-dispatch
        if action.recurring:
            status = "pending_confirmation"
            expires = (datetime.utcnow() + timedelta(hours=48)).isoformat()
        else:
            status = "pending"
            expires = None

        await db.execute(
            """INSERT INTO note_actions (id, note_id, action_type, payload, status, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (action_id, note_id, action.action_type, json.dumps(payload), status, expires),
        )
        count += 1
        logger.info(f"[{note_id}] Action created: {action.action_type} — {action.title} ({status})")

    # Auto-dispatch non-recurring actions
    pending = await db.fetch_all(
        "SELECT * FROM note_actions WHERE note_id = ? AND status = 'pending'",
        (note_id,),
    )
    for row in pending:
        try:
            payload = json.loads(row["payload"])
            await _execute_action(row["id"], row["action_type"], payload, note_id)
        except Exception as e:
            logger.error(f"Action dispatch failed {row['id']}: {e}")
            await db.execute(
                "UPDATE note_actions SET status = 'failed' WHERE id = ?",
                (row["id"],),
            )

    # Notify about pending confirmations
    confirmations = await db.fetch_all(
        "SELECT * FROM note_actions WHERE note_id = ? AND status = 'pending_confirmation'",
        (note_id,),
    )
    for row in confirmations:
        try:
            payload = json.loads(row["payload"])
            await _notify_confirmation_needed(row["id"], row["action_type"], payload)
        except Exception as e:
            logger.warning(f"Confirmation notification failed {row['id']}: {e}")

    return count


async def _execute_action(
    action_id: str, action_type: str, payload: dict, note_id: str,
) -> None:
    """Execute a single action."""

    if action_type == "calendar_event":
        ics_content = generate_ics(payload)
        # Store the .ics file alongside the note
        from src.config import get_settings
        from src.knowledge.document_store import DocumentStore

        settings = get_settings()
        doc_store = DocumentStore(settings.documents_path)
        safe_title = (payload.get("title", "event") or "event").replace("/", "-")[:50]
        filename = f"{safe_title}.ics"
        doc_store.store_document(note_id, ics_content.encode("utf-8"), filename)

        # Send via Telegram
        await _send_ics_via_bridge(payload, ics_content, filename)

        await db.execute(
            "UPDATE note_actions SET status = 'dispatched', dispatched_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), action_id),
        )

    elif action_type == "reminder":
        # Queue a resurface item for the due date
        due = payload.get("due_date") or payload.get("start")
        if due:
            from src.knowledge.models import new_id as rid
            await db.execute(
                """INSERT INTO resurface_queue (id, queue_type, note_id, reason, priority, scheduled_for)
                   VALUES (?, 'follow_up', ?, ?, 0.9, ?)""",
                (rid(), note_id, f"Reminder: {payload.get('title', '')}", due),
            )
        await db.execute(
            "UPDATE note_actions SET status = 'dispatched', dispatched_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), action_id),
        )

    elif action_type == "task":
        # For now, tasks are tracked as action items on the note
        # Future: dedicated task management
        await db.execute(
            "UPDATE note_actions SET status = 'dispatched', dispatched_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), action_id),
        )

    elif action_type == "follow_up":
        due = payload.get("due_date") or payload.get("start")
        if due:
            from src.knowledge.models import new_id as rid
            await db.execute(
                """INSERT INTO resurface_queue (id, queue_type, note_id, reason, priority, scheduled_for)
                   VALUES (?, 'follow_up', ?, ?, 0.8, ?)""",
                (rid(), note_id, f"Follow up: {payload.get('title', '')}", due),
            )
        await db.execute(
            "UPDATE note_actions SET status = 'dispatched', dispatched_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), action_id),
        )

    else:
        logger.info(f"Action type '{action_type}' not yet implemented, marking dispatched")
        await db.execute(
            "UPDATE note_actions SET status = 'dispatched', dispatched_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), action_id),
        )


async def confirm_action(action_id: str) -> Optional[str]:
    """Confirm a pending action and execute it. Returns a status message."""
    row = await db.fetch_one(
        "SELECT * FROM note_actions WHERE id = ? AND status = 'pending_confirmation'",
        (action_id,),
    )
    if not row:
        return None

    payload = json.loads(row["payload"])
    await db.execute("UPDATE note_actions SET status = 'pending' WHERE id = ?", (action_id,))

    try:
        await _execute_action(action_id, row["action_type"], payload, row["note_id"])
        return f"Confirmed: {payload.get('title', 'action')}"
    except Exception as e:
        logger.error(f"Confirmed action failed {action_id}: {e}")
        await db.execute("UPDATE note_actions SET status = 'failed' WHERE id = ?", (action_id,))
        return f"Failed: {e}"


async def skip_action(action_id: str) -> Optional[str]:
    """Skip a pending action. Returns a status message."""
    row = await db.fetch_one(
        "SELECT * FROM note_actions WHERE id = ? AND status = 'pending_confirmation'",
        (action_id,),
    )
    if not row:
        return None

    payload = json.loads(row["payload"])
    await db.execute(
        "UPDATE note_actions SET status = 'skipped', dispatched_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), action_id),
    )
    return f"Skipped: {payload.get('title', 'action')}"


# --- ICS Generation ---

def generate_ics(event: dict) -> str:
    """Generate an ICS calendar file from event data."""
    uid = new_id()
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    title = _ics_escape(event.get("title", "Event"))
    description = _ics_escape(event.get("description", ""))
    location = _ics_escape(event.get("location", ""))

    dtstart = _to_ics_datetime(event.get("start"))
    dtend = _to_ics_datetime(event.get("end"))

    # If no end time, default to 1 hour after start
    if dtstart and not dtend:
        try:
            start_dt = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
            end_dt = start_dt + timedelta(hours=1)
            dtend = end_dt.strftime("%Y%m%dT%H%M%S")
        except (ValueError, KeyError):
            dtend = dtstart

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Mimir//Second Brain//EN",
        "BEGIN:VEVENT",
        f"UID:{uid}@mimir",
        f"DTSTAMP:{now}",
    ]

    if dtstart:
        lines.append(f"DTSTART:{dtstart}")
    if dtend:
        lines.append(f"DTEND:{dtend}")

    lines.append(f"SUMMARY:{title}")

    if description:
        lines.append(f"DESCRIPTION:{description}")
    if location:
        lines.append(f"LOCATION:{location}")

    # Recurring rule
    rrule = event.get("recurring")
    if rrule:
        freq_map = {
            "daily": "FREQ=DAILY",
            "weekly": "FREQ=WEEKLY",
            "monthly": "FREQ=MONTHLY",
            "yearly": "FREQ=YEARLY",
        }
        if rrule.upper().startswith("RRULE:"):
            lines.append(rrule)
        elif rrule.lower() in freq_map:
            lines.append(f"RRULE:{freq_map[rrule.lower()]}")

    lines.extend([
        "END:VEVENT",
        "END:VCALENDAR",
    ])

    return "\r\n".join(lines) + "\r\n"


def _to_ics_datetime(iso_str: Optional[str]) -> Optional[str]:
    """Convert ISO 8601 string to ICS datetime format."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y%m%dT%H%M%S")
    except (ValueError, TypeError):
        return None


def _ics_escape(text: str) -> str:
    """Escape special characters for ICS format."""
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


# --- Bridge notifications ---

async def _send_ics_via_bridge(event: dict, ics_content: str, filename: str) -> None:
    """Send the ICS file and a summary via the messaging bridge."""
    try:
        from src.bridge.dispatcher import get_dispatcher
        dispatcher = get_dispatcher()
        if not dispatcher:
            return

        title = event.get("title", "Event")
        start = event.get("start", "")
        location = event.get("location", "")
        loc_text = f"\nLocation: {location}" if location else ""

        text = f"📅 **New event found**\n\n**{title}**\nDate: {start}{loc_text}"

        # Send text notification
        targets = await dispatcher._get_targets("daily_brief")  # reuse existing targets
        for platform, recipient_id in targets:
            adapter = dispatcher._adapters.get(platform)
            if not adapter:
                continue

            from src.bridge.models import OutboundMessage
            msg = OutboundMessage(platform=platform, recipient_id=recipient_id, text=text)
            await adapter.send(msg)

            # Send the .ics file
            if hasattr(adapter, "send_document"):
                await adapter.send_document(
                    recipient_id=recipient_id,
                    file_bytes=ics_content.encode("utf-8"),
                    filename=filename,
                    caption=f"Import this to add '{title}' to your calendar",
                )
    except Exception as e:
        logger.warning(f"Bridge ICS notification failed: {e}")


async def _notify_confirmation_needed(
    action_id: str, action_type: str, payload: dict,
) -> None:
    """Notify the user that an action needs confirmation."""
    try:
        from src.bridge.dispatcher import get_dispatcher
        dispatcher = get_dispatcher()
        if not dispatcher:
            return

        title = payload.get("title", "Action")
        recurring = payload.get("recurring", "")
        start = payload.get("start", "")

        text = (
            f"🔄 **Recurring event detected**\n\n"
            f"**{title}**\n"
            f"Schedule: {recurring}\n"
            f"Starting: {start}\n\n"
            f"Reply `/confirm {action_id[:8]}` to add to calendar\n"
            f"Reply `/skip {action_id[:8]}` to ignore"
        )

        targets = await dispatcher._get_targets("daily_brief")
        for platform, recipient_id in targets:
            adapter = dispatcher._adapters.get(platform)
            if not adapter:
                continue
            from src.bridge.models import OutboundMessage
            msg = OutboundMessage(platform=platform, recipient_id=recipient_id, text=text)
            await adapter.send(msg)
    except Exception as e:
        logger.warning(f"Confirmation notification failed: {e}")
