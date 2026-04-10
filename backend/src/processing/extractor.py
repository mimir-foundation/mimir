import json
import logging
import re

from src.harness import AIOperation
from src.knowledge import database as db
from src.knowledge.models import ExtractionResult, EntityExtraction, new_id

logger = logging.getLogger("mimir.processing.extractor")


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    text = text.strip()
    # Remove markdown code fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    logger.warning(f"Failed to parse JSON from LLM response: {text[:200]}")
    return {}


async def extract(note_id: str, processed_content: str, source_type: str, harness) -> ExtractionResult:
    from src.processing.prompts import build_extraction_prompt

    prompt = build_extraction_prompt(processed_content, source_type)

    response = await harness.complete(
        operation=AIOperation.EXTRACT,
        prompt=prompt,
        system="You are a knowledge librarian. Always respond with valid JSON only.",
        temperature=0.1,
        response_format="json",
    )

    data = _parse_json_response(response)
    if not data:
        logger.warning(f"Empty extraction for note {note_id}")
        return ExtractionResult()

    result = ExtractionResult(
        suggested_title=data.get("suggested_title"),
        concepts=[c.lower().strip() for c in data.get("concepts", []) if isinstance(c, str)],
        entities=[
            EntityExtraction(name=e["name"], type=e.get("type", "tool"), role=e.get("role"))
            for e in data.get("entities", [])
            if isinstance(e, dict) and "name" in e
        ],
        key_claims=data.get("key_claims", []),
        content_type=data.get("content_type", "reference"),
        temporal_relevance=data.get("temporal_relevance", "evergreen"),
        expiry_hint=data.get("expiry_hint"),
        action_items=data.get("action_items", []),
    )

    # Upsert concepts
    for concept_name in result.concepts[:10]:
        concept_id = new_id()
        await db.execute(
            "INSERT OR IGNORE INTO concepts (id, name) VALUES (?, ?)",
            (concept_id, concept_name),
        )
        concept_row = await db.fetch_one("SELECT id FROM concepts WHERE name = ?", (concept_name,))
        if concept_row:
            await db.execute(
                "INSERT OR IGNORE INTO note_concepts (note_id, concept_id, relevance_score) VALUES (?, ?, 1.0)",
                (note_id, concept_row["id"]),
            )

    # Upsert entities
    for entity in result.entities[:15]:
        entity_id = new_id()
        etype = entity.type.lower().strip() if entity.type else "tool"
        await db.execute(
            "INSERT OR IGNORE INTO entities (id, name, entity_type) VALUES (?, ?, ?)",
            (entity_id, entity.name, etype),
        )
        entity_row = await db.fetch_one(
            "SELECT id FROM entities WHERE name = ? AND entity_type = ?",
            (entity.name, etype),
        )
        if entity_row:
            await db.execute(
                "INSERT OR IGNORE INTO note_entities (note_id, entity_id, context) VALUES (?, ?, ?)",
                (note_id, entity_row["id"], entity.role),
            )

    # Update note title if none exists
    if result.suggested_title:
        await db.execute(
            "UPDATE notes SET title = ? WHERE id = ? AND title IS NULL",
            (result.suggested_title, note_id),
        )

    return result
