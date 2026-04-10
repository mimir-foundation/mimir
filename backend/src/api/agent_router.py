import json
import logging
from typing import Optional

from fastapi import APIRouter, Request

from src.knowledge import database as db

logger = logging.getLogger("mimir.api.agent")

router = APIRouter(prefix="/api/agent", tags=["agent"])


# --- Daily Brief ---

@router.get("/brief")
async def get_brief(date: Optional[str] = None):
    """Get a daily brief. If no date specified, returns the latest."""
    from src.agent.daily_brief import get_latest_brief, get_brief_by_date

    if date:
        brief = await get_brief_by_date(date)
    else:
        brief = await get_latest_brief()

    if not brief:
        return {"brief": None, "message": "No brief available"}
    return {"brief": brief}


@router.post("/brief/generate")
async def trigger_brief(request: Request):
    """Manually trigger brief generation."""
    from src.agent.daily_brief import generate_brief
    brief = await generate_brief(request.app.state.harness)
    if brief:
        from src.agent.notifications import send_brief_notification
        await send_brief_notification(brief["content"])
        return {"ok": True, "brief": brief}
    return {"ok": False, "message": "Brief already generated today or generation failed"}


# --- Resurface ---

@router.get("/resurface")
async def get_resurface_items(limit: int = 10):
    """Get pending resurface items."""
    from src.agent.resurface import get_pending_items
    items = await get_pending_items(limit)
    return {"items": items}


@router.post("/resurface/{item_id}/click")
async def click_resurface(item_id: str):
    """Mark a resurface item as clicked (user engaged)."""
    from src.agent.resurface import mark_clicked, mark_delivered
    await mark_clicked(item_id)
    await mark_delivered(item_id)
    return {"ok": True}


@router.post("/resurface/{item_id}/dismiss")
async def dismiss_resurface(item_id: str):
    """Dismiss a resurface item."""
    from src.agent.resurface import mark_dismissed
    await mark_dismissed(item_id)
    return {"ok": True}


# --- Activity Log ---

@router.get("/activity")
async def get_activity(limit: int = 20, offset: int = 0):
    """Get agent activity log."""
    rows = await db.fetch_all(
        """SELECT * FROM agent_log
           ORDER BY started_at DESC
           LIMIT ? OFFSET ?""",
        (limit, offset),
    )

    total = await db.fetch_one("SELECT COUNT(*) as cnt FROM agent_log")

    results = []
    for row in rows:
        r = dict(row)
        if r.get("details"):
            try:
                r["details"] = json.loads(r["details"])
            except (json.JSONDecodeError, TypeError):
                pass
        results.append(r)

    return {"log": results, "total": total["cnt"] if total else 0}


# --- Interest Signals ---

@router.get("/interests")
async def get_interests():
    """Get current interest topics (decayed)."""
    from src.agent.signals import get_recent_interests
    interests = await get_recent_interests()
    return {"interests": interests}


# --- Manual Triggers ---

@router.post("/deep-scan")
async def trigger_deep_scan(request: Request):
    """Manually trigger a connection deep scan."""
    from src.agent.connection_finder import deep_scan
    result = await deep_scan(request.app.state.harness, request.app.state.vector_store)
    return {"ok": True, "result": result}


@router.post("/taxonomy-rebuild")
async def trigger_taxonomy_rebuild(request: Request):
    """Manually trigger taxonomy rebuild."""
    from src.agent.taxonomy import rebuild_taxonomy
    result = await rebuild_taxonomy(request.app.state.harness, request.app.state.vector_store)
    return {"ok": True, "result": result}
