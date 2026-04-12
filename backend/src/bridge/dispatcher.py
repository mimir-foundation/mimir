"""Outbound dispatcher — sends proactive notifications to messaging platforms."""

import json
import logging
from typing import Optional

from src.bridge.adapters.base import PlatformAdapter
from src.bridge.models import OutboundMessage, Platform
from src.knowledge import database as db
from src.knowledge.models import new_id

logger = logging.getLogger("mimir.bridge.dispatcher")

_dispatcher: Optional["OutboundDispatcher"] = None


def get_dispatcher() -> Optional["OutboundDispatcher"]:
    return _dispatcher


def set_dispatcher(d: Optional["OutboundDispatcher"]) -> None:
    global _dispatcher
    _dispatcher = d


class OutboundDispatcher:
    def __init__(self, adapters: dict[str, PlatformAdapter]):
        self._adapters = adapters

    async def send_daily_brief(self, content: str) -> None:
        """Send the daily brief to all configured brief channels."""
        targets = await self._get_targets("daily_brief")
        for platform, recipient_id in targets:
            adapter = self._adapters.get(platform)
            if not adapter:
                continue
            text = adapter.format_text(f"**Mimir Daily Brief**\n\n{content}")
            msg = OutboundMessage(
                platform=platform, recipient_id=recipient_id, text=text
            )
            ok = await adapter.send(msg)
            await self._log_outbound(platform, "daily_brief", text, ok)

    async def send_connection_alert(
        self, source_title: str, target_title: str, explanation: str
    ) -> None:
        targets = await self._get_targets("connection_alert")
        text = (
            f"**New Connection**\n\n"
            f'"{source_title}" ↔ "{target_title}"\n\n{explanation}'
        )
        for platform, recipient_id in targets:
            adapter = self._adapters.get(platform)
            if not adapter:
                continue
            formatted = adapter.format_text(text)
            msg = OutboundMessage(
                platform=platform, recipient_id=recipient_id, text=formatted
            )
            ok = await adapter.send(msg)
            await self._log_outbound(platform, "connection_alert", text, ok)

    async def send_resurface(
        self, note_title: str, reason: str, synthesis: str
    ) -> None:
        targets = await self._get_targets("resurface")
        text = f"**Resurface: {note_title}**\n\n{reason}"
        if synthesis:
            text += f"\n\n{synthesis}"
        for platform, recipient_id in targets:
            adapter = self._adapters.get(platform)
            if not adapter:
                continue
            formatted = adapter.format_text(text)
            msg = OutboundMessage(
                platform=platform, recipient_id=recipient_id, text=formatted
            )
            ok = await adapter.send(msg)
            await self._log_outbound(platform, "resurface", text, ok)

    async def _get_targets(self, channel_type: str) -> list[tuple[str, str]]:
        """Load outbound targets from bridge config in DB."""
        row = await db.fetch_one("SELECT value FROM settings WHERE key = 'bridge'")
        if not row:
            return []
        try:
            config = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return []

        channels = config.get("outbound_channels", {}).get(channel_type, [])
        targets = []
        for entry in channels:
            # Each entry is {"platform": "telegram", "recipient_id": "123456"}
            if isinstance(entry, dict):
                targets.append((entry["platform"], entry["recipient_id"]))
            elif isinstance(entry, str):
                # Legacy: "telegram:123456"
                parts = entry.split(":", 1)
                if len(parts) == 2:
                    targets.append((parts[0], parts[1]))

        # Skip non-platform targets (e.g. "dashboard") that aren't sendable
        targets = [(p, r) for p, r in targets if p in self._adapters]

        # Fallback: if no explicit targets, use platform user_id from config
        if not targets:
            for platform_name in (Platform.TELEGRAM, Platform.MATTERMOST):
                pcfg = config.get(platform_name, {})
                uid = pcfg.get("user_id") or pcfg.get("channel_id")
                if uid and platform_name in self._adapters:
                    targets.append((platform_name, uid))

        # Final fallback: check env vars directly
        if not targets:
            from src.config import get_settings
            settings = get_settings()
            if settings.telegram_user_id and Platform.TELEGRAM in self._adapters:
                targets.append((Platform.TELEGRAM, settings.telegram_user_id))
            if settings.mattermost_channel_id and Platform.MATTERMOST in self._adapters:
                targets.append((Platform.MATTERMOST, settings.mattermost_channel_id))

        return targets

    async def _log_outbound(
        self, platform: str, intent: str, text: str, success: bool
    ) -> None:
        try:
            await db.execute(
                """INSERT INTO bridge_message_log
                   (id, platform, direction, intent, text, status)
                   VALUES (?, ?, 'outbound', ?, ?, ?)""",
                (
                    new_id(),
                    platform,
                    intent,
                    text[:500],
                    "ok" if success else "error",
                ),
            )
        except Exception as e:
            logger.warning(f"Failed to log outbound message: {e}")
