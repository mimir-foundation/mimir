import json
import logging
from typing import Optional

from fastapi import APIRouter, Request

from src.knowledge import database as db

logger = logging.getLogger("mimir.api.settings")

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
async def get_settings():
    rows = await db.fetch_all("SELECT key, value FROM settings")
    result = {}
    for row in rows:
        try:
            result[row["key"]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            result[row["key"]] = row["value"]
    return result


@router.put("/settings")
async def update_setting(body: dict):
    key = body.get("key")
    value = body.get("value")
    if not key:
        return {"error": "key is required"}
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, json.dumps(value)),
    )
    return {"ok": True}


@router.get("/harness/health")
async def harness_health(request: Request):
    harness = request.app.state.harness
    health = await harness.health()
    return {"status": health}


@router.get("/harness/config")
async def harness_config(request: Request):
    harness = request.app.state.harness
    config = harness.config
    return {
        "embed": {"provider": config.embed.provider, "model": config.embed.model},
        "extract": {"provider": config.extract.provider, "model": config.extract.model},
        "reason": {"provider": config.reason.provider, "model": config.reason.model},
        "transcribe": {"provider": config.transcribe.provider, "model": config.transcribe.model},
    }


@router.get("/harness/presets")
async def harness_presets():
    return {
        "presets": ["local", "hybrid", "cloud", "budget"],
        "descriptions": {
            "local": "All operations run locally via Ollama (free, private)",
            "hybrid": "Embeddings + extraction local, reasoning via cloud API (best quality)",
            "cloud": "All operations via cloud APIs (highest quality, costs money)",
            "budget": "Local + cheap cloud model for reasoning (good balance)",
        },
    }


@router.post("/harness/presets/{preset_name}/apply")
async def apply_preset(request: Request, preset_name: str):
    from src.config import get_settings
    from src.harness.router import PRESETS, HarnessRouter

    if preset_name not in PRESETS:
        return {"error": f"Unknown preset: {preset_name}"}

    settings = get_settings()
    config = PRESETS[preset_name](settings)
    request.app.state.harness.reload(config)

    return {"ok": True, "preset": preset_name}
