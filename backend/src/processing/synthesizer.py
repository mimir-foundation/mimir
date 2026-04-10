import logging

from src.harness import AIOperation
from src.knowledge.models import ExtractionResult
from src.processing.prompts import build_synthesis_prompt

logger = logging.getLogger("mimir.processing.synthesizer")


async def synthesize(
    processed_content: str,
    extraction: ExtractionResult,
    connections: list[dict],
    harness,
) -> str:
    # Build connections text
    if connections:
        conn_lines = []
        for c in connections:
            conn_lines.append(f"- [{c.get('type', 'related')}] {c.get('explanation', 'Related note')}")
        connections_text = "\n".join(conn_lines)
    else:
        connections_text = "None found yet."

    prompt = build_synthesis_prompt(
        processed_content=processed_content,
        key_claims=extraction.key_claims,
        connections_text=connections_text,
    )

    synthesis = await harness.complete(
        operation=AIOperation.REASON,
        prompt=prompt,
        system="You are the user's second brain. Be concise and insightful.",
        temperature=0.5,
        max_tokens=300,
    )

    return synthesis.strip()
