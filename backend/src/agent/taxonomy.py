"""Taxonomy evolution — weekly concept hierarchy reorganization."""

import json
import logging
from datetime import datetime

from src.harness import AIOperation
from src.knowledge import database as db
from src.knowledge.models import new_id
from src.processing.extractor import _parse_json_response
from src.agent.prompts import build_taxonomy_merge_prompt

logger = logging.getLogger("mimir.agent.taxonomy")


async def rebuild_taxonomy(harness, vector_store) -> dict:
    """Weekly task to reorganize the concept hierarchy.

    Steps:
    1. Get all concepts with their note counts
    2. Merge near-duplicate concepts (embedding similarity > 0.92)
    3. Identify parent-child relationships via LLM
    4. Prune concepts with 0 notes
    5. Identify emerging clusters (concepts growing fast)
    """
    log_id = new_id()
    await db.execute(
        """INSERT INTO agent_log (id, action_type, details, status)
           VALUES (?, 'rebuild_taxonomy', '{}', 'running')""",
        (log_id,),
    )

    merged = 0
    pruned = 0
    hierarchies_set = 0

    try:
        # 1. Get all concepts
        concepts = await db.fetch_all(
            "SELECT id, name, note_count, parent_id FROM concepts ORDER BY note_count DESC"
        )

        if len(concepts) < 2:
            await _finish_log(log_id, "complete", {"merged": 0, "pruned": 0})
            return {"merged": 0, "pruned": 0, "hierarchies": 0}

        # 2. Find near-duplicate concepts via embedding similarity
        concept_names = [c["name"] for c in concepts if c["note_count"] > 0]
        if concept_names:
            try:
                embeddings = await harness.embed(concept_names)
                merge_pairs = _find_similar_pairs(concept_names, embeddings, threshold=0.92)

                for keep_name, merge_name in merge_pairs:
                    merged += await _merge_concepts(keep_name, merge_name)
            except Exception as e:
                logger.warning(f"Embedding-based merge failed: {e}")

        # 3. Use LLM to identify parent-child relationships
        # Only for concepts with 3+ notes to avoid noise
        significant_concepts = [c for c in concepts if c["note_count"] >= 3 and c.get("parent_id") is None]
        if len(significant_concepts) > 2:
            try:
                prompt = build_taxonomy_merge_prompt(significant_concepts[:30])
                response = await harness.complete(
                    operation=AIOperation.REASON,
                    prompt=prompt,
                    system="Respond with valid JSON only.",
                    temperature=0.2,
                    response_format="json",
                )

                data = _parse_json_response(response)

                # Apply LLM-suggested merges
                for merge in data.get("merges", []):
                    keep = merge.get("keep", "")
                    for dup in merge.get("merge", []):
                        if keep and dup and keep != dup:
                            merged += await _merge_concepts(keep, dup)

                # Apply hierarchies
                for hierarchy in data.get("hierarchies", []):
                    parent_name = hierarchy.get("parent", "")
                    children = hierarchy.get("children", [])
                    for child_name in children:
                        if parent_name and child_name and parent_name != child_name:
                            success = await _set_parent(parent_name, child_name)
                            if success:
                                hierarchies_set += 1

            except Exception as e:
                logger.warning(f"LLM taxonomy analysis failed: {e}")

        # 4. Prune empty concepts
        cursor = await db.execute(
            "DELETE FROM concepts WHERE note_count = 0 AND id NOT IN (SELECT parent_id FROM concepts WHERE parent_id IS NOT NULL)"
        )
        pruned = cursor.rowcount

        # 5. Update counts
        await db.execute(
            """UPDATE concepts SET note_count = (
                SELECT COUNT(*) FROM note_concepts WHERE concept_id = concepts.id
            )"""
        )

        result = {"merged": merged, "pruned": pruned, "hierarchies": hierarchies_set}
        await _finish_log(log_id, "complete", result)
        logger.info(f"Taxonomy rebuild: {merged} merged, {pruned} pruned, {hierarchies_set} hierarchies")
        return result

    except Exception as e:
        logger.error(f"Taxonomy rebuild failed: {e}")
        await _finish_log(log_id, "error", {"error": str(e)})
        return {"merged": merged, "pruned": pruned, "hierarchies": hierarchies_set, "error": str(e)}


def _find_similar_pairs(
    names: list[str], embeddings: list[list[float]], threshold: float = 0.92
) -> list[tuple[str, str]]:
    """Find pairs of concepts with cosine similarity above threshold."""
    pairs = []
    n = len(names)

    for i in range(n):
        for j in range(i + 1, n):
            sim = _cosine_similarity(embeddings[i], embeddings[j])
            if sim > threshold:
                # Keep the one with more characters (likely more specific)
                if len(names[i]) >= len(names[j]):
                    pairs.append((names[i], names[j]))
                else:
                    pairs.append((names[j], names[i]))

    return pairs


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0
    return dot / (norm_a * norm_b)


async def _merge_concepts(keep_name: str, merge_name: str) -> int:
    """Merge merge_name into keep_name. Returns 1 if merged, 0 if not."""
    keep = await db.fetch_one("SELECT id FROM concepts WHERE name = ?", (keep_name,))
    merge = await db.fetch_one("SELECT id FROM concepts WHERE name = ?", (merge_name,))

    if not keep or not merge or keep["id"] == merge["id"]:
        return 0

    # Move note_concepts links
    await db.execute(
        """UPDATE OR IGNORE note_concepts SET concept_id = ? WHERE concept_id = ?""",
        (keep["id"], merge["id"]),
    )
    # Delete orphaned links (duplicates from the IGNORE)
    await db.execute(
        "DELETE FROM note_concepts WHERE concept_id = ?", (merge["id"],)
    )
    # Update children
    await db.execute(
        "UPDATE concepts SET parent_id = ? WHERE parent_id = ?",
        (keep["id"], merge["id"]),
    )
    # Delete merged concept
    await db.execute("DELETE FROM concepts WHERE id = ?", (merge["id"],))

    logger.info(f"Merged concept '{merge_name}' into '{keep_name}'")
    return 1


async def _set_parent(parent_name: str, child_name: str) -> bool:
    """Set a parent-child relationship between concepts."""
    parent = await db.fetch_one("SELECT id FROM concepts WHERE name = ?", (parent_name,))
    child = await db.fetch_one("SELECT id FROM concepts WHERE name = ?", (child_name,))

    if not parent or not child or parent["id"] == child["id"]:
        return False

    # Avoid cycles
    if child["id"] == parent.get("parent_id"):
        return False

    await db.execute(
        "UPDATE concepts SET parent_id = ? WHERE id = ?",
        (parent["id"], child["id"]),
    )
    return True


async def _finish_log(log_id: str, status: str, details: dict) -> None:
    await db.execute(
        """UPDATE agent_log SET status = ?, details = ?, completed_at = ? WHERE id = ?""",
        (status, json.dumps(details), datetime.utcnow().isoformat(), log_id),
    )
