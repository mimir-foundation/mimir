"""Resurface engine — 5 trigger types that proactively surface old knowledge."""

import json
import logging
from datetime import datetime, timedelta

from src.knowledge import database as db
from src.knowledge.models import new_id

logger = logging.getLogger("mimir.agent.resurface")

SPACED_REP_INTERVALS = [1, 3, 7, 14, 30, 60, 90]


async def check_resurface_triggers(note_id: str) -> list[dict]:
    """Run all 5 resurface triggers after a note is processed. Returns created items."""
    items = []
    items.extend(await _check_strong_connections(note_id))
    items.extend(await _check_concept_cluster(note_id))
    items.extend(await _check_entity_recurrence(note_id))
    # Spaced rep and follow-up are checked on schedule, not per-note
    return items


async def run_scheduled_resurface() -> list[dict]:
    """Scheduled job: check spaced repetition and follow-up triggers."""
    items = []
    items.extend(await _check_spaced_repetition())
    items.extend(await _check_follow_ups())
    return items


# --- Trigger 1: Strong Connection ---

async def _check_strong_connections(note_id: str) -> list[dict]:
    """Surface old notes that have a strong connection (>0.8) to the new note."""
    connections = await db.fetch_all(
        """SELECT c.id, c.target_note_id, c.strength, c.explanation, n.title
           FROM connections c
           JOIN notes n ON n.id = c.target_note_id
           WHERE c.source_note_id = ? AND c.strength > 0.8 AND c.surfaced = 0""",
        (note_id,),
    )

    items = []
    for conn in connections:
        item = await _queue_resurface(
            queue_type="connection_alert",
            note_id=conn["target_note_id"],
            connection_id=conn["id"],
            reason=f"This relates to something you just saved — {conn['explanation'] or 'strong connection found'}",
            priority=conn["strength"],
        )
        if item:
            items.append(item)
            await db.execute("UPDATE connections SET surfaced = 1 WHERE id = ?", (conn["id"],))

    # Also check reverse direction
    connections_rev = await db.fetch_all(
        """SELECT c.id, c.source_note_id, c.strength, c.explanation, n.title
           FROM connections c
           JOIN notes n ON n.id = c.source_note_id
           WHERE c.target_note_id = ? AND c.strength > 0.8 AND c.surfaced = 0""",
        (note_id,),
    )
    for conn in connections_rev:
        item = await _queue_resurface(
            queue_type="connection_alert",
            note_id=conn["source_note_id"],
            connection_id=conn["id"],
            reason=f"This relates to something you just saved — {conn['explanation'] or 'strong connection found'}",
            priority=conn["strength"],
        )
        if item:
            items.append(item)
            await db.execute("UPDATE connections SET surfaced = 1 WHERE id = ?", (conn["id"],))

    return items


# --- Trigger 2: Concept Cluster ---

async def _check_concept_cluster(note_id: str) -> list[dict]:
    """Surface a concept cluster when a concept crosses the threshold (5 notes)."""
    # Get concepts for this note
    note_concepts = await db.fetch_all(
        """SELECT c.id, c.name, c.note_count
           FROM concepts c
           JOIN note_concepts nc ON c.id = nc.concept_id
           WHERE nc.note_id = ?""",
        (note_id,),
    )

    items = []
    for concept in note_concepts:
        # Trigger at exactly 5, 10, 20, 50 notes
        count = concept["note_count"]
        if count in (5, 10, 20, 50):
            # Check we haven't already surfaced for this threshold
            existing = await db.fetch_one(
                """SELECT id FROM resurface_queue
                   WHERE queue_type = 'concept_cluster' AND reason LIKE ?
                   AND created_at > ?""",
                (f"%{concept['name']}%{count} notes%",
                 (datetime.utcnow() - timedelta(days=1)).isoformat()),
            )
            if existing:
                continue

            item = await _queue_resurface(
                queue_type="concept_cluster",
                note_id=note_id,
                reason=f"You keep coming back to \"{concept['name']}\" — {count} notes now. Here's everything you've captured on this topic.",
                priority=min(0.9, 0.5 + count * 0.01),
            )
            if item:
                items.append(item)

    return items


# --- Trigger 3: Entity Recurrence ---

async def _check_entity_recurrence(note_id: str) -> list[dict]:
    """Surface old notes when the same entity reappears after 30+ days."""
    # Get entities for this note
    note_entities = await db.fetch_all(
        """SELECT e.id, e.name, e.entity_type
           FROM entities e
           JOIN note_entities ne ON e.id = ne.entity_id
           WHERE ne.note_id = ?""",
        (note_id,),
    )

    items = []
    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()

    for entity in note_entities:
        # Find old notes (30+ days) mentioning the same entity
        old_notes = await db.fetch_all(
            """SELECT n.id, n.title, n.created_at
               FROM notes n
               JOIN note_entities ne ON n.id = ne.note_id
               WHERE ne.entity_id = ? AND n.id != ? AND n.created_at < ?
               ORDER BY n.created_at DESC
               LIMIT 3""",
            (entity["id"], note_id, cutoff),
        )

        for old_note in old_notes:
            # Don't re-surface within 7 days
            already = await db.fetch_one(
                """SELECT id FROM resurface_queue
                   WHERE note_id = ? AND queue_type = 'entity_recurrence'
                   AND created_at > ?""",
                (old_note["id"], (datetime.utcnow() - timedelta(days=7)).isoformat()),
            )
            if already:
                continue

            item = await _queue_resurface(
                queue_type="entity_recurrence",
                note_id=old_note["id"],
                reason=f"You encountered \"{entity['name']}\" again — you last noted about them on {old_note['created_at'][:10]}",
                priority=0.6,
            )
            if item:
                items.append(item)

    return items


# --- Trigger 4: Spaced Repetition ---

async def _check_spaced_repetition() -> list[dict]:
    """Surface starred notes on increasing intervals."""
    starred = await db.fetch_all(
        "SELECT id, title, created_at FROM notes WHERE is_starred = 1 AND is_archived = 0"
    )

    items = []
    now = datetime.utcnow()

    for note in starred:
        created = datetime.fromisoformat(note["created_at"])
        age_days = (now - created).days

        # Find which interval we're at
        for interval in SPACED_REP_INTERVALS:
            # Check if we're within 1 day of an interval
            if abs(age_days - interval) <= 1:
                # Check if already surfaced for this interval
                already = await db.fetch_one(
                    """SELECT id FROM resurface_queue
                       WHERE note_id = ? AND queue_type = 'spaced_rep'
                       AND reason LIKE ?""",
                    (note["id"], f"%{interval} day%"),
                )
                if already:
                    continue

                item = await _queue_resurface(
                    queue_type="spaced_rep",
                    note_id=note["id"],
                    reason=f"Revisit ({interval}-day review): {note['title'] or 'Untitled'}",
                    priority=0.7,
                    scheduled_for=now.isoformat(),
                )
                if item:
                    items.append(item)
                break

    return items


# --- Trigger 5: Follow-up ---

async def _check_follow_ups() -> list[dict]:
    """Surface notes with action items that haven't been revisited in 7+ days."""
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()

    # Find notes with action items in their extraction (stored in agent_log)
    # We look for notes that were processed 7+ days ago and have action items
    notes_with_actions = await db.fetch_all(
        """SELECT al.details, al.started_at
           FROM agent_log al
           WHERE al.action_type = 'extract_actions'
           AND al.started_at < ?
           AND al.status = 'complete'
           ORDER BY al.started_at DESC
           LIMIT 50""",
        (cutoff,),
    )

    # Also check: notes processed 7+ days ago that user hasn't viewed
    old_unviewed = await db.fetch_all(
        """SELECT n.id, n.title, n.processed_at
           FROM notes n
           WHERE n.processing_status = 'complete'
           AND n.processed_at < ?
           AND n.is_archived = 0
           AND n.id NOT IN (
               SELECT note_id FROM interest_signals
               WHERE signal_type = 'view' AND note_id IS NOT NULL
               AND created_at > ?
           )
           ORDER BY n.processed_at DESC
           LIMIT 10""",
        (cutoff, cutoff),
    )

    items = []
    for note in old_unviewed:
        # Only resurface if not already queued recently
        already = await db.fetch_one(
            """SELECT id FROM resurface_queue
               WHERE note_id = ? AND queue_type = 'follow_up'
               AND created_at > ?""",
            (note["id"], (datetime.utcnow() - timedelta(days=14)).isoformat()),
        )
        if already:
            continue

        item = await _queue_resurface(
            queue_type="follow_up",
            note_id=note["id"],
            reason=f"Still on your mind? You saved \"{note['title'] or 'Untitled'}\" but haven't revisited it.",
            priority=0.4,
        )
        if item:
            items.append(item)

    return items


# --- Helpers ---

async def _queue_resurface(
    queue_type: str,
    note_id: str,
    reason: str,
    priority: float = 0.5,
    connection_id: str | None = None,
    scheduled_for: str | None = None,
) -> dict | None:
    """Add an item to the resurface queue."""
    item_id = new_id()
    try:
        await db.execute(
            """INSERT INTO resurface_queue
               (id, queue_type, note_id, connection_id, reason, priority, scheduled_for)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (item_id, queue_type, note_id, connection_id, reason, priority, scheduled_for),
        )
        logger.info(f"Queued resurface [{queue_type}]: {reason[:80]}")
        return {
            "id": item_id,
            "queue_type": queue_type,
            "note_id": note_id,
            "reason": reason,
            "priority": priority,
        }
    except Exception as e:
        logger.warning(f"Failed to queue resurface: {e}")
        return None


async def get_pending_items(limit: int = 10) -> list[dict]:
    """Get undelivered resurface items, ordered by priority."""
    return await db.fetch_all(
        """SELECT rq.*, n.title as note_title
           FROM resurface_queue rq
           JOIN notes n ON n.id = rq.note_id
           WHERE rq.delivered = 0 AND rq.dismissed = 0
           AND (rq.scheduled_for IS NULL OR rq.scheduled_for <= ?)
           ORDER BY rq.priority DESC, rq.created_at DESC
           LIMIT ?""",
        (datetime.utcnow().isoformat(), limit),
    )


async def mark_delivered(item_id: str) -> None:
    await db.execute("UPDATE resurface_queue SET delivered = 1 WHERE id = ?", (item_id,))


async def mark_clicked(item_id: str) -> None:
    await db.execute("UPDATE resurface_queue SET clicked = 1 WHERE id = ?", (item_id,))


async def mark_dismissed(item_id: str) -> None:
    await db.execute("UPDATE resurface_queue SET dismissed = 1 WHERE id = ?", (item_id,))


async def prune_stale(days: int = 30) -> int:
    """Remove old delivered or dismissed resurface items."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    cursor = await db.execute(
        """DELETE FROM resurface_queue
           WHERE (delivered = 1 OR dismissed = 1) AND created_at < ?""",
        (cutoff,),
    )
    return cursor.rowcount
