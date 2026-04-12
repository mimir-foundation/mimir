"""MCP server — exposes Mimir tools to Claude Code and other MCP clients."""

import json
import logging
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.routing import Mount, Route

logger = logging.getLogger("mimir.mcp")

BACKEND_URL = "http://localhost:8000"

server = Server("mimir-mcp")


def _text(content: str) -> list[TextContent]:
    return [TextContent(type="text", text=content)]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="mimir_search",
            description="Search your Mimir knowledge base using hybrid search (semantic + full-text + graph). Returns matching notes ranked by relevance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="mimir_ask",
            description="Ask a natural language question over your Mimir knowledge base. Returns an LLM-generated answer with source citations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask",
                    },
                },
                "required": ["question"],
            },
        ),
        Tool(
            name="mimir_capture",
            description="Capture a note or URL into Mimir for processing and indexing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Text content or URL to capture",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional title for the note",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="mimir_recall",
            description="Get a specific note by ID from Mimir, including its concepts, entities, and connections.",
            inputSchema={
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": "The note ID to retrieve",
                    },
                },
                "required": ["note_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30) as client:
            if name == "mimir_search":
                query = arguments["query"]
                limit = arguments.get("limit", 10)
                resp = await client.get(
                    "/api/search",
                    params={"q": query, "limit": limit},
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    return _text(f"No results found for: {query}")
                lines = []
                for r in results:
                    title = r.get("title") or "Untitled"
                    score = r.get("score", 0)
                    synthesis = (r.get("synthesis") or "")[:200]
                    concepts = ", ".join(r.get("concepts", []))
                    lines.append(
                        f"- **{title}** (score: {score:.3f})\n"
                        f"  ID: {r['note_id']}\n"
                        f"  {synthesis}\n"
                        f"  Concepts: {concepts}"
                    )
                return _text(f"Found {len(results)} results:\n\n" + "\n\n".join(lines))

            elif name == "mimir_ask":
                question = arguments["question"]
                resp = await client.get(
                    "/api/search",
                    params={"q": question, "mode": "ask"},
                )
                resp.raise_for_status()
                data = resp.json()
                answer = data.get("answer", "No answer.")
                sources = data.get("sources", [])
                source_text = ""
                if sources:
                    titles = [s["title"] for s in sources[:5]]
                    source_text = "\n\nSources: " + ", ".join(titles)
                return _text(f"{answer}{source_text}")

            elif name == "mimir_capture":
                content = arguments["content"]
                title = arguments.get("title")
                is_url = content.strip().startswith(("http://", "https://"))
                if is_url:
                    body: dict[str, Any] = {"url": content}
                    resp = await client.post("/api/capture/url", json=body)
                else:
                    body = {"content": content}
                    if title:
                        body["title"] = title
                    resp = await client.post("/api/capture/note", json=body)
                resp.raise_for_status()
                data = resp.json()
                return _text(
                    f"Captured! Note ID: {data.get('note_id', 'unknown')}\n"
                    f"Status: {data.get('status', 'pending')}"
                )

            elif name == "mimir_recall":
                note_id = arguments["note_id"]
                resp = await client.get(f"/api/notes/{note_id}")
                resp.raise_for_status()
                data = resp.json()
                title = data.get("title") or "Untitled"
                synthesis = data.get("synthesis") or ""
                content = data.get("processed_content") or data.get("raw_content", "")
                concepts = [c["name"] for c in data.get("concepts", [])]
                entities = [f"{e['name']} ({e['entity_type']})" for e in data.get("entities", [])]
                connections = [
                    f"{c.get('target_title', 'Unknown')} ({c['connection_type']}, strength: {c['strength']:.2f})"
                    for c in data.get("connections", [])
                ]
                parts = [
                    f"# {title}",
                    f"Source: {data.get('source_type', 'unknown')} | Created: {data.get('created_at', '')}",
                ]
                if synthesis:
                    parts.append(f"\n## Synthesis\n{synthesis}")
                if content:
                    parts.append(f"\n## Content\n{content[:2000]}")
                if concepts:
                    parts.append(f"\n## Concepts\n{', '.join(concepts)}")
                if entities:
                    parts.append(f"\n## Entities\n{', '.join(entities)}")
                if connections:
                    parts.append(f"\n## Connections\n" + "\n".join(f"- {c}" for c in connections))
                return _text("\n".join(parts))

            else:
                return _text(f"Unknown tool: {name}")

    except httpx.HTTPStatusError as e:
        return _text(f"API error: {e.response.status_code} {e.response.text}")
    except Exception as e:
        logger.error(f"MCP tool error: {e}", exc_info=True)
        return _text(f"Error: {e}")


def create_mcp_app() -> Starlette:
    """Create a Starlette app that serves the MCP SSE transport."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(
                streams[0], streams[1], server.create_initialization_options()
            )

    return Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )
