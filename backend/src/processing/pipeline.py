import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.knowledge import database as db
from src.knowledge.models import ExtractionResult

logger = logging.getLogger("mimir.processing.pipeline")


async def process_note(note_id: str, harness, vector_store) -> None:
    """Run the full 7-stage processing pipeline on a note."""

    note = await db.fetch_one("SELECT * FROM notes WHERE id = ?", (note_id,))
    if not note:
        logger.error(f"Note {note_id} not found")
        return

    await db.execute(
        "UPDATE notes SET processing_status = 'processing', processing_stage = 'normalize' WHERE id = ?",
        (note_id,),
    )

    try:
        # Stage 1: Normalize
        from src.processing.normalizer import normalize
        processed_content, word_count, reading_time = await normalize(
            note["raw_content"], note["source_type"], note.get("source_uri"),
        )
        await db.execute(
            """UPDATE notes SET processed_content = ?, word_count = ?, reading_time_seconds = ?,
               processing_stage = 'chunk' WHERE id = ?""",
            (processed_content, word_count, reading_time, note_id),
        )
        logger.info(f"[{note_id}] Normalized: {word_count} words")

        # Stage 2: Chunk
        from src.processing.chunker import chunk
        chunks = chunk(note_id, processed_content)
        await db.execute("UPDATE notes SET processing_stage = 'extract' WHERE id = ?", (note_id,))
        logger.info(f"[{note_id}] Chunked: {len(chunks)} chunks")

        # Stage 3: Extract
        from src.processing.extractor import extract
        extraction = await extract(note_id, processed_content, note["source_type"], harness)
        await db.execute("UPDATE notes SET processing_stage = 'embed' WHERE id = ?", (note_id,))
        logger.info(f"[{note_id}] Extracted: {len(extraction.concepts)} concepts, {len(extraction.entities)} entities")

        # Stage 4: Embed
        from src.processing.embedder import embed
        entity_names = [e.name for e in extraction.entities]
        await embed(
            chunks=chunks,
            source_type=note["source_type"],
            created_at=note["created_at"],
            concepts=extraction.concepts,
            entities=entity_names,
            harness=harness,
            vector_store=vector_store,
        )
        await db.execute("UPDATE notes SET processing_stage = 'link' WHERE id = ?", (note_id,))
        logger.info(f"[{note_id}] Embedded")

        # Stage 5: Link
        from src.processing.linker import link
        connections = await link(note_id, extraction, harness, vector_store)
        await db.execute("UPDATE notes SET processing_stage = 'synthesize' WHERE id = ?", (note_id,))
        logger.info(f"[{note_id}] Linked: {len(connections)} connections")

        # Stage 6: Synthesize
        from src.processing.synthesizer import synthesize
        synthesis = await synthesize(processed_content, extraction, connections, harness)
        await db.execute(
            "UPDATE notes SET synthesis = ?, processing_stage = 'index' WHERE id = ?",
            (synthesis, note_id),
        )
        logger.info(f"[{note_id}] Synthesized")

        # Stage 7: Index
        # Update concept counts
        await db.execute(
            """UPDATE concepts SET note_count = (
                SELECT COUNT(*) FROM note_concepts WHERE concept_id = concepts.id
            )"""
        )

        # Mark complete
        now = datetime.utcnow().isoformat()
        await db.execute(
            """UPDATE notes SET processing_status = 'complete', processed_at = ?,
               processing_stage = NULL WHERE id = ?""",
            (now, note_id),
        )
        logger.info(f"[{note_id}] Processing complete")

        # Trigger agent event
        try:
            from src.agent.runtime import on_note_processed
            await on_note_processed(note_id)
        except Exception as e:
            logger.warning(f"[{note_id}] Agent on_note_processed failed: {e}")

    except Exception as e:
        logger.error(f"[{note_id}] Processing failed at stage {note.get('processing_stage', 'unknown')}: {e}")
        retry_count = note.get("retry_count", 0) + 1
        await db.execute(
            "UPDATE notes SET processing_status = 'error', retry_count = ? WHERE id = ?",
            (retry_count, note_id),
        )

        # Log to agent_log
        from src.knowledge.models import new_id
        import json
        await db.execute(
            """INSERT INTO agent_log (id, action_type, details, status, error_message, completed_at)
               VALUES (?, 'process_note', ?, 'error', ?, ?)""",
            (new_id(), json.dumps({"note_id": note_id}), str(e), datetime.utcnow().isoformat()),
        )


async def process_pending_notes(app) -> None:
    """Background job: process pending notes."""
    harness = app.state.harness
    vector_store = app.state.vector_store

    rows = await db.fetch_all(
        "SELECT id FROM notes WHERE processing_status = 'pending' ORDER BY created_at LIMIT 5"
    )

    for row in rows:
        try:
            await process_note(row["id"], harness, vector_store)
        except Exception as e:
            logger.error(f"Failed to process note {row['id']}: {e}")


async def retry_errored_notes(app) -> None:
    """Background job: retry errored notes."""
    rows = await db.fetch_all(
        "SELECT id FROM notes WHERE processing_status = 'error' AND retry_count < 3 ORDER BY created_at LIMIT 3"
    )

    for row in rows:
        await db.execute(
            "UPDATE notes SET processing_status = 'pending' WHERE id = ?",
            (row["id"],),
        )
        logger.info(f"Retrying note {row['id']}")


async def start_scheduler(app) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        process_pending_notes, "interval", seconds=30, args=[app], id="process_pending",
        max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        retry_errored_notes, "interval", minutes=15, args=[app], id="retry_errored",
        max_instances=1, coalesce=True,
    )

    # Register Phase 2 agent jobs
    from src.agent.runtime import register_agent_jobs
    register_agent_jobs(scheduler, app)

    scheduler.start()
    return scheduler
