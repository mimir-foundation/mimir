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
  "action_items": ["implicit or explicit todo"],
  "actions": [
    {{
      "action_type": "calendar_event|reminder|task|contact|follow_up",
      "title": "event or task title",
      "start": "ISO 8601 datetime if applicable (e.g. 2026-04-25T14:00:00)",
      "end": "ISO 8601 datetime if applicable",
      "location": "place if applicable",
      "description": "brief description",
      "recurring": "null for one-time, or 'daily'|'weekly'|'monthly'|'yearly' if recurring",
      "due_date": "ISO 8601 date for tasks/reminders",
      "contact_info": null
    }}
  ]
}}

IMPORTANT for the "actions" field:
- Only include actions when the content contains CLEAR, SPECIFIC dates, events, deadlines, tasks, reminders, or contact details.
- For calendar events: extract the exact date and time. If the year is not stated, assume the next occurrence.
- For tasks/reminders: extract due dates if mentioned.
- For contacts: extract name, email, phone, company into contact_info.
- If no actionable content is found, return an empty actions array.
- Do NOT fabricate dates or events that are not explicitly stated in the content."""


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
