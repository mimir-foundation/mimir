import re
import logging

from src.knowledge.models import Chunk

logger = logging.getLogger("mimir.processing.chunker")

TARGET_TOKENS = 400
OVERLAP_TOKENS = 50


def _estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def chunk(note_id: str, content: str) -> list[Chunk]:
    if not content or not content.strip():
        return []

    word_count = len(content.split())

    # Short notes: single chunk
    if word_count < 500:
        return [Chunk(
            text=content,
            chunk_index=0,
            note_id=note_id,
            token_count=_estimate_tokens(content),
        )]

    # Split into paragraphs
    paragraphs = re.split(r"\n{2,}", content)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_text = ""
    overlap_text = ""

    for para in paragraphs:
        candidate = (current_text + "\n\n" + para).strip() if current_text else para

        if _estimate_tokens(candidate) > TARGET_TOKENS * 1.5 and current_text:
            # Emit current chunk
            chunks.append(Chunk(
                text=current_text.strip(),
                chunk_index=len(chunks),
                note_id=note_id,
                token_count=_estimate_tokens(current_text),
            ))

            # Build overlap from end of current chunk
            sentences = _split_sentences(current_text)
            overlap_parts = []
            overlap_tokens = 0
            for s in reversed(sentences):
                t = _estimate_tokens(s)
                if overlap_tokens + t > OVERLAP_TOKENS:
                    break
                overlap_parts.insert(0, s)
                overlap_tokens += t
            overlap_text = " ".join(overlap_parts)

            current_text = (overlap_text + "\n\n" + para).strip() if overlap_text else para
        else:
            current_text = candidate

    # Emit final chunk
    if current_text.strip():
        chunks.append(Chunk(
            text=current_text.strip(),
            chunk_index=len(chunks),
            note_id=note_id,
            token_count=_estimate_tokens(current_text),
        ))

    return chunks
