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
    from src.harness.router import PRESETS, load_harness_config_with_db_keys

    if preset_name not in PRESETS:
        return {"error": f"Unknown preset: {preset_name}"}

    settings = get_settings()
    db_keys = await _load_api_keys()
    config = load_harness_config_with_db_keys(settings, preset_name, db_keys)
    request.app.state.harness.reload(config)

    return {"ok": True, "preset": preset_name}


@router.get("/harness/api-keys")
async def get_api_keys():
    """Get configured API keys (masked)."""
    row = await db.fetch_one("SELECT value FROM settings WHERE key = 'api_keys'")
    if not row:
        return {"anthropic": "", "openai": "", "google": ""}
    try:
        keys = json.loads(row["value"])
        # Mask keys in response
        masked = {}
        for provider, key in keys.items():
            if key and len(key) > 8:
                masked[provider] = key[:4] + "..." + key[-4:]
            elif key:
                masked[provider] = "***"
            else:
                masked[provider] = ""
        return masked
    except (json.JSONDecodeError, TypeError):
        return {"anthropic": "", "openai": "", "google": ""}


@router.put("/harness/api-keys")
async def update_api_keys(request: Request, body: dict):
    """Save API keys and hot-reload the harness.

    Only keys present in the request body are updated.
    Omitted keys keep their existing values.
    """
    # Load existing keys first
    existing = await _load_api_keys()
    keys = {
        "anthropic": existing.get("anthropic", ""),
        "openai": existing.get("openai", ""),
        "google": existing.get("google", ""),
    }
    # Only overwrite keys that were explicitly provided
    for provider in ("anthropic", "openai", "google"):
        if provider in body and body[provider]:
            keys[provider] = body[provider]
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("api_keys", json.dumps(keys)),
    )

    # Hot-reload harness with new keys
    try:
        from src.config import get_settings
        from src.harness.router import load_harness_config_with_db_keys

        settings = get_settings()
        config = load_harness_config_with_db_keys(settings, settings.harness_preset, keys)
        request.app.state.harness.reload(config)
        return {"ok": True, "reloaded": True}
    except Exception as e:
        logger.warning(f"Harness reload after key update failed: {e}")
        return {"ok": True, "reloaded": False, "error": str(e)}


async def _load_api_keys() -> dict:
    """Load raw API keys from DB settings."""
    row = await db.fetch_one("SELECT value FROM settings WHERE key = 'api_keys'")
    if not row:
        return {}
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return {}
