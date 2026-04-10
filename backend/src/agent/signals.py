"""Interest signal tracking with 7-day half-life decay."""

import logging
import math
from datetime import datetime, timedelta

from src.knowledge import database as db
from src.knowledge.models import new_id

logger = logging.getLogger("mimir.agent.signals")

HALF_LIFE_DAYS = 7


async def log_signal(
    signal_type: str,
    note_id: str | None = None,
    query: str | None = None,
    concept: str | None = None,
    weight: float = 1.0,
) -> None:
    """Log an interest signal. Types: search, view, star, capture, unstar."""
    await db.execute(
        "INSERT INTO interest_signals (id, signal_type, note_id, query, concept, weight) VALUES (?, ?, ?, ?, ?, ?)",
        (new_id(), signal_type, note_id, query, concept, weight),
    )


async def get_recent_interests(days: int = 14, limit: int = 20) -> list[dict]:
    """Get recent interest signals with decay-weighted scores.

    Returns concepts/queries ranked by decayed interest weight.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = await db.fetch_all(
        """SELECT signal_type, note_id, query, concept, weight, created_at
           FROM interest_signals
           WHERE created_at >= ?
           ORDER BY created_at DESC""",
        (cutoff,),
    )

    # Aggregate by concept/query with decay
    scores: dict[str, float] = {}
    now = datetime.utcnow()

    for row in rows:
        age_days = (now - datetime.fromisoformat(row["created_at"])).total_seconds() / 86400
        decay = math.pow(0.5, age_days / HALF_LIFE_DAYS)
        decayed_weight = row["weight"] * decay

        key = row["concept"] or row["query"] or row["note_id"] or "unknown"
        scores[key] = scores.get(key, 0) + decayed_weight

    sorted_interests = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"topic": k, "score": v} for k, v in sorted_interests]


async def get_active_concepts(days: int = 14, min_score: float = 0.5) -> list[str]:
    """Get concept names the user has been actively engaging with."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = await db.fetch_all(
        """SELECT concept, SUM(weight) as total_weight
           FROM interest_signals
           WHERE concept IS NOT NULL AND created_at >= ?
           GROUP BY concept
           ORDER BY total_weight DESC
           LIMIT 20""",
        (cutoff,),
    )
    return [r["concept"] for r in rows if r["total_weight"] >= min_score]


async def prune_old_signals(days: int = 90) -> int:
    """Delete signals older than the given number of days."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    cursor = await db.execute(
        "DELETE FROM interest_signals WHERE created_at < ?", (cutoff,)
    )
    return cursor.rowcount
