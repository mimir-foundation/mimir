def build_extraction_prompt(processed_content: str, source_type: str, context: str = "") -> str:
    context_line = f"\nUSER CONTEXT: {context}" if context else ""
    return f"""You are a knowledge librarian. Analyze the following content and extract structured metadata.

CONTENT:
{processed_content[:3000]}

SOURCE TYPE: {source_type}{context_line}

Respond in JSON only:
{{
  "suggested_title": "concise descriptive title if none exists",
  "concepts": ["concept1", "concept2"],
  "entities": [
    {{"name": "...", "type": "person|company|project|place|book|tool|event", "role": "how they relate to this content"}}
  ],
  "key_claims": ["core idea 1", "core idea 2"],
  "content_type": "reference|opinion|tutorial|story|idea|question|quote|data",
  "temporal_relevance": "evergreen|time-sensitive|historical",
  "expiry_hint": null,
  "action_items": ["implicit or explicit todo"]
}}"""


def build_link_validation_prompt(
    note_a_title: str, note_a_content: str, note_a_concepts: str,
    note_b_title: str, note_b_content: str, note_b_concepts: str,
) -> str:
    return f"""You are a knowledge connector. Given two pieces of content, determine if and how they are meaningfully connected.

NOTE A (new):
Title: {note_a_title}
Content: {note_a_content[:500]}
Concepts: {note_a_concepts}

NOTE B (existing):
Title: {note_b_title}
Content: {note_b_content[:500]}
Concepts: {note_b_concepts}

Are these meaningfully connected beyond surface-level topic overlap?
If yes, respond in JSON:
{{
  "connected": true,
  "type": "related|builds_on|contradicts|supports|inspired_by",
  "strength": 0.5,
  "explanation": "One sentence explaining the connection"
}}
If not meaningfully connected:
{{"connected": false}}"""


def build_synthesis_prompt(
    processed_content: str,
    key_claims: list[str],
    connections_text: str = "None found yet.",
) -> str:
    claims = ", ".join(key_claims) if key_claims else "None extracted"
    return f"""You are the user's second brain. Write a 2-4 sentence synthesis of this content.
Write in second person ("you"), casual tone, focused on the key insight and why it matters.
If there are connections to existing notes, weave them in naturally.

CONTENT:
{processed_content[:1500]}

KEY CLAIMS: {claims}

CONNECTED NOTES:
{connections_text}

Write the synthesis. No preamble. Just the synthesis paragraph."""
