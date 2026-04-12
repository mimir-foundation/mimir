import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.knowledge.models import SearchFilters
from src.search.engine import MimirSearch

logger = logging.getLogger("mimir.api.search")

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search(
    request: Request,
    q: str,
    mode: str = "search",
    source_type: Optional[str] = None,
    concepts: Optional[str] = None,
    entities: Optional[str] = None,
    tags: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    content_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    filters = SearchFilters(
        source_type=source_type,
        concepts=concepts.split(",") if concepts else None,
        entities=entities.split(",") if entities else None,
        tags=tags.split(",") if tags else None,
        date_from=datetime.fromisoformat(after) if after else None,
        date_to=datetime.fromisoformat(before) if before else None,
        content_type=content_type,
    )

    engine = MimirSearch(
        harness=request.app.state.harness,
        vector_store=request.app.state.vector_store,
    )

    if mode == "ask":
        result = await engine.ask(q)
        # Log interest signal
        try:
            from src.agent.runtime import on_search
            await on_search(q)
        except Exception:
            pass
        return result

    results = await engine.search(q, filters=filters, limit=limit + offset)
    paged = results[offset : offset + limit]

    # Log interest signal
    try:
        from src.agent.runtime import on_search
        await on_search(q)
    except Exception:
        pass

    return {
        "results": [r.model_dump() for r in paged],
        "total": len(results),
    }


class AskRequest(BaseModel):
    q: str
    conversation: list[dict] | None = None


@router.post("")
async def ask_with_context(request: Request, body: AskRequest):
    """Ask with conversation history for multi-turn chat."""
    engine = MimirSearch(
        harness=request.app.state.harness,
        vector_store=request.app.state.vector_store,
    )
    result = await engine.ask(body.q, conversation=body.conversation)
    try:
        from src.agent.runtime import on_search
        await on_search(body.q)
    except Exception:
        pass
    return result
