import logging
from typing import Optional

from src.knowledge import database as db
from src.knowledge.models import SearchFilters, SearchResult
from src.knowledge.vector_store import VectorStore

logger = logging.getLogger("mimir.search")

RRF_K = 60  # Standard RRF constant


class MimirSearch:
    def __init__(self, harness, vector_store: VectorStore):
        self.harness = harness
        self.vector_store = vector_store

    async def search(
        self, query: str, filters: Optional[SearchFilters] = None, limit: int = 20
    ) -> list[SearchResult]:
        # Run all three search strategies
        semantic_results = await self._semantic_search(query, filters)
        fts_results = await self._fts_search(query, filters)
        graph_results = await self._graph_search(query)

        # Reciprocal rank fusion
        scores: dict[str, float] = {}

        for rank, (note_id, _) in enumerate(semantic_results):
            scores[note_id] = scores.get(note_id, 0) + 0.5 / (RRF_K + rank + 1)

        for rank, (note_id, _) in enumerate(fts_results):
            scores[note_id] = scores.get(note_id, 0) + 0.3 / (RRF_K + rank + 1)

        for rank, (note_id, _) in enumerate(graph_results):
            scores[note_id] = scores.get(note_id, 0) + 0.2 / (RRF_K + rank + 1)

        # Sort by score
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]

        if not sorted_ids:
            return []

        # Fetch note details
        results = []
        for note_id, score in sorted_ids:
            note = await db.fetch_one(
                "SELECT id, title, synthesis, source_type, created_at FROM notes WHERE id = ?",
                (note_id,),
            )
            if not note:
                continue

            # Get concepts
            concepts = await db.fetch_all(
                """SELECT c.name FROM concepts c
                   JOIN note_concepts nc ON c.id = nc.concept_id
                   WHERE nc.note_id = ?""",
                (note_id,),
            )

            # Find highlight from semantic results
            highlight = None
            for sid, h in semantic_results:
                if sid == note_id:
                    highlight = h
                    break

            results.append(SearchResult(
                note_id=note["id"],
                title=note["title"],
                synthesis=note["synthesis"],
                score=score,
                highlights=highlight,
                concepts=[c["name"] for c in concepts],
                source_type=note["source_type"],
                created_at=note["created_at"],
            ))

        return results

    async def ask(self, question: str) -> dict:
        """Natural language Q&A over the knowledge base.

        1. Search for relevant notes (top 10)
        2. Feed notes as context to LLM
        3. Generate answer with citations to specific notes
        """
        from src.harness import AIOperation

        # Find relevant notes
        results = await self.search(question, limit=10)
        if not results:
            return {
                "answer": "I don't have any notes that seem relevant to that question.",
                "sources": [],
                "confidence": 0.0,
            }

        # Build context from notes
        note_texts = []
        sources = []
        for r in results:
            note = await db.fetch_one(
                "SELECT id, title, processed_content, synthesis FROM notes WHERE id = ?",
                (r.note_id,),
            )
            if not note:
                continue
            content = note["synthesis"] or (note["processed_content"] or "")[:800]
            title = note["title"] or "Untitled"
            note_texts.append(f"[{title}] (id: {note['id']})\n{content}")
            sources.append({"note_id": note["id"], "title": title, "score": r.score})

        formatted_notes = "\n\n---\n\n".join(note_texts)

        prompt = f"""You are the user's second brain. Answer their question using ONLY the
knowledge they have previously captured. If you don't have enough
information in the provided notes, say so honestly.

QUESTION: {question}

RELEVANT NOTES:
{formatted_notes}

Answer the question. Cite specific notes by their title in brackets like [Note Title].
If the notes contain conflicting information, mention both perspectives.
Keep it concise."""

        answer = await self.harness.complete(
            operation=AIOperation.REASON,
            prompt=prompt,
            system="You are the user's second brain. Only use information from the provided notes.",
            temperature=0.3,
            max_tokens=600,
        )

        return {
            "answer": answer.strip(),
            "sources": sources,
            "confidence": results[0].score if results else 0.0,
        }

    async def _semantic_search(
        self, query: str, filters: Optional[SearchFilters] = None
    ) -> list[tuple[str, str]]:
        """Returns list of (note_id, highlight_text) sorted by similarity."""
        try:
            embeddings = await self.harness.embed([query])
            if not embeddings or not embeddings[0]:
                return []

            chroma_where = None
            if filters:
                chroma_where = self._build_chroma_filter(filters)

            results = self.vector_store.search(
                query_embedding=embeddings[0],
                n_results=50,
                where=chroma_where,
            )

            if not results["ids"] or not results["ids"][0]:
                return []

            # Group by note_id, keep best score per note
            seen: dict[str, tuple[float, str]] = {}
            for i, doc_id in enumerate(results["ids"][0]):
                note_id = results["metadatas"][0][i].get("note_id")
                distance = results["distances"][0][i]
                doc_text = results["documents"][0][i] if results["documents"] else ""
                if note_id and (note_id not in seen or distance < seen[note_id][0]):
                    seen[note_id] = (distance, doc_text[:200])

            return [(nid, text) for nid, (_, text) in sorted(seen.items(), key=lambda x: x[1][0])]

        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")
            return []

    async def _fts_search(
        self, query: str, filters: Optional[SearchFilters] = None
    ) -> list[tuple[str, str]]:
        """Full-text search via FTS5. Returns (note_id, highlight_snippet)."""
        try:
            # Escape FTS5 special chars
            safe_query = query.replace('"', '""')

            sql = """
                SELECT n.id, n.title,
                       snippet(notes_fts, 1, '<mark>', '</mark>', '...', 32) as highlight
                FROM notes_fts fts
                JOIN notes n ON n.rowid = fts.rowid
                WHERE notes_fts MATCH ?
            """
            params = [f'"{safe_query}"']

            if filters and filters.source_type:
                sql += " AND n.source_type = ?"
                params.append(filters.source_type)
            if filters and filters.date_from:
                sql += " AND n.created_at >= ?"
                params.append(filters.date_from.isoformat())
            if filters and filters.date_to:
                sql += " AND n.created_at <= ?"
                params.append(filters.date_to.isoformat())

            sql += " ORDER BY rank LIMIT 50"

            rows = await db.fetch_all(sql, tuple(params))
            return [(r["id"], r.get("highlight", "")) for r in rows]

        except Exception as e:
            logger.warning(f"FTS search failed: {e}")
            return []

    async def _graph_search(self, query: str) -> list[tuple[str, str]]:
        """Find notes via concept/entity matching. Returns (note_id, reason)."""
        try:
            # Tokenize query, match against known concepts
            query_words = [w.lower().strip() for w in query.split() if len(w) > 2]
            if not query_words:
                return []

            placeholders = ",".join("?" * len(query_words))

            # Match concepts
            concept_notes = await db.fetch_all(
                f"""SELECT DISTINCT nc.note_id, c.name
                    FROM concepts c
                    JOIN note_concepts nc ON c.id = nc.concept_id
                    WHERE c.name IN ({placeholders})""",
                tuple(query_words),
            )

            # Also check for multi-word concept matches
            if len(query_words) > 1:
                full_query = query.lower().strip()
                more_notes = await db.fetch_all(
                    """SELECT DISTINCT nc.note_id, c.name
                       FROM concepts c
                       JOIN note_concepts nc ON c.id = nc.concept_id
                       WHERE c.name LIKE ?""",
                    (f"%{full_query}%",),
                )
                concept_notes.extend(more_notes)

            # Follow connections from matched notes (1-hop)
            note_ids = list({r["note_id"] for r in concept_notes})
            connected = []
            if note_ids:
                placeholders = ",".join("?" * len(note_ids))
                connected = await db.fetch_all(
                    f"""SELECT target_note_id as note_id, strength
                        FROM connections
                        WHERE source_note_id IN ({placeholders}) AND strength > 0.5
                        UNION
                        SELECT source_note_id as note_id, strength
                        FROM connections
                        WHERE target_note_id IN ({placeholders}) AND strength > 0.5""",
                    (*note_ids, *note_ids),
                )

            results = [(nid, "concept match") for nid in note_ids]
            results.extend([(r["note_id"], "connected") for r in connected])

            # Deduplicate
            seen = set()
            deduped = []
            for nid, reason in results:
                if nid not in seen:
                    seen.add(nid)
                    deduped.append((nid, reason))

            return deduped

        except Exception as e:
            logger.warning(f"Graph search failed: {e}")
            return []

    def _build_chroma_filter(self, filters: SearchFilters) -> Optional[dict]:
        conditions = []
        if filters.source_type:
            conditions.append({"source_type": {"$eq": filters.source_type}})
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
