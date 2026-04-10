"""Mattermost adapter — Bot API integration."""

import logging
from typing import Optional

import httpx

from src.bridge.adapters.base import PlatformAdapter
from src.bridge.models import InboundMessage, MessageType, OutboundMessage, Platform

logger = logging.getLogger("mimir.bridge.mattermost")


class MattermostAdapter(PlatformAdapter):
    platform = Platform.MATTERMOST

    def __init__(self, server_url: str, bot_token: str, channel_id: str = ""):
        self._url = server_url.rstrip("/")
        self._token = bot_token
        self._channel_id = channel_id
        self._client = httpx.AsyncClient(
            base_url=self._url,
            headers={"Authorization": f"Bearer {bot_token}"},
            timeout=30.0,
        )

    # --- Normalize inbound (from outgoing webhook) ---

    def normalize(self, payload: dict) -> Optional[InboundMessage]:
        """Convert a Mattermost outgoing webhook payload into an InboundMessage."""
        text = payload.get("text", "")
        user_id = payload.get("user_id", "")
        post_id = payload.get("post_id", "") or payload.get("trigger_id", "")
        channel_id = payload.get("channel_id", "")

        if not text and not payload.get("file_ids"):
            return None

        message_type = MessageType.TEXT
        media_url = None
        mime_type = None

        file_ids = payload.get("file_ids") or []
        if file_ids:
            message_type = MessageType.DOCUMENT
            media_url = file_ids[0]

        return InboundMessage(
            platform=Platform.MATTERMOST,
            platform_message_id=post_id,
            sender_id=user_id,
            text=text,
            message_type=message_type,
            media_url=media_url,
            media_mime_type=mime_type,
            raw_payload=payload,
        )

    # --- Send outbound ---

    async def send(self, message: OutboundMessage) -> bool:
        try:
            channel = message.recipient_id or self._channel_id
            if not channel:
                logger.error("No channel_id for Mattermost send")
                return False

            payload = {
                "channel_id": channel,
                "message": message.text[:16383],
            }
            if message.reply_to_id:
                payload["root_id"] = message.reply_to_id

            resp = await self._client.post("/api/v4/posts", json=payload)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Mattermost send failed: {e}")
            return False

    # --- Format ---

    def format_text(self, text: str) -> str:
        """Mattermost uses standard Markdown — pass through."""
        return text

    # --- Media download ---

    async def download_media(self, media_ref: str) -> tuple[bytes, str]:
        resp = await self._client.get(f"/api/v4/files/{media_ref}")
        resp.raise_for_status()
        mime = resp.headers.get("content-type", "application/octet-stream")
        return resp.content, mime

    # --- Verification ---

    def verify_token(self, payload_token: str, expected: str) -> bool:
        return payload_token == expected

    # --- Health check ---

    async def get_me(self) -> Optional[dict]:
        try:
            resp = await self._client.get("/api/v4/users/me")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Mattermost getMe failed: {e}")
            return None

    # --- Cleanup ---

    async def close(self) -> None:
        await self._client.aclose()
