"""Agent runtime — scheduled and event-driven behaviors."""

import json
import logging
from datetime import datetime

from src.knowledge import database as db
from src.knowledge.models import new_id

logger = logging.getLogger("mimir.agent.runtime")


# --- Scheduled Jobs ---

async def job_deep_scan(app) -> None:
    """Every 6 hours: deep scan for connections."""
    logger.info("Starting connection deep scan...")
    from src.agent.connection_finder import deep_scan
    result = await deep_scan(app.state.harness, app.state.vector_store)
    logger.info(f"Deep scan result: {result}")


async def job_generate_brief(app) -> None:
    """Daily: generate the morning brief."""
    logger.info("Generating daily brief...")
    from src.agent.daily_brief import generate_brief
    brief = await generate_brief(app.state.harness)

    if brief:
        # Send via webhook if configured
        from src.agent.notifications import send_brief_notification
        await send_brief_notification(brief["content"])

        # Send via messaging bridge
        try:
            from src.bridge.dispatcher import get_dispatcher
            dispatcher = get_dispatcher()
            if dispatcher:
                await dispatcher.send_daily_brief(brief["content"])
        except Exception as e:
            logger.warning(f"Bridge brief delivery failed: {e}")


async def job_scheduled_resurface(app) -> None:
    """Every 4 hours: check spaced repetition and follow-up triggers."""
    logger.info("Running scheduled resurface checks...")
    from src.agent.resurface import run_scheduled_resurface
    items = await run_scheduled_resurface()
    if items:
        logger.info(f"Scheduled resurface: {len(items)} items queued")


async def job_prune_stale(app) -> None:
    """Weekly: clean up old resurface items and signals."""
    logger.info("Pruning stale items...")
    from src.agent.resurface import prune_stale
    from src.agent.signals import prune_old_signals

    pruned_resurface = await prune_stale(days=30)
    pruned_signals = await prune_old_signals(days=90)
    logger.info(f"Pruned {pruned_resurface} resurface items, {pruned_signals} signals")


async def job_rebuild_taxonomy(app) -> None:
    """Weekly: reorganize concept hierarchy."""
    logger.info("Rebuilding taxonomy...")
    from src.agent.taxonomy import rebuild_taxonomy
    result = await rebuild_taxonomy(app.state.harness, app.state.vector_store)
    logger.info(f"Taxonomy rebuild result: {result}")


async def job_send_digest(app) -> None:
    """Weekly: send digest email if SMTP is configured."""
    logger.info("Sending weekly digest...")
    from src.agent.digest import send_digest
    ok = await send_digest()
    logger.info(f"Weekly digest {'sent' if ok else 'skipped/failed'}")


# --- Event Handlers ---

async def on_note_processed(note_id: str) -> None:
    """Called after a note completes processing. Triggers resurface checks."""
    try:
        from src.agent.resurface import check_resurface_triggers
        items = await check_resurface_triggers(note_id)
        if items:
            logger.info(f"Note {note_id} triggered {len(items)} resurface items")

            # Send high-priority items via webhook
            for item in items:
                if item.get("priority", 0) > 0.8:
                    from src.agent.notifications import send_resurface_notification
                    note = await db.fetch_one("SELECT title FROM notes WHERE id = ?", (item["note_id"],))
                    if note:
                        await send_resurface_notification(item["reason"], note["title"] or "Untitled")

                        # Also send via messaging bridge
                        try:
                            from src.bridge.dispatcher import get_dispatcher
                            dispatcher = get_dispatcher()
                            if dispatcher:
                                await dispatcher.send_resurface(note["title"] or "Untitled", item["reason"], "")
                        except Exception as e:
                            logger.warning(f"Bridge resurface failed: {e}")

        # Log interest signal for the capture
        from src.agent.signals import log_signal
        note = await db.fetch_one("SELECT source_type FROM notes WHERE id = ?", (note_id,))
        if note:
            # Get concepts for this note
            concepts = await db.fetch_all(
                """SELECT c.name FROM concepts c
                   JOIN note_concepts nc ON c.id = nc.concept_id
                   WHERE nc.note_id = ?""",
                (note_id,),
            )
            for c in concepts:
                await log_signal("capture", note_id=note_id, concept=c["name"])

    except Exception as e:
        logger.error(f"on_note_processed failed for {note_id}: {e}")


async def on_note_viewed(note_id: str) -> None:
    """Called when a user views a note. Logs interest signal."""
    try:
        from src.agent.signals import log_signal
        await log_signal("view", note_id=note_id)

        # Also log concepts
        concepts = await db.fetch_all(
            """SELECT c.name FROM concepts c
               JOIN note_concepts nc ON c.id = nc.concept_id
               WHERE nc.note_id = ?""",
            (note_id,),
        )
        for c in concepts:
            await log_signal("view", note_id=note_id, concept=c["name"], weight=0.5)

    except Exception as e:
        logger.error(f"on_note_viewed failed for {note_id}: {e}")


async def on_search(query: str) -> None:
    """Called when a user searches. Logs interest signal."""
    try:
        from src.agent.signals import log_signal
        await log_signal("search", query=query)

        # Try to match query words to concepts
        words = [w.lower().strip() for w in query.split() if len(w) > 2]
        if words:
            placeholders = ",".join("?" * len(words))
            concepts = await db.fetch_all(
                f"SELECT name FROM concepts WHERE name IN ({placeholders})",
                tuple(words),
            )
            for c in concepts:
                await log_signal("search", query=query, concept=c["name"], weight=0.8)

    except Exception as e:
        logger.error(f"on_search failed: {e}")


async def on_note_starred(note_id: str, starred: bool) -> None:
    """Called when a user stars/unstars a note."""
    try:
        from src.agent.signals import log_signal
        signal_type = "star" if starred else "unstar"
        weight = 2.0 if starred else -1.0
        await log_signal(signal_type, note_id=note_id, weight=weight)
    except Exception as e:
        logger.error(f"on_note_starred failed: {e}")


def register_agent_jobs(scheduler, app) -> None:
    """Register all Phase 2 agent jobs with the scheduler."""
    from src.config import get_settings
    settings = get_settings()

    # Parse brief time
    try:
        hour, minute = settings.brief_time.split(":")
        brief_hour = int(hour)
        brief_minute = int(minute)
    except (ValueError, AttributeError):
        brief_hour = 7
        brief_minute = 0

    # Connection deep scan: every 6 hours
    scheduler.add_job(
        job_deep_scan, "interval", hours=6, args=[app],
        id="deep_scan", max_instances=1, coalesce=True,
    )

    # Daily brief: once per day at configured time
    scheduler.add_job(
        job_generate_brief, "cron", hour=brief_hour, minute=brief_minute, args=[app],
        id="daily_brief", max_instances=1, coalesce=True,
    )

    # Scheduled resurface checks: every 4 hours
    scheduler.add_job(
        job_scheduled_resurface, "interval", hours=4, args=[app],
        id="scheduled_resurface", max_instances=1, coalesce=True,
    )

    # Prune stale: weekly (Sundays at 3 AM)
    scheduler.add_job(
        job_prune_stale, "cron", day_of_week="sun", hour=3, args=[app],
        id="prune_stale", max_instances=1, coalesce=True,
    )

    # Rebuild taxonomy: weekly (Sundays at 4 AM)
    scheduler.add_job(
        job_rebuild_taxonomy, "cron", day_of_week="sun", hour=4, args=[app],
        id="rebuild_taxonomy", max_instances=1, coalesce=True,
    )

    # Weekly digest email (only if SMTP configured)
    if settings.smtp_host and settings.smtp_recipient:
        day_map = {"monday": "mon", "tuesday": "tue", "wednesday": "wed",
                    "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun"}
        digest_dow = day_map.get(settings.digest_day.lower(), "mon")
        scheduler.add_job(
            job_send_digest, "cron", day_of_week=digest_dow, hour=settings.digest_hour,
            args=[app], id="weekly_digest", max_instances=1, coalesce=True,
        )
        logger.info(f"Weekly digest scheduled: {settings.digest_day} at {settings.digest_hour:02d}:00")

    logger.info(f"Agent jobs registered (brief at {brief_hour:02d}:{brief_minute:02d})")
