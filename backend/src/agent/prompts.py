"""LLM prompt templates for agent behaviors."""


def build_brief_prompt(
    date: str,
    recent_notes: str,
    recent_count: int,
    new_connections: str,
    resurface_items: str,
    dangling_items: str,
    historical_items: str,
) -> str:
    return f"""You are Mimir, a personal knowledge assistant. Write a brief daily digest.
Be conversational and concise.

TODAY'S DATE: {date}

RECENTLY CAPTURED ({recent_count} notes):
{recent_notes}

NEW CONNECTIONS FOUND:
{new_connections}

RESURFACED NOTES (relevant to recent activity):
{resurface_items}

DANGLING THREADS (saved but never revisited, 30+ days old):
{dangling_items}

THIS DAY LAST YEAR:
{historical_items}

Write a friendly 150-300 word digest. Lead with the most interesting
connection or resurface. Don't list everything — curate. End with one
question or prompt that might spark the user's thinking."""


def build_taxonomy_merge_prompt(concepts: list[dict]) -> str:
    concept_list = "\n".join(
        f"- {c['name']} ({c['note_count']} notes)"
        for c in concepts
    )
    return f"""You are a knowledge librarian organizing a taxonomy. Review these concepts and suggest merges and parent-child relationships.

CONCEPTS:
{concept_list}

For each group that should be merged (near-duplicates), output:
{{"merges": [{{"keep": "canonical name", "merge": ["duplicate1", "duplicate2"]}}]}}

For parent-child relationships, output:
{{"hierarchies": [{{"parent": "parent concept", "children": ["child1", "child2"]}}]}}

Respond with valid JSON only. If no changes needed, respond: {{"merges": [], "hierarchies": []}}"""
