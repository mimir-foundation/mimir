"""Anthropic Claude provider — Messages API via httpx."""

import base64
import logging
from typing import Optional

import httpx

logger = logging.getLogger("mimir.harness.anthropic")

API_URL = "https://api.anthropic.com/v1/messages"


def _detect_image_mime(data: bytes) -> str:
    """Detect image MIME type from magic bytes."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/jpeg"  # safe default for Anthropic


class AnthropicProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(
            timeout=120.0,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: Optional[str] = None,
        images: Optional[list[bytes]] = None,
    ) -> str:
        # Build content blocks
        content = []
        if images:
            for img in images:
                b64 = base64.b64encode(img).decode("utf-8")
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": _detect_image_mime(img),
                        "data": b64,
                    },
                })
        content.append({"type": "text", "text": prompt})

        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": content}],
            "temperature": temperature,
        }
        if system:
            payload["system"] = system

        resp = await self._client.post(API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # Extract text from response content blocks
        text_parts = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block["text"])
        return "\n".join(text_parts)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Anthropic does not provide an embeddings API. Use Ollama or OpenAI for embeddings.")

    async def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            # Minimal request to verify key works
            resp = await self._client.post(
                API_URL,
                json={
                    "model": self._model,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()
