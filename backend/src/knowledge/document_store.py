import os
import logging
from pathlib import Path

logger = logging.getLogger("mimir.documents")


class DocumentStore:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def store_document(self, note_id: str, file_bytes: bytes, filename: str) -> str:
        note_dir = self.base_path / note_id
        note_dir.mkdir(parents=True, exist_ok=True)
        file_path = note_dir / filename
        file_path.write_bytes(file_bytes)
        logger.info(f"Stored document: {file_path}")
        return str(file_path)

    def get_document_path(self, note_id: str) -> Path:
        return self.base_path / note_id

    def get_document_files(self, note_id: str) -> list[Path]:
        note_dir = self.base_path / note_id
        if not note_dir.exists():
            return []
        return list(note_dir.iterdir())

    def delete_document(self, note_id: str) -> None:
        import shutil
        note_dir = self.base_path / note_id
        if note_dir.exists():
            shutil.rmtree(note_dir)
            logger.info(f"Deleted documents for note: {note_id}")
