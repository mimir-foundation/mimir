"""Deep scan for connections that the real-time linker might miss."""

import json
import logging
from datetime import datetime, timedelta

from src.harness import AIOperation
from src.knowledge import database as db
from src.knowledge.models import new_id
from src.processing.extractor import _parse_json_response
from src.processing.prompts import build_link_validation_prompt

logger = logging.getLogger("mimir.agent.connections")

MAX_LLM_CALLS_PER_SCAN = 50


async def deep_scan(harness, vector_store) -> dict:
    """Periodic deep scan for cross-note connections.

    Strategy:
    1. Get all notes from last 7 days
    2. For each, find top-10 semantic neighbors across ALL notes
    3. Filter to pairs that don't already have a connection
    4. Use LLM to validate each candidate
    5. Create connections for validated pairs
    6. Queue high-strength connections for resurface

    Returns summary of scan results.
    """
    scan_id = new_id()
    started_at = datetime.utcnow().isoformat()
    llm_calls = 0
    connections_found = 0

    await db.execute(
        """INSERT INTO agent_log (id, action_type, details, status)
           VALUES (?, 'deep_scan', ?, 'running')""",
        (scan_id, json.dumps({"started_at": started_at})),
    )

    try:
        # Get recent notes
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        recent_notes = await db.fetch_all(
            """SELECT id, title, synthesis, processed_content
               FROM notes
               WHERE processing_status = 'complete' AND created_at >= ?
               ORDER BY created_at DESC
               LIMIT 50""",
            (cutoff,),
        )

        if not recent_notes:
            logger.info("Deep scan: no recent notes to scan")
            await _finish_log(scan_id, "complete", {"connections_found": 0, "llm_calls": 0})
            return {"connections_found": 0, "llm_calls": 0}

        # Get existing connection pairs
        existing_pairs = set()
        all_conns = await db.fetch_all(
            "SELECT source_note_id, target_note_id FROM connections"
        )
        for c in all_conns:
            pair = tuple(sorted([c["source_note_id"], c["target_note_id"]]))
            existing_pairs.add(pair)

        # Collect candidates
        candidates: list[tuple[str, str, float]] = []  # (note_a, note_b, similarity)

        for note in recent_notes:
            if llm_calls >= MAX_LLM_CALLS_PER_SCAN:
                break

            # Get embeddings for this note
            note_chunks = vector_store.get_note_chunks(note["id"])
            if not note_chunks["ids"] or not note_chunks.get("embeddings"):
                continue

            # Search for neighbors using first chunk
            results = vector_store.search(
                query_embedding=note_chunks["embeddings"][0],
                n_results=15,
            )

            if not results["ids"] or not results["ids"][0]:
                continue

            for i, doc_id in enumerate(results["ids"][0]):
                neighbor_note_id = results["metadatas"][0][i].get("note_id")
                if not neighbor_note_id or neighbor_note_id == note["id"]:
                    continue

                distance = results["distances"][0][i]
                similarity = 1 - distance

                if similarity < 0.6:  # Lower threshold for deep scan
                    continue

                pair = tuple(sorted([note["id"], neighbor_note_id]))
                if pair in existing_pairs:
                    continue

                candidates.append((note["id"], neighbor_note_id, similarity))
                existing_pairs.add(pair)  # Avoid duplicates in candidates

        # Sort by similarity, validate with LLM
        candidates.sort(key=lambda x: x[2], reverse=True)

        for note_a_id, note_b_id, similarity in candidates:
            if llm_calls >= MAX_LLM_CALLS_PER_SCAN:
                break

            note_a = await db.fetch_one(
                "SELECT title, synthesis, processed_content FROM notes WHERE id = ?",
                (note_a_id,),
            )
            note_b = await db.fetch_one(
                "SELECT title, synthesis, processed_content FROM notes WHERE id = ?",
                (note_b_id,),
            )

            if not note_a or not note_b:
                continue

            # Get concepts
            concepts_a = await db.fetch_all(
                """SELECT c.name FROM concepts c
                   JOIN note_concepts nc ON c.id = nc.concept_id
                   WHERE nc.note_id = ?""",
                (note_a_id,),
            )
            concepts_b = await db.fetch_all(
                """SELECT c.name FROM concepts c
                   JOIN note_concepts nc ON c.id = nc.concept_id
                   WHERE nc.note_id = ?""",
                (note_b_id,),
            )

            prompt = build_link_validation_prompt(
                note_a_title=note_a["title"] or "Untitled",
                note_a_content=note_a["synthesis"] or (note_a["processed_content"] or "")[:500],
                note_a_concepts=", ".join(c["name"] for c in concepts_a),
                note_b_title=note_b["title"] or "Untitled",
                note_b_content=note_b["synthesis"] or (note_b["processed_content"] or "")[:500],
                note_b_concepts=", ".join(c["name"] for c in concepts_b),
            )

            try:
                response = await harness.complete(
                    operation=AIOperation.REASON,
                    prompt=prompt,
                    system="Respond with valid JSON only.",
                    temperature=0.2,
                    response_format="json",
                )
                llm_calls += 1

                data = _parse_json_response(response)
                if data.get("connected") and data.get("strength", 0) > 0.5:
                    conn_id = new_id()
                    await db.execute(
                        """INSERT OR IGNORE INTO connections
                           (id, source_note_id, target_note_id, connection_type, strength, explanation)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            conn_id,
                            note_a_id,
                            note_b_id,
                            data.get("type", "related"),
                            data.get("strength", 0.5),
                            data.get("explanation", ""),
                        ),
                    )
                    connections_found += 1

                    # Queue strong connections for resurface
                    if data.get("strength", 0) > 0.7:
                        from src.agent.resurface import _queue_resurface
                        await _queue_resurface(
                            queue_type="connection_alert",
                            note_id=note_b_id,
                            connection_id=conn_id,
                            reason=f"Deep scan found a connection: {data.get('explanation', 'Related notes')}",
                            priority=data.get("strength", 0.7),
                        )

            except Exception as e:
                logger.warning(f"LLM validation failed during deep scan: {e}")
                llm_calls += 1
                continue

        result = {
            "connections_found": connections_found,
            "llm_calls": llm_calls,
            "candidates_evaluated": min(len(candidates), MAX_LLM_CALLS_PER_SCAN),
            "recent_notes_scanned": len(recent_notes),
        }
        await _finish_log(scan_id, "complete", result)
        logger.info(f"Deep scan complete: {connections_found} connections, {llm_calls} LLM calls")
        return result

    except Exception as e:
        logger.error(f"Deep scan failed: {e}")
        await _finish_log(scan_id, "error", {"error": str(e)})
        return {"connections_found": 0, "llm_calls": llm_calls, "error": str(e)}


async def _finish_log(scan_id: str, status: str, details: dict) -> None:
    await db.execute(
        """UPDATE agent_log
           SET status = ?, details = ?, completed_at = ?
           WHERE id = ?""",
        (status, json.dumps(details), datetime.utcnow().isoformat(), scan_id),
    )
