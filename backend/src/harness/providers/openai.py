"""OpenAI provider — Chat Completions + Embeddings API via httpx."""

import base64
import logging
from typing import Optional

import httpx

logger = logging.getLogger("mimir.harness.openai")

CHAT_URL = "https://api.openai.com/v1/chat/completions"
EMBED_URL = "https://api.openai.com/v1/embeddings"


def _detect_image_mime(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/jpeg"


class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o", embed_model: Optional[str] = None):
        self._api_key = api_key
        self._model = model
        self._embed_model = embed_model or "text-embedding-3-small"
        self._client = httpx.AsyncClient(
            timeout=120.0,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    @property
    def name(self) -> str:
        return "openai"

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
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        # Build user message content
        content = []
        if images:
            for img in images:
                b64 = base64.b64encode(img).decode("utf-8")
                mime = _detect_image_mime(img)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                })
        content.append({"type": "text", "text": prompt})

        # If no images, simplify to plain text
        if not images:
            messages.append({"role": "user", "content": prompt})
        else:
            messages.append({"role": "user", "content": content})

        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        resp = await self._client.post(CHAT_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        # Batch up to 100 texts per request
        for i in range(0, len(texts), 100):
            batch = texts[i:i + 100]
            resp = await self._client.post(
                EMBED_URL,
                json={"model": self._embed_model, "input": batch},
            )
            resp.raise_for_status()
            data = resp.json()
            for item in sorted(data["data"], key=lambda x: x["index"]):
                embeddings.append(item["embedding"])
        return embeddings

    async def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            resp = await self._client.post(
                CHAT_URL,
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                },
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()
