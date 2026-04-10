import logging
from typing import Optional

import httpx

logger = logging.getLogger("mimir.harness.ollama")


class OllamaProvider:
    def __init__(self, base_url: str, model: str, embed_model: Optional[str] = None):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._embed_model = embed_model or model
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=120.0)

    @property
    def name(self) -> str:
        return "ollama"

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
    ) -> str:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system
        if response_format == "json":
            payload["format"] = "json"

        resp = await self._client.post("/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for text in texts:
            resp = await self._client.post(
                "/api/embeddings",
                json={"model": self._embed_model, "prompt": text},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings.append(data["embedding"])
        return embeddings

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()
