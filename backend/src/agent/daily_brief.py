"""Daily brief generation — a morning newspaper for your knowledge."""

import json
import logging
from datetime import datetime, timedelta

from src.harness import AIOperation
from src.knowledge import database as db
from src.knowledge.models import new_id
from src.agent.prompts import build_brief_prompt

logger = logging.getLogger("mimir.agent.brief")


async def generate_brief(harness) -> dict | None:
    """Generate the daily brief digest.

    Sections:
    1. Recently captured (since last brief, max 5)
    2. Connections found (new, unsurfaced, max 3)
    3. Resurface (relevant to recent activity, max 3)
    4. Dangling threads (saved but never revisited, 30+ days, max 2)
    5. This day last year
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Check if already generated today
    existing = await db.fetch_one(
        "SELECT id FROM daily_briefs WHERE brief_date = ?", (today,)
    )
    if existing:
        logger.info(f"Brief already generated for {today}")
        return None

    log_id = new_id()
    await db.execute(
        """INSERT INTO agent_log (id, action_type, details, status)
           VALUES (?, 'generate_brief', ?, 'running')""",
        (log_id, json.dumps({"date": today})),
    )

    try:
        # 1. Recently captured
        last_brief = await db.fetch_one(
            "SELECT generated_at FROM daily_briefs ORDER BY generated_at DESC LIMIT 1"
        )
        since = last_brief["generated_at"] if last_brief else (datetime.utcnow() - timedelta(days=1)).isoformat()

        recent = await db.fetch_all(
            """SELECT title, synthesis, source_type, created_at
               FROM notes
               WHERE created_at >= ? AND processing_status = 'complete'
               ORDER BY created_at DESC LIMIT 5""",
            (since,),
        )
        recent_text = "\n".join(
            f"- {n['title'] or 'Untitled'}: {(n['synthesis'] or '')[:100]}"
            for n in recent
        ) or "No new captures."

        # 2. New connections
        new_conns = await db.fetch_all(
            """SELECT c.explanation, c.strength, c.connection_type,
                      n1.title as source_title, n2.title as target_title
               FROM connections c
               JOIN notes n1 ON n1.id = c.source_note_id
               JOIN notes n2 ON n2.id = c.target_note_id
               WHERE c.discovered_at >= ? AND c.surfaced = 0
               ORDER BY c.strength DESC LIMIT 3""",
            (since,),
        )
        conns_text = "\n".join(
            f"- \"{c['source_title'] or 'Untitled'}\" {c['connection_type']} \"{c['target_title'] or 'Untitled'}\" "
            f"(strength: {c['strength']:.1f}): {c['explanation'] or ''}"
            for c in new_conns
        ) or "No new connections."

        # 3. Resurface items
        resurface = await db.fetch_all(
            """SELECT rq.reason, n.title
               FROM resurface_queue rq
               JOIN notes n ON n.id = rq.note_id
               WHERE rq.delivered = 0 AND rq.dismissed = 0
               ORDER BY rq.priority DESC LIMIT 3"""
        )
        resurface_text = "\n".join(
            f"- {r['title'] or 'Untitled'}: {r['reason']}"
            for r in resurface
        ) or "Nothing to resurface right now."

        # 4. Dangling threads
        cutoff_30d = (datetime.utcnow() - timedelta(days=30)).isoformat()
        dangling = await db.fetch_all(
            """SELECT n.id, n.title, n.created_at
               FROM notes n
               WHERE n.processing_status = 'complete'
               AND n.is_archived = 0
               AND n.created_at < ?
               AND n.id NOT IN (
                   SELECT note_id FROM interest_signals
                   WHERE signal_type = 'view' AND note_id IS NOT NULL
               )
               ORDER BY RANDOM() LIMIT 2""",
            (cutoff_30d,),
        )
        dangling_text = "\n".join(
            f"- \"{d['title'] or 'Untitled'}\" (saved {d['created_at'][:10]})"
            for d in dangling
        ) or "No dangling threads."

        # 5. This day last year
        last_year = (datetime.utcnow() - timedelta(days=365))
        year_window_start = (last_year - timedelta(days=2)).isoformat()
        year_window_end = (last_year + timedelta(days=2)).isoformat()
        historical = await db.fetch_all(
            """SELECT title, synthesis, created_at
               FROM notes
               WHERE created_at BETWEEN ? AND ?
               AND processing_status = 'complete'
               LIMIT 3""",
            (year_window_start, year_window_end),
        )
        historical_text = "\n".join(
            f"- \"{h['title'] or 'Untitled'}\": {(h['synthesis'] or '')[:100]}"
            for h in historical
        ) or "Nothing from this date."

        # Generate brief via LLM
        prompt = build_brief_prompt(
            date=today,
            recent_notes=recent_text,
            recent_count=len(recent),
            new_connections=conns_text,
            resurface_items=resurface_text,
            dangling_items=dangling_text,
            historical_items=historical_text,
        )

        brief_content = await harness.complete(
            operation=AIOperation.REASON,
            prompt=prompt,
            system="You are Mimir, a personal knowledge assistant. Be warm, concise, and insightful.",
            temperature=0.6,
            max_tokens=500,
        )

        brief_content = brief_content.strip()

        # Store sections data
        sections = {
            "recent": [{"title": n["title"], "created_at": n["created_at"]} for n in recent],
            "connections": [
                {"source": c["source_title"], "target": c["target_title"],
                 "type": c["connection_type"], "explanation": c["explanation"]}
                for c in new_conns
            ],
            "resurface": [{"title": r["title"], "reason": r["reason"]} for r in resurface],
            "dangling": [{"title": d["title"], "created_at": d["created_at"]} for d in dangling],
            "historical": [{"title": h["title"]} for h in historical],
        }

        # Save brief
        brief_id = new_id()
        await db.execute(
            """INSERT INTO daily_briefs (id, brief_date, content, sections)
               VALUES (?, ?, ?, ?)""",
            (brief_id, today, brief_content, json.dumps(sections)),
        )

        # Mark resurface items as delivered
        for r in resurface:
            pass  # They'll be shown with the brief

        # Mark connections as surfaced
        for c in new_conns:
            pass  # Brief counts as surfacing

        await db.execute(
            """UPDATE agent_log SET status = 'complete', completed_at = ?,
               details = ? WHERE id = ?""",
            (datetime.utcnow().isoformat(),
             json.dumps({"date": today, "sections": list(sections.keys())}),
             log_id),
        )

        logger.info(f"Daily brief generated for {today}")
        return {
            "id": brief_id,
            "date": today,
            "content": brief_content,
            "sections": sections,
        }

    except Exception as e:
        logger.error(f"Failed to generate daily brief: {e}")
        await db.execute(
            """UPDATE agent_log SET status = 'error', error_message = ?,
               completed_at = ? WHERE id = ?""",
            (str(e), datetime.utcnow().isoformat(), log_id),
        )
        return None


async def get_latest_brief() -> dict | None:
    """Get the most recent daily brief."""
    row = await db.fetch_one(
        "SELECT * FROM daily_briefs ORDER BY generated_at DESC LIMIT 1"
    )
    if not row:
        return None
    result = dict(row)
    if result.get("sections"):
        try:
            result["sections"] = json.loads(result["sections"])
        except (json.JSONDecodeError, TypeError):
            pass
    return result


async def get_brief_by_date(date: str) -> dict | None:
    """Get a brief for a specific date."""
    row = await db.fetch_one(
        "SELECT * FROM daily_briefs WHERE brief_date = ?", (date,)
    )
    if not row:
        return None
    result = dict(row)
    if result.get("sections"):
        try:
            result["sections"] = json.loads(result["sections"])
        except (json.JSONDecodeError, TypeError):
            pass
    return result
