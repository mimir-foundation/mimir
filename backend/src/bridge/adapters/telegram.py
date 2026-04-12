"""Telegram adapter — Bot API integration."""

import asyncio
import logging
import re
from typing import Optional

import httpx

from src.bridge.adapters.base import PlatformAdapter
from src.bridge.models import InboundMessage, MessageType, OutboundMessage, Platform

logger = logging.getLogger("mimir.bridge.telegram")

# Characters that must be escaped in MarkdownV2
_MD2_ESCAPE = re.compile(r"([_\*\[\]\(\)~`>#+\-=|{}.!\\])")


class TelegramAdapter(PlatformAdapter):
    platform = Platform.TELEGRAM

    def __init__(self, bot_token: str, webhook_base_url: str = ""):
        self._token = bot_token
        self._api = f"https://api.telegram.org/bot{bot_token}"
        self._webhook_base_url = webhook_base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)
        self._poll_task: Optional[asyncio.Task] = None
        self._poll_offset = 0

    # --- Normalize inbound ---

    def normalize(self, payload: dict) -> Optional[InboundMessage]:
        """Convert a Telegram Update dict into an InboundMessage."""
        msg = payload.get("message")
        if not msg:
            return None

        sender_id = str(msg.get("from", {}).get("id", ""))
        text = msg.get("text", "") or msg.get("caption", "")
        message_type = MessageType.TEXT
        media_url = None
        mime_type = None

        if "photo" in msg:
            message_type = MessageType.IMAGE
            # Highest-resolution photo is last in the array
            photo = msg["photo"][-1]
            media_url = photo["file_id"]
        elif "voice" in msg or "audio" in msg:
            message_type = MessageType.AUDIO
            voice = msg.get("voice") or msg.get("audio", {})
            media_url = voice.get("file_id")
            mime_type = voice.get("mime_type", "audio/ogg")
        elif "document" in msg:
            message_type = MessageType.DOCUMENT
            doc = msg["document"]
            media_url = doc.get("file_id")
            mime_type = doc.get("mime_type")

        reply_to_id = None
        if "reply_to_message" in msg:
            reply_to_id = str(msg["reply_to_message"].get("message_id", ""))

        return InboundMessage(
            platform=Platform.TELEGRAM,
            platform_message_id=str(msg.get("message_id", "")),
            sender_id=sender_id,
            text=text,
            message_type=message_type,
            media_url=media_url,
            media_mime_type=mime_type,
            caption=msg.get("caption"),
            reply_to_id=reply_to_id,
            raw_payload=payload,
        )

    # --- Send outbound ---

    async def send(self, message: OutboundMessage) -> bool:
        try:
            payload: dict = {
                "chat_id": message.recipient_id,
                "text": message.text[:4096],
            }
            if message.parse_mode:
                payload["parse_mode"] = message.parse_mode
            if message.reply_to_id:
                payload["reply_to_message_id"] = message.reply_to_id

            resp = await self._client.post(f"{self._api}/sendMessage", json=payload)
            if resp.status_code != 200:
                # Fallback: retry without parse_mode (formatting issues)
                if message.parse_mode:
                    payload.pop("parse_mode", None)
                    resp = await self._client.post(
                        f"{self._api}/sendMessage", json=payload
                    )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def send_document(
        self, recipient_id: str, file_bytes: bytes, filename: str, caption: str = "",
    ) -> bool:
        """Send a file (e.g. .ics) to a Telegram chat."""
        try:
            files = {"document": (filename, file_bytes)}
            data = {"chat_id": recipient_id}
            if caption:
                data["caption"] = caption[:1024]
            resp = await self._client.post(
                f"{self._api}/sendDocument", data=data, files=files,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Telegram sendDocument failed: {e}")
            return False

    # --- Format ---

    def format_text(self, text: str) -> str:
        """Escape MarkdownV2 specials, preserve bold/italic markers."""
        # First escape all special chars
        escaped = _MD2_ESCAPE.sub(r"\\\1", text)
        # Restore **bold** → *bold* (Telegram MarkdownV2 uses single *)
        escaped = re.sub(r"\\\*\\\*(.+?)\\\*\\\*", r"*\1*", escaped)
        return escaped

    # --- Media download ---

    async def download_media(self, media_ref: str) -> tuple[bytes, str]:
        """Download a file by file_id. Returns (bytes, mime_type)."""
        # Get file path
        resp = await self._client.get(
            f"{self._api}/getFile", params={"file_id": media_ref}
        )
        resp.raise_for_status()
        file_path = resp.json()["result"]["file_path"]

        # Download
        file_url = f"https://api.telegram.org/file/bot{self._token}/{file_path}"
        dl = await self._client.get(file_url)
        dl.raise_for_status()

        mime = dl.headers.get("content-type", "application/octet-stream")
        return dl.content, mime

    # --- Webhook registration ---

    async def register_webhook(self) -> bool:
        """Register the webhook URL with Telegram."""
        if not self._webhook_base_url:
            return False
        url = f"{self._webhook_base_url}/bridge/telegram/webhook"
        try:
            resp = await self._client.post(
                f"{self._api}/setWebhook",
                json={"url": url, "allowed_updates": ["message"]},
            )
            resp.raise_for_status()
            data = resp.json()
            ok = data.get("result", False)
            if ok:
                logger.info(f"Telegram webhook registered: {url}")
            else:
                logger.warning(f"Telegram setWebhook response: {data}")
            return ok
        except Exception as e:
            logger.error(f"Failed to register Telegram webhook: {e}")
            return False

    # --- Long-polling (local dev) ---

    def start_polling(self) -> None:
        """Start a background task that long-polls Telegram for updates."""
        if self._poll_task and not self._poll_task.done():
            return
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Telegram long-polling started")

    async def _poll_loop(self) -> None:
        while True:
            try:
                resp = await self._client.get(
                    f"{self._api}/getUpdates",
                    params={"offset": self._poll_offset, "timeout": 30},
                    timeout=45.0,
                )
                if resp.status_code != 200:
                    await asyncio.sleep(5)
                    continue
                data = resp.json()
                for update in data.get("result", []):
                    self._poll_offset = update["update_id"] + 1
                    # Process via handler — injected at init_bridge time
                    if self._on_update:
                        await self._on_update(update)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Telegram poll error: {e}")
                await asyncio.sleep(5)

    _on_update = None  # Set by init_bridge

    # --- Verification ---

    def verify_request(self, headers: dict, secret: str) -> bool:
        """Check X-Telegram-Bot-Api-Secret-Token header."""
        return headers.get("x-telegram-bot-api-secret-token") == secret

    # --- Health check ---

    async def get_me(self) -> Optional[dict]:
        try:
            resp = await self._client.get(f"{self._api}/getMe")
            resp.raise_for_status()
            return resp.json().get("result")
        except Exception as e:
            logger.error(f"Telegram getMe failed: {e}")
            return None

    # --- Cleanup ---

    async def close(self) -> None:
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        await self._client.aclose()
