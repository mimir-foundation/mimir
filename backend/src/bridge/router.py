"""Bridge routers and lifecycle management."""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from fastapi import APIRouter, Request, Response

from src.bridge.adapters.base import PlatformAdapter
from src.bridge.adapters.mattermost import MattermostAdapter
from src.bridge.adapters.telegram import TelegramAdapter
from src.bridge.dispatcher import OutboundDispatcher, set_dispatcher
from src.bridge.handler import MessageHandler
from src.bridge.models import OutboundMessage, Platform
from src.bridge.security import BridgeSecurity
from src.knowledge import database as db

logger = logging.getLogger("mimir.bridge.router")

# --- Webhook router (no auth — receives external webhooks) ---

webhook_router = APIRouter(prefix="/bridge", tags=["bridge-webhook"])

# --- Management router (normal auth) ---

management_router = APIRouter(prefix="/api/bridge", tags=["bridge-management"])

# Module-level state set by init_bridge
_bridge_state: Optional["BridgeState"] = None


@dataclass
class BridgeState:
    adapters: dict[str, PlatformAdapter] = field(default_factory=dict)
    handler: Optional[MessageHandler] = None
    security: Optional[BridgeSecurity] = None
    dispatcher: Optional[OutboundDispatcher] = None

    async def shutdown(self) -> None:
        for adapter in self.adapters.values():
            try:
                await adapter.close()
            except Exception as e:
                logger.warning(f"Adapter close error: {e}")
        set_dispatcher(None)


# --- Init ---


async def init_bridge(app) -> Optional[BridgeState]:
    """Initialize messaging bridge from DB settings + env vars."""
    global _bridge_state

    from src.config import get_settings

    settings = get_settings()

    # Load bridge config from DB
    row = await db.fetch_one("SELECT value FROM settings WHERE key = 'bridge'")
    if row:
        try:
            config = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            config = {}
    else:
        config = {}

    # Overlay env vars
    if settings.telegram_bot_token:
        config.setdefault("telegram", {})["bot_token"] = settings.telegram_bot_token
    if settings.telegram_user_id:
        config.setdefault("telegram", {})["user_id"] = settings.telegram_user_id
    if settings.bridge_webhook_base_url:
        config.setdefault("telegram", {})[
            "webhook_base_url"
        ] = settings.bridge_webhook_base_url
    if settings.mattermost_url:
        config.setdefault("mattermost", {})["url"] = settings.mattermost_url
    if settings.mattermost_bot_token:
        config.setdefault("mattermost", {})["bot_token"] = settings.mattermost_bot_token
    if settings.mattermost_channel_id:
        config.setdefault("mattermost", {})[
            "channel_id"
        ] = settings.mattermost_channel_id

    enabled = config.get("enabled_platforms", [])
    adapters: dict[str, PlatformAdapter] = {}

    # Telegram
    tg_cfg = config.get("telegram", {})
    tg_token = tg_cfg.get("bot_token", "")
    if tg_token and (not enabled or Platform.TELEGRAM in enabled):
        tg_adapter = TelegramAdapter(
            bot_token=tg_token,
            webhook_base_url=tg_cfg.get("webhook_base_url", ""),
        )
        adapters[Platform.TELEGRAM] = tg_adapter
        logger.info("Telegram adapter created")

    # Mattermost
    mm_cfg = config.get("mattermost", {})
    mm_token = mm_cfg.get("bot_token", "")
    mm_url = mm_cfg.get("url", "")
    if mm_token and mm_url and (not enabled or Platform.MATTERMOST in enabled):
        mm_adapter = MattermostAdapter(
            server_url=mm_url,
            bot_token=mm_token,
            channel_id=mm_cfg.get("channel_id", ""),
        )
        adapters[Platform.MATTERMOST] = mm_adapter
        logger.info("Mattermost adapter created")

    if not adapters:
        logger.info("No messaging bridge platforms configured")
        _bridge_state = None
        return None

    # Security
    security = BridgeSecurity(config.get("security", {}))

    # Handler
    handler = MessageHandler(app.state.harness, app.state.vector_store)

    # Telegram: webhook or polling
    tg = adapters.get(Platform.TELEGRAM)
    if isinstance(tg, TelegramAdapter):
        if tg._webhook_base_url:
            await tg.register_webhook()
        else:
            # Set up polling callback
            async def _on_telegram_update(update: dict):
                msg = tg.normalize(update)
                if msg and security.is_authorized(msg):
                    resp = await handler.handle(msg, tg)
                    formatted = tg.format_text(resp.text)
                    resp.text = formatted
                    resp.parse_mode = "MarkdownV2"
                    await tg.send(resp)

            tg._on_update = _on_telegram_update
            tg.start_polling()

    # Dispatcher
    dispatcher = OutboundDispatcher(adapters)
    set_dispatcher(dispatcher)

    state = BridgeState(
        adapters=adapters,
        handler=handler,
        security=security,
        dispatcher=dispatcher,
    )
    _bridge_state = state
    return state


async def reload_bridge(app) -> Optional[BridgeState]:
    """Tear down existing bridge and re-initialize from current config."""
    global _bridge_state
    if _bridge_state:
        await _bridge_state.shutdown()
        _bridge_state = None
    return await init_bridge(app)


# ===== Webhook endpoints =====


@webhook_router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram webhook updates."""
    if not _bridge_state or Platform.TELEGRAM not in _bridge_state.adapters:
        return Response(status_code=404, content="Telegram not configured")

    adapter: TelegramAdapter = _bridge_state.adapters[Platform.TELEGRAM]  # type: ignore
    payload = await request.json()

    msg = adapter.normalize(payload)
    if not msg:
        return {"ok": True}

    if not _bridge_state.security.is_authorized(msg):
        return {"ok": True}  # Silent drop per Telegram convention

    resp = await _bridge_state.handler.handle(msg, adapter)
    formatted = adapter.format_text(resp.text)
    resp.text = formatted
    resp.parse_mode = "MarkdownV2"
    await adapter.send(resp)
    return {"ok": True}


@webhook_router.post("/mattermost/webhook")
async def mattermost_webhook(request: Request):
    """Receive Mattermost outgoing webhook."""
    if not _bridge_state or Platform.MATTERMOST not in _bridge_state.adapters:
        return Response(status_code=404, content="Mattermost not configured")

    adapter: MattermostAdapter = _bridge_state.adapters[Platform.MATTERMOST]  # type: ignore
    payload = await request.json()

    # Verify token if configured
    row = await db.fetch_one("SELECT value FROM settings WHERE key = 'bridge'")
    if row:
        try:
            cfg = json.loads(row["value"])
            expected_token = cfg.get("mattermost", {}).get("webhook_token", "")
            if expected_token:
                incoming_token = payload.get("token", "")
                if not adapter.verify_token(incoming_token, expected_token):
                    return Response(status_code=401, content="Invalid token")
        except (json.JSONDecodeError, TypeError):
            pass

    msg = adapter.normalize(payload)
    if not msg:
        return {"text": ""}

    if not _bridge_state.security.is_authorized(msg):
        return {"text": ""}

    resp = await _bridge_state.handler.handle(msg, adapter)

    # Mattermost outgoing webhooks expect a JSON response with "text"
    # to reply inline. Also send via API for richer formatting.
    await adapter.send(resp)
    return {"text": ""}


# ===== Management endpoints =====


@management_router.get("/status")
async def bridge_status():
    """Check connection status for each configured platform."""
    results = {}
    if not _bridge_state:
        return {"configured": False, "platforms": {}}

    for name, adapter in _bridge_state.adapters.items():
        try:
            me = await adapter.get_me()
            results[name] = {"connected": me is not None, "info": me}
        except Exception as e:
            results[name] = {"connected": False, "error": str(e)}

    return {"configured": True, "platforms": results}


@management_router.get("/config")
async def bridge_config():
    """Read bridge settings from DB."""
    row = await db.fetch_one("SELECT value FROM settings WHERE key = 'bridge'")
    if not row:
        return {}
    try:
        config = json.loads(row["value"])
        # Mask tokens in response
        for platform in ("telegram", "mattermost"):
            if platform in config:
                token = config[platform].get("bot_token", "")
                if token:
                    config[platform]["bot_token"] = token[:4] + "..." + token[-4:] if len(token) > 8 else "***"
        return config
    except (json.JSONDecodeError, TypeError):
        return {}


@management_router.put("/config")
async def update_bridge_config(request: Request):
    """Update bridge settings and hot-reload the bridge."""
    body = await request.json()
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("bridge", json.dumps(body)),
    )

    # Hot-reload: tear down and re-init with new config
    try:
        new_state = await reload_bridge(request.app)
        request.app.state.bridge = new_state
        platforms = list(new_state.adapters.keys()) if new_state else []
        logger.info(f"Bridge hot-reloaded: {platforms}")
        return {"status": "reloaded", "platforms": platforms}
    except Exception as e:
        logger.error(f"Bridge reload failed: {e}")
        return {"status": "saved", "error": str(e), "note": "Config saved but reload failed. Try restarting."}


@management_router.post("/test/{platform}")
async def test_bridge(platform: str):
    """Send a test message to the specified platform."""
    if not _bridge_state or platform not in _bridge_state.adapters:
        return {"success": False, "error": f"{platform} not configured"}

    adapter = _bridge_state.adapters[platform]

    # Determine recipient
    row = await db.fetch_one("SELECT value FROM settings WHERE key = 'bridge'")
    recipient = ""
    if row:
        try:
            cfg = json.loads(row["value"])
            pcfg = cfg.get(platform, {})
            recipient = pcfg.get("user_id") or pcfg.get("channel_id", "")
        except (json.JSONDecodeError, TypeError):
            pass

    if not recipient:
        return {"success": False, "error": "No recipient configured"}

    msg = OutboundMessage(
        platform=platform,
        recipient_id=recipient,
        text=adapter.format_text("Mimir test message — your bridge is working!"),
    )
    ok = await adapter.send(msg)
    return {"success": ok}


@management_router.get("/log")
async def bridge_log(limit: int = 50, offset: int = 0):
    """Query bridge message log."""
    rows = await db.fetch_all(
        "SELECT * FROM bridge_message_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return rows
