import logging

from src.knowledge.models import Chunk
from src.knowledge.vector_store import VectorStore

logger = logging.getLogger("mimir.processing.embedder")


async def embed(
    chunks: list[Chunk],
    source_type: str,
    created_at: str,
    concepts: list[str],
    entities: list[str],
    harness,
    vector_store: VectorStore,
) -> None:
    if not chunks:
        return

    texts = [c.text for c in chunks]
    embeddings = await harness.embed(texts)

    ids = [f"{c.note_id}__{c.chunk_index}" for c in chunks]
    metadatas = [
        {
            "note_id": c.note_id,
            "chunk_index": c.chunk_index,
            "source_type": source_type,
            "created_at": created_at,
            "concepts": ",".join(concepts),
            "entities": ",".join(entities),
            "word_count": len(c.text.split()),
        }
        for c in chunks
    ]

    vector_store.add_chunks(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
    logger.info(f"Embedded {len(chunks)} chunks for note {chunks[0].note_id}")
