"""Async API client for the Mimir backend."""

from typing import Any

import httpx


class MimirClient:
    def __init__(self, base_url: str, api_key: str | None = None):
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(
            base_url=base_url, headers=headers, timeout=30.0
        )

    async def aclose(self):
        await self._http.aclose()

    async def _get(self, path: str, **params) -> dict:
        resp = await self._http.get(path, params={k: v for k, v in params.items() if v is not None})
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json: Any = None) -> dict:
        resp = await self._http.post(path, json=json)
        resp.raise_for_status()
        return resp.json()

    async def _put(self, path: str, json: Any = None) -> dict:
        resp = await self._http.put(path, json=json)
        resp.raise_for_status()
        return resp.json()

    async def _delete(self, path: str) -> dict:
        resp = await self._http.delete(path)
        resp.raise_for_status()
        return resp.json()

    # Health
    async def health(self) -> dict:
        return await self._get("/api/health")

    # Stats
    async def get_stats(self) -> dict:
        return await self._get("/api/stats")

    # Capture
    async def capture_note(self, content: str, title: str | None = None, tags: list[str] | None = None) -> dict:
        return await self._post("/api/capture/note", json={"content": content, "title": title, "tags": tags})

    async def capture_url(self, url: str, context: str | None = None) -> dict:
        return await self._post("/api/capture/url", json={"url": url, "context": context})

    async def capture_clipboard(self, content: str) -> dict:
        return await self._post("/api/capture/clipboard", json={"content": content, "source_type": "clipboard"})

    # Search
    async def search(self, q: str, mode: str = "search", source_type: str | None = None, limit: int = 20) -> dict:
        return await self._get("/api/search", q=q, mode=mode, source_type=source_type, limit=limit)

    # Notes
    async def get_notes(self, sort: str = "recent", limit: int = 20, offset: int = 0,
                        is_starred: bool | None = None, processing_status: str | None = None) -> dict:
        params = {"sort": sort, "limit": limit, "offset": offset}
        if is_starred is not None:
            params["is_starred"] = str(is_starred).lower()
        if processing_status:
            params["processing_status"] = processing_status
        return await self._get("/api/notes", **params)

    async def get_note(self, note_id: str) -> dict:
        return await self._get(f"/api/notes/{note_id}")

    async def update_note(self, note_id: str, data: dict) -> dict:
        return await self._put(f"/api/notes/{note_id}", json=data)

    async def delete_note(self, note_id: str) -> dict:
        return await self._delete(f"/api/notes/{note_id}")

    # Concepts & Entities
    async def get_concepts(self) -> dict:
        return await self._get("/api/concepts")

    async def get_concept(self, concept_id: str) -> dict:
        return await self._get(f"/api/concepts/{concept_id}")

    async def get_entities(self, entity_type: str | None = None) -> dict:
        return await self._get("/api/entities", entity_type=entity_type)

    async def get_entity(self, entity_id: str) -> dict:
        return await self._get(f"/api/entities/{entity_id}")

    # Connections
    async def get_connections(self, note_id: str | None = None, connection_type: str | None = None,
                               min_strength: float = 0.0) -> dict:
        return await self._get("/api/connections", note_id=note_id,
                               connection_type=connection_type, min_strength=min_strength)

    # Agent
    async def get_brief(self, date: str | None = None) -> dict:
        return await self._get("/api/agent/brief", date=date)

    async def generate_brief(self) -> dict:
        return await self._post("/api/agent/brief/generate")

    async def get_resurface(self, limit: int = 10) -> dict:
        return await self._get("/api/agent/resurface", limit=limit)

    async def click_resurface(self, item_id: str) -> dict:
        return await self._post(f"/api/agent/resurface/{item_id}/click")

    async def dismiss_resurface(self, item_id: str) -> dict:
        return await self._post(f"/api/agent/resurface/{item_id}/dismiss")

    async def get_activity(self, limit: int = 20) -> dict:
        return await self._get("/api/agent/activity", limit=limit)

    async def get_interests(self) -> dict:
        return await self._get("/api/agent/interests")

    async def trigger_deep_scan(self) -> dict:
        return await self._post("/api/agent/deep-scan")

    async def trigger_taxonomy_rebuild(self) -> dict:
        return await self._post("/api/agent/taxonomy-rebuild")

    # Settings & Harness
    async def get_settings(self) -> dict:
        return await self._get("/api/settings")

    async def put_setting(self, key: str, value: Any) -> dict:
        return await self._put("/api/settings", json={"key": key, "value": value})

    async def get_harness_config(self) -> dict:
        return await self._get("/api/harness/config")

    async def get_harness_health(self) -> dict:
        return await self._get("/api/harness/health")

    async def apply_preset(self, name: str) -> dict:
        return await self._post(f"/api/harness/presets/{name}/apply")

    # Export
    async def export_json(self) -> bytes:
        resp = await self._http.get("/api/export/json")
        resp.raise_for_status()
        return resp.content

    async def export_markdown(self) -> bytes:
        resp = await self._http.get("/api/export/markdown")
        resp.raise_for_status()
        return resp.content
