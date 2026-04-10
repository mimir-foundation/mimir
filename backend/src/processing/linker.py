import json
import logging

from src.harness import AIOperation
from src.knowledge import database as db
from src.knowledge.models import ExtractionResult, new_id
from src.knowledge.vector_store import VectorStore
from src.processing.prompts import build_link_validation_prompt

logger = logging.getLogger("mimir.processing.linker")


async def link(
    note_id: str,
    extraction: ExtractionResult,
    harness,
    vector_store: VectorStore,
) -> list[dict]:
    """Find and create connections to existing notes. Returns created connections."""

    candidates: dict[str, float] = {}  # note_id -> signal score

    # 1. Entity overlap
    entity_names = [e.name for e in extraction.entities]
    if entity_names:
        placeholders = ",".join("?" * len(entity_names))
        rows = await db.fetch_all(
            f"""SELECT ne.note_id, COUNT(*) as overlap_count
                FROM note_entities ne
                JOIN entities e ON ne.entity_id = e.id
                WHERE e.name IN ({placeholders}) AND ne.note_id != ?
                GROUP BY ne.note_id
                ORDER BY overlap_count DESC
                LIMIT 10""",
            (*entity_names, note_id),
        )
        for row in rows:
            candidates[row["note_id"]] = candidates.get(row["note_id"], 0) + row["overlap_count"] * 0.3

    # 2. Concept overlap (2+ shared concepts)
    concept_names = extraction.concepts
    if concept_names:
        placeholders = ",".join("?" * len(concept_names))
        rows = await db.fetch_all(
            f"""SELECT nc.note_id, COUNT(*) as overlap_count
                FROM note_concepts nc
                JOIN concepts c ON nc.concept_id = c.id
                WHERE c.name IN ({placeholders}) AND nc.note_id != ?
                GROUP BY nc.note_id
                HAVING overlap_count >= 2
                ORDER BY overlap_count DESC
                LIMIT 10""",
            (*concept_names, note_id),
        )
        for row in rows:
            candidates[row["note_id"]] = candidates.get(row["note_id"], 0) + row["overlap_count"] * 0.2

    # 3. Semantic similarity via vector search
    note_chunks = vector_store.get_note_chunks(note_id)
    if note_chunks["ids"] and note_chunks.get("embeddings") is not None and len(note_chunks["embeddings"]) > 0:
        first_embedding = note_chunks["embeddings"][0]
        results = vector_store.search(query_embedding=first_embedding, n_results=10)
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                cand_note_id = results["metadatas"][0][i].get("note_id")
                if cand_note_id and cand_note_id != note_id:
                    distance = results["distances"][0][i]
                    similarity = 1 - distance  # cosine distance to similarity
                    if similarity > 0.75:
                        candidates[cand_note_id] = candidates.get(cand_note_id, 0) + similarity * 0.5

    if not candidates:
        return []

    # Filter out notes that already have connections
    existing = await db.fetch_all(
        """SELECT target_note_id FROM connections WHERE source_note_id = ?
           UNION SELECT source_note_id FROM connections WHERE target_note_id = ?""",
        (note_id, note_id),
    )
    existing_ids = {r["target_note_id"] for r in existing} | {r["source_note_id"] for r in existing}

    # Sort by signal score, take top 10 new candidates
    sorted_candidates = sorted(
        [(nid, score) for nid, score in candidates.items() if nid not in existing_ids],
        key=lambda x: x[1],
        reverse=True,
    )[:10]

    # Get current note info
    current_note = await db.fetch_one("SELECT title, synthesis, processed_content FROM notes WHERE id = ?", (note_id,))
    if not current_note:
        return []

    connections = []
    for cand_id, signal_score in sorted_candidates:
        cand_note = await db.fetch_one("SELECT title, synthesis, processed_content FROM notes WHERE id = ?", (cand_id,))
        if not cand_note:
            continue

        # Get candidate concepts
        cand_concepts = await db.fetch_all(
            """SELECT c.name FROM concepts c
               JOIN note_concepts nc ON c.id = nc.concept_id
               WHERE nc.note_id = ?""",
            (cand_id,),
        )
        cand_concept_names = ", ".join(r["name"] for r in cand_concepts)

        prompt = build_link_validation_prompt(
            note_a_title=current_note["title"] or "Untitled",
            note_a_content=current_note["synthesis"] or (current_note["processed_content"] or "")[:500],
            note_a_concepts=", ".join(extraction.concepts),
            note_b_title=cand_note["title"] or "Untitled",
            note_b_content=cand_note["synthesis"] or (cand_note["processed_content"] or "")[:500],
            note_b_concepts=cand_concept_names,
        )

        try:
            response = await harness.complete(
                operation=AIOperation.REASON,
                prompt=prompt,
                system="Respond with valid JSON only.",
                temperature=0.2,
                response_format="json",
            )

            from src.processing.extractor import _parse_json_response
            data = _parse_json_response(response)

            if data.get("connected") and data.get("strength", 0) > 0.5:
                conn_id = new_id()
                await db.execute(
                    """INSERT OR IGNORE INTO connections
                       (id, source_note_id, target_note_id, connection_type, strength, explanation)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        conn_id,
                        note_id,
                        cand_id,
                        data.get("type", "related"),
                        data.get("strength", 0.5),
                        data.get("explanation", ""),
                    ),
                )
                connections.append({
                    "id": conn_id,
                    "target_note_id": cand_id,
                    "type": data.get("type", "related"),
                    "strength": data.get("strength", 0.5),
                    "explanation": data.get("explanation", ""),
                })
        except Exception as e:
            logger.warning(f"Link validation failed for {note_id} <-> {cand_id}: {e}")
            continue

    logger.info(f"Found {len(connections)} connections for note {note_id}")
    return connections
