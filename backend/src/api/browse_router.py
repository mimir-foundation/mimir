import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from src.knowledge import database as db
from src.knowledge.models import new_id

logger = logging.getLogger("mimir.api.browse")

router = APIRouter(prefix="/api", tags=["browse"])


@router.get("/notes")
async def list_notes(
    sort: str = "recent",
    source_type: Optional[str] = None,
    processing_status: Optional[str] = None,
    is_starred: Optional[bool] = None,
    is_archived: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
):
    sql = "SELECT * FROM notes WHERE 1=1"
    params = []

    if source_type:
        sql += " AND source_type = ?"
        params.append(source_type)
    if processing_status:
        sql += " AND processing_status = ?"
        params.append(processing_status)
    if is_starred is not None:
        sql += " AND is_starred = ?"
        params.append(1 if is_starred else 0)
    if is_archived is not None:
        sql += " AND is_archived = ?"
        params.append(1 if is_archived else 0)
    else:
        sql += " AND is_archived = 0"

    if sort == "starred":
        sql += " ORDER BY is_starred DESC, created_at DESC"
    elif sort == "most_connected":
        sql = sql.replace(
            "SELECT * FROM notes",
            """SELECT n.*, COALESCE(conn_count, 0) as connection_count FROM notes n
               LEFT JOIN (
                   SELECT source_note_id as note_id, COUNT(*) as conn_count FROM connections GROUP BY source_note_id
                   UNION ALL
                   SELECT target_note_id, COUNT(*) FROM connections GROUP BY target_note_id
               ) cc ON n.id = cc.note_id""",
        )
        sql += " ORDER BY connection_count DESC, created_at DESC"
    else:
        sql += " ORDER BY created_at DESC"

    sql += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    notes = await db.fetch_all(sql, tuple(params))

    # Enrich with concepts and tags
    results = []
    for note in notes:
        concepts = await db.fetch_all(
            "SELECT c.name FROM concepts c JOIN note_concepts nc ON c.id = nc.concept_id WHERE nc.note_id = ?",
            (note["id"],),
        )
        tags = await db.fetch_all(
            "SELECT t.name FROM tags t JOIN note_tags nt ON t.id = nt.tag_id WHERE nt.note_id = ?",
            (note["id"],),
        )
        results.append({
            **note,
            "concepts": [c["name"] for c in concepts],
            "tags": [t["name"] for t in tags],
        })

    # Total count
    count_sql = "SELECT COUNT(*) as cnt FROM notes WHERE is_archived = 0"
    total = await db.fetch_one(count_sql)

    return {"notes": results, "total": total["cnt"] if total else 0}


@router.get("/notes/{note_id}")
async def get_note(note_id: str):
    # Log interest signal
    try:
        from src.agent.runtime import on_note_viewed
        await on_note_viewed(note_id)
    except Exception:
        pass

    note = await db.fetch_one("SELECT * FROM notes WHERE id = ?", (note_id,))
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    concepts = await db.fetch_all(
        """SELECT c.id, c.name, c.description, nc.relevance_score
           FROM concepts c JOIN note_concepts nc ON c.id = nc.concept_id
           WHERE nc.note_id = ?""",
        (note_id,),
    )
    entities = await db.fetch_all(
        """SELECT e.id, e.name, e.entity_type, ne.context
           FROM entities e JOIN note_entities ne ON e.id = ne.entity_id
           WHERE ne.note_id = ?""",
        (note_id,),
    )
    tags = await db.fetch_all(
        "SELECT t.id, t.name, t.color FROM tags t JOIN note_tags nt ON t.id = nt.tag_id WHERE nt.note_id = ?",
        (note_id,),
    )
    connections = await db.fetch_all(
        """SELECT c.id, c.target_note_id, c.connection_type, c.strength, c.explanation,
                  n.title as target_title
           FROM connections c
           JOIN notes n ON n.id = c.target_note_id
           WHERE c.source_note_id = ?
           UNION ALL
           SELECT c.id, c.source_note_id, c.connection_type, c.strength, c.explanation,
                  n.title as target_title
           FROM connections c
           JOIN notes n ON n.id = c.source_note_id
           WHERE c.target_note_id = ?""",
        (note_id, note_id),
    )

    actions = await db.fetch_all(
        "SELECT * FROM note_actions WHERE note_id = ? ORDER BY created_at",
        (note_id,),
    )

    return {
        **note,
        "concepts": [dict(c) for c in concepts],
        "entities": [dict(e) for e in entities],
        "tags": [dict(t) for t in tags],
        "connections": [dict(c) for c in connections],
        "actions": [dict(a) for a in actions],
    }


@router.get("/notes/{note_id}/actions")
async def get_note_actions(note_id: str):
    actions = await db.fetch_all(
        "SELECT * FROM note_actions WHERE note_id = ? ORDER BY created_at",
        (note_id,),
    )
    return {"actions": [dict(a) for a in actions]}


@router.put("/notes/{note_id}")
async def update_note(note_id: str, body: dict):
    note = await db.fetch_one("SELECT id FROM notes WHERE id = ?", (note_id,))
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    allowed = {"title", "is_starred", "is_archived"}
    updates = []
    params = []
    for key, value in body.items():
        if key in allowed:
            if key in ("is_starred", "is_archived"):
                value = 1 if value else 0
            updates.append(f"{key} = ?")
            params.append(value)

    # Handle tags
    if "tags" in body and isinstance(body["tags"], list):
        await db.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
        for tag_name in body["tags"]:
            tag_name = tag_name.strip().lower()
            if not tag_name:
                continue
            tid = new_id()
            await db.execute("INSERT OR IGNORE INTO tags (id, name) VALUES (?, ?)", (tid, tag_name))
            tag_row = await db.fetch_one("SELECT id FROM tags WHERE name = ?", (tag_name,))
            if tag_row:
                await db.execute(
                    "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
                    (note_id, tag_row["id"]),
                )

    if updates:
        sql = f"UPDATE notes SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        params.append(note_id)
        await db.execute(sql, tuple(params))

    # Log star signal
    if "is_starred" in body:
        try:
            from src.agent.runtime import on_note_starred
            await on_note_starred(note_id, bool(body["is_starred"]))
        except Exception:
            pass

    return {"ok": True}


@router.delete("/notes/{note_id}")
async def delete_note(request: Request, note_id: str):
    note = await db.fetch_one("SELECT id FROM notes WHERE id = ?", (note_id,))
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Delete from vector store
    request.app.state.vector_store.delete_note(note_id)

    # Delete document store files on disk
    try:
        from src.config import get_settings
        from src.knowledge.document_store import DocumentStore
        doc_store = DocumentStore(get_settings().documents_path)
        doc_store.delete_document(note_id)
    except Exception:
        pass

    # Delete orphaned interest_signals (no FK constraint)
    await db.execute("DELETE FROM interest_signals WHERE note_id = ?", (note_id,))

    # Cascade delete in SQLite (foreign keys handle most)
    await db.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    return {"ok": True}


@router.get("/errored-notes")
async def get_errored_notes():
    """Return notes with processing errors, including error details from agent_log."""
    notes = await db.fetch_all(
        "SELECT id, title, source_type, created_at, processing_status FROM notes WHERE processing_status = 'error' ORDER BY created_at DESC LIMIT 50"
    )
    results = []
    for note in notes:
        # Find latest error from agent_log for this note
        log = await db.fetch_one(
            "SELECT error_message, completed_at FROM agent_log WHERE details LIKE ? AND status = 'error' ORDER BY completed_at DESC LIMIT 1",
            (f'%{note["id"]}%',),
        )
        # Count how many times it has been retried
        retry_count = await db.fetch_one(
            "SELECT COUNT(*) as cnt FROM agent_log WHERE details LIKE ? AND status = 'error'",
            (f'%{note["id"]}%',),
        )
        results.append({
            **note,
            "error_message": log["error_message"] if log else "Unknown error",
            "error_at": log["completed_at"] if log else None,
            "retry_count": retry_count["cnt"] if retry_count else 0,
        })
    return {"notes": results}


@router.post("/notes/{note_id}/retry")
async def retry_note(note_id: str):
    """Reset an errored note to pending so the pipeline reprocesses it."""
    note = await db.fetch_one(
        "SELECT id, processing_status FROM notes WHERE id = ?", (note_id,)
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note["processing_status"] != "error":
        return {"ok": False, "error": "Note is not in error state"}
    await db.execute(
        "UPDATE notes SET processing_status = 'pending', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (note_id,),
    )
    return {"ok": True}


@router.get("/concepts")
async def list_concepts():
    concepts = await db.fetch_all(
        "SELECT * FROM concepts ORDER BY note_count DESC"
    )
    return {"concepts": concepts}


@router.get("/entities")
async def list_entities(entity_type: Optional[str] = None):
    if entity_type:
        entities = await db.fetch_all(
            "SELECT * FROM entities WHERE entity_type = ? ORDER BY name", (entity_type,)
        )
    else:
        entities = await db.fetch_all("SELECT * FROM entities ORDER BY name")
    return {"entities": entities}


@router.get("/connections")
async def list_connections(
    note_id: Optional[str] = None,
    connection_type: Optional[str] = None,
    min_strength: float = 0.0,
):
    sql = "SELECT * FROM connections WHERE strength >= ?"
    params: list = [min_strength]

    if note_id:
        sql += " AND (source_note_id = ? OR target_note_id = ?)"
        params.extend([note_id, note_id])
    if connection_type:
        sql += " AND connection_type = ?"
        params.append(connection_type)

    sql += " ORDER BY strength DESC"
    connections = await db.fetch_all(sql, tuple(params))
    return {"connections": connections}


@router.get("/stats")
async def get_stats():
    total_notes = await db.fetch_one("SELECT COUNT(*) as cnt FROM notes")
    total_concepts = await db.fetch_one("SELECT COUNT(*) as cnt FROM concepts")
    total_connections = await db.fetch_one("SELECT COUNT(*) as cnt FROM connections")
    total_entities = await db.fetch_one("SELECT COUNT(*) as cnt FROM entities")
    pending = await db.fetch_one("SELECT COUNT(*) as cnt FROM notes WHERE processing_status = 'pending'")
    processing = await db.fetch_one("SELECT COUNT(*) as cnt FROM notes WHERE processing_status = 'processing'")
    errored = await db.fetch_one("SELECT COUNT(*) as cnt FROM notes WHERE processing_status = 'error'")

    return {
        "notes": total_notes["cnt"] if total_notes else 0,
        "concepts": total_concepts["cnt"] if total_concepts else 0,
        "connections": total_connections["cnt"] if total_connections else 0,
        "entities": total_entities["cnt"] if total_entities else 0,
        "pending": pending["cnt"] if pending else 0,
        "processing": processing["cnt"] if processing else 0,
        "errored": errored["cnt"] if errored else 0,
    }


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str):
    """Entity detail page — everything we know about a person/project/etc."""
    entity = await db.fetch_one("SELECT * FROM entities WHERE id = ?", (entity_id,))
    if not entity:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Entity not found")

    # All notes mentioning this entity
    notes = await db.fetch_all(
        """SELECT n.id, n.title, n.synthesis, n.source_type, n.created_at, ne.context
           FROM notes n
           JOIN note_entities ne ON n.id = ne.note_id
           WHERE ne.entity_id = ?
           ORDER BY n.created_at DESC""",
        (entity_id,),
    )

    # Co-occurring entities (entities that appear in the same notes)
    co_entities = await db.fetch_all(
        """SELECT e.id, e.name, e.entity_type, COUNT(*) as co_count
           FROM entities e
           JOIN note_entities ne2 ON e.id = ne2.entity_id
           WHERE ne2.note_id IN (
               SELECT note_id FROM note_entities WHERE entity_id = ?
           ) AND e.id != ?
           GROUP BY e.id
           ORDER BY co_count DESC
           LIMIT 10""",
        (entity_id, entity_id),
    )

    # Concepts associated with this entity's notes
    concepts = await db.fetch_all(
        """SELECT c.id, c.name, COUNT(*) as note_count
           FROM concepts c
           JOIN note_concepts nc ON c.id = nc.concept_id
           WHERE nc.note_id IN (
               SELECT note_id FROM note_entities WHERE entity_id = ?
           )
           GROUP BY c.id
           ORDER BY note_count DESC
           LIMIT 10""",
        (entity_id,),
    )

    return {
        **entity,
        "notes": notes,
        "co_entities": co_entities,
        "concepts": concepts,
        "note_count": len(notes),
    }


@router.get("/concepts/{concept_id}")
async def get_concept(concept_id: str):
    """Concept detail — all notes, child concepts, parent chain."""
    concept = await db.fetch_one("SELECT * FROM concepts WHERE id = ?", (concept_id,))
    if not concept:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Concept not found")

    # Notes with this concept
    notes = await db.fetch_all(
        """SELECT n.id, n.title, n.synthesis, n.source_type, n.created_at, nc.relevance_score
           FROM notes n
           JOIN note_concepts nc ON n.id = nc.note_id
           WHERE nc.concept_id = ?
           ORDER BY nc.relevance_score DESC, n.created_at DESC""",
        (concept_id,),
    )

    # Children
    children = await db.fetch_all(
        "SELECT id, name, note_count FROM concepts WHERE parent_id = ? ORDER BY note_count DESC",
        (concept_id,),
    )

    # Parent chain
    parents = []
    current = concept
    while current and current.get("parent_id"):
        parent = await db.fetch_one(
            "SELECT id, name, parent_id FROM concepts WHERE id = ?",
            (current["parent_id"],),
        )
        if parent:
            parents.append({"id": parent["id"], "name": parent["name"]})
            current = parent
        else:
            break

    return {
        **concept,
        "notes": notes,
        "children": children,
        "parents": list(reversed(parents)),
    }


@router.get("/graph")
async def get_graph(
    concept: Optional[str] = None,
    entity: Optional[str] = None,
    connection_type: Optional[str] = None,
    min_strength: float = 0.3,
    limit: int = 200,
):
    """Graph data for force-directed visualization.

    Returns nodes (notes) and edges (connections) suitable for D3.
    """
    # Build note filter
    note_ids = None

    if concept:
        rows = await db.fetch_all(
            """SELECT nc.note_id FROM note_concepts nc
               JOIN concepts c ON c.id = nc.concept_id
               WHERE c.name = ?""",
            (concept,),
        )
        note_ids = {r["note_id"] for r in rows}

    if entity:
        rows = await db.fetch_all(
            """SELECT ne.note_id FROM note_entities ne
               JOIN entities e ON e.id = ne.entity_id
               WHERE e.name = ?""",
            (entity,),
        )
        entity_note_ids = {r["note_id"] for r in rows}
        note_ids = note_ids & entity_note_ids if note_ids else entity_note_ids

    # Get connections
    conn_sql = "SELECT * FROM connections WHERE strength >= ?"
    conn_params: list = [min_strength]

    if connection_type:
        conn_sql += " AND connection_type = ?"
        conn_params.append(connection_type)

    conn_sql += " ORDER BY strength DESC LIMIT ?"
    conn_params.append(limit * 2)

    all_connections = await db.fetch_all(conn_sql, tuple(conn_params))

    # Filter to relevant notes
    if note_ids is not None:
        connections = [
            c for c in all_connections
            if c["source_note_id"] in note_ids or c["target_note_id"] in note_ids
        ]
    else:
        connections = all_connections

    # Collect all referenced note IDs
    referenced_ids = set()
    for c in connections:
        referenced_ids.add(c["source_note_id"])
        referenced_ids.add(c["target_note_id"])

    if not referenced_ids:
        return {"nodes": [], "edges": []}

    # Fetch notes for nodes
    placeholders = ",".join("?" * len(referenced_ids))
    notes = await db.fetch_all(
        f"""SELECT id, title, source_type, created_at, is_starred
            FROM notes WHERE id IN ({placeholders})
            LIMIT ?""",
        (*referenced_ids, limit),
    )

    # Get concepts per note for coloring
    nodes = []
    for note in notes:
        concepts = await db.fetch_all(
            "SELECT c.name FROM concepts c JOIN note_concepts nc ON c.id = nc.concept_id WHERE nc.note_id = ? LIMIT 3",
            (note["id"],),
        )
        # Count connections for sizing
        conn_count = sum(
            1 for c in connections
            if c["source_note_id"] == note["id"] or c["target_note_id"] == note["id"]
        )
        nodes.append({
            "id": note["id"],
            "title": note["title"] or "Untitled",
            "source_type": note["source_type"],
            "created_at": note["created_at"],
            "is_starred": note["is_starred"],
            "concepts": [c["name"] for c in concepts],
            "connection_count": conn_count,
        })

    edges = [
        {
            "source": c["source_note_id"],
            "target": c["target_note_id"],
            "type": c["connection_type"],
            "strength": c["strength"],
            "explanation": c["explanation"],
        }
        for c in connections
    ]

    return {"nodes": nodes, "edges": edges}
