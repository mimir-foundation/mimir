import logging
from typing import Optional

import chromadb

logger = logging.getLogger("mimir.vector")

COLLECTION_NAME = "mimir_notes"


class VectorStore:
    def __init__(self, persist_path: str):
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Vector store initialized with {self.collection.count()} documents")

    def add_chunks(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 20,
        where: Optional[dict] = None,
    ) -> dict:
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, self.collection.count() or 1),
        }
        if where:
            kwargs["where"] = where
        if kwargs["n_results"] < 1:
            return {"ids": [[]], "distances": [[]], "metadatas": [[]], "documents": [[]]}
        return self.collection.query(**kwargs)

    def delete_note(self, note_id: str) -> None:
        results = self.collection.get(where={"note_id": note_id})
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} chunks for note {note_id}")

    def get_note_chunks(self, note_id: str) -> dict:
        return self.collection.get(where={"note_id": note_id}, include=["documents", "metadatas", "embeddings"])

    def count(self) -> int:
        return self.collection.count()
