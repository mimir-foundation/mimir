# MIMIR — AI Harness Layer (Blueprint Addendum)

## Purpose

Mimir's AI capabilities are powered through a **harness abstraction** — a provider-agnostic interface that lets the system use any combination of AI backends for different tasks. The harness is the engine. Mimir is the chassis. You swap engines without touching the chassis.

This addendum replaces all direct Ollama references in the main blueprint with a flexible harness system.

---

## 1. HARNESS ARCHITECTURE

### 1.1 Core Concept

Mimir performs 4 distinct AI operations. Each operation can be routed to a different provider independently:

| Operation | What It Does | Example Routing |
|-----------|-------------|-----------------|
| **embed** | Generate vector embeddings for chunks | Ollama `nomic-embed-text` locally |
| **extract** | Structured metadata extraction (JSON output) | Ollama `gemma4` locally |
| **reason** | Complex tasks: connection validation, synthesis, daily briefs, Q&A | Anthropic Claude API for quality |
| **transcribe** | Audio → text | Local `faster-whisper` or OpenAI Whisper API |

A user might run embeddings and extraction locally (fast, free, private) but route reasoning to Claude for higher quality synthesis and connection discovery. Or run everything locally. Or everything through APIs. The harness makes this a configuration decision, not a code decision.

### 1.2 Provider Registry

```python
# src/harness/__init__.py

from enum import Enum
from typing import Protocol

class AIOperation(str, Enum):
    EMBED = "embed"
    EXTRACT = "extract"
    REASON = "reason"
    TRANSCRIBE = "transcribe"

class AIProvider(Protocol):
    """Every provider implements this interface."""
    
    provider_name: str
    supported_operations: list[AIOperation]
    
    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: str = "text",  # "text" | "json"
    ) -> str:
        """Generate a text completion."""
        ...
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...
    
    async def transcribe(self, audio_bytes: bytes, format: str = "wav") -> str:
        """Transcribe audio to text."""
        ...
    
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        ...
```

### 1.3 Harness Router

```python
# src/harness/router.py

from dataclasses import dataclass

@dataclass
class HarnessConfig:
    """
    Maps each AI operation to a specific provider + model.
    Loaded from settings DB on startup, hot-reloadable via API.
    """
    embed: ProviderConfig
    extract: ProviderConfig
    reason: ProviderConfig
    transcribe: ProviderConfig
    
@dataclass
class ProviderConfig:
    provider: str       # "ollama" | "openai" | "anthropic" | "google" | "local"
    model: str          # "gemma4" | "claude-sonnet-4-20250514" | "gpt-4o" | etc.
    base_url: str | None = None   # Override URL (for self-hosted / proxied APIs)
    api_key: str | None = None    # Required for cloud providers
    options: dict | None = None   # Provider-specific params (temperature overrides, etc.)

class HarnessRouter:
    """
    Central router. All AI calls go through here.
    The rest of Mimir never knows or cares which provider handles the request.
    """
    
    def __init__(self, config: HarnessConfig):
        self.providers: dict[AIOperation, AIProvider] = {}
        self._init_providers(config)
    
    def _init_providers(self, config: HarnessConfig):
        """Instantiate the correct provider class for each operation."""
        operation_configs = {
            AIOperation.EMBED: config.embed,
            AIOperation.EXTRACT: config.extract,
            AIOperation.REASON: config.reason,
            AIOperation.TRANSCRIBE: config.transcribe,
        }
        for operation, pc in operation_configs.items():
            self.providers[operation] = _create_provider(pc)
    
    async def complete(self, operation: AIOperation, prompt: str, **kwargs) -> str:
        """Route a completion request to the correct provider."""
        provider = self.providers[operation]
        return await provider.complete(prompt, **kwargs)
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Route embedding requests."""
        provider = self.providers[AIOperation.EMBED]
        return await provider.embed(texts)
    
    async def transcribe(self, audio_bytes: bytes, **kwargs) -> str:
        """Route transcription requests."""
        provider = self.providers[AIOperation.TRANSCRIBE]
        return await provider.transcribe(audio_bytes, **kwargs)
    
    async def health(self) -> dict[str, bool]:
        """Check all provider health."""
        return {
            op.value: await self.providers[op].health_check()
            for op in AIOperation
        }
    
    def reload(self, config: HarnessConfig):
        """Hot-reload configuration without restart."""
        self._init_providers(config)


def _create_provider(config: ProviderConfig) -> AIProvider:
    """Factory function — instantiate the right provider from config."""
    match config.provider:
        case "ollama":
            from .providers.ollama import OllamaProvider
            return OllamaProvider(model=config.model, base_url=config.base_url or "http://ollama:11434")
        case "openai":
            from .providers.openai import OpenAIProvider
            return OpenAIProvider(model=config.model, api_key=config.api_key, base_url=config.base_url)
        case "anthropic":
            from .providers.anthropic import AnthropicProvider
            return AnthropicProvider(model=config.model, api_key=config.api_key)
        case "google":
            from .providers.google import GoogleProvider
            return GoogleProvider(model=config.model, api_key=config.api_key)
        case "local_whisper":
            from .providers.local_whisper import LocalWhisperProvider
            return LocalWhisperProvider(model_size=config.model)
        case _:
            raise ValueError(f"Unknown provider: {config.provider}")
```

---

## 2. PROVIDER IMPLEMENTATIONS

### 2.1 Ollama Provider

```python
# src/harness/providers/ollama.py

import httpx

class OllamaProvider:
    provider_name = "ollama"
    supported_operations = [AIOperation.EMBED, AIOperation.EXTRACT, AIOperation.REASON]
    
    def __init__(self, model: str, base_url: str = "http://ollama:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=120.0)
    
    async def complete(self, prompt: str, system: str = None,
                       temperature: float = 0.3, max_tokens: int = 2000,
                       response_format: str = "text") -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        if system:
            payload["system"] = system
        if response_format == "json":
            payload["format"] = "json"
        
        resp = await self.client.post(f"{self.base_url}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json()["response"]
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch embed via Ollama. Ollama handles one at a time, so we loop."""
        embeddings = []
        for text in texts:
            resp = await self.client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text}
            )
            resp.raise_for_status()
            embeddings.append(resp.json()["embedding"])
        return embeddings
    
    async def transcribe(self, audio_bytes: bytes, format: str = "wav") -> str:
        raise NotImplementedError("Ollama does not support transcription")
    
    async def health_check(self) -> bool:
        try:
            resp = await self.client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False
```

### 2.2 Anthropic Provider

```python
# src/harness/providers/anthropic.py

import httpx

class AnthropicProvider:
    provider_name = "anthropic"
    supported_operations = [AIOperation.EXTRACT, AIOperation.REASON]
    
    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str = None):
        self.model = model
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=120.0,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        )
        self.base_url = "https://api.anthropic.com"
    
    async def complete(self, prompt: str, system: str = None,
                       temperature: float = 0.3, max_tokens: int = 2000,
                       response_format: str = "text") -> str:
        messages = [{"role": "user", "content": prompt}]
        
        # If we need JSON, instruct in system prompt
        if response_format == "json" and system:
            system = system + "\n\nRespond with valid JSON only. No preamble, no markdown fences."
        elif response_format == "json":
            system = "Respond with valid JSON only. No preamble, no markdown fences."
        
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system
        
        resp = await self.client.post(f"{self.base_url}/v1/messages", json=payload)
        resp.raise_for_status()
        data = resp.json()
        
        # Extract text from content blocks
        return "".join(
            block["text"] for block in data["content"] if block["type"] == "text"
        )
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Use a dedicated embedding provider (Ollama or OpenAI)")
    
    async def transcribe(self, audio_bytes: bytes, format: str = "wav") -> str:
        raise NotImplementedError("Use a dedicated transcription provider")
    
    async def health_check(self) -> bool:
        try:
            # Simple auth check — send a minimal request
            resp = await self.client.post(
                f"{self.base_url}/v1/messages",
                json={
                    "model": self.model,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}]
                }
            )
            return resp.status_code in (200, 429)  # 429 means key is valid but rate-limited
        except Exception:
            return False
```

### 2.3 OpenAI Provider (also covers OpenAI-compatible APIs like LM Studio, vLLM, etc.)

```python
# src/harness/providers/openai.py

import httpx

class OpenAIProvider:
    provider_name = "openai"
    supported_operations = [AIOperation.EMBED, AIOperation.EXTRACT, AIOperation.REASON, AIOperation.TRANSCRIBE]
    
    def __init__(self, model: str = "gpt-4o", api_key: str = None,
                 base_url: str = None):
        self.model = model
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com").rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=120.0,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )
    
    async def complete(self, prompt: str, system: str = None,
                       temperature: float = 0.3, max_tokens: int = 2000,
                       response_format: str = "text") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        
        resp = await self.client.post(f"{self.base_url}/v1/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        # OpenAI supports batch embedding natively
        resp = await self.client.post(
            f"{self.base_url}/v1/embeddings",
            json={"model": self.model, "input": texts}
        )
        resp.raise_for_status()
        data = resp.json()
        # Sort by index to maintain order
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]
    
    async def transcribe(self, audio_bytes: bytes, format: str = "wav") -> str:
        import io
        files = {"file": (f"audio.{format}", io.BytesIO(audio_bytes), f"audio/{format}")}
        data = {"model": "whisper-1"}
        
        # Need a separate client without JSON content-type for multipart
        async with httpx.AsyncClient(
            timeout=120.0,
            headers={"Authorization": f"Bearer {self.api_key}"}
        ) as client:
            resp = await client.post(
                f"{self.base_url}/v1/audio/transcriptions",
                files=files,
                data=data
            )
            resp.raise_for_status()
            return resp.json()["text"]
    
    async def health_check(self) -> bool:
        try:
            resp = await self.client.get(f"{self.base_url}/v1/models")
            return resp.status_code in (200, 429)
        except Exception:
            return False
```

### 2.4 Google Gemini Provider

```python
# src/harness/providers/google.py

import httpx

class GoogleProvider:
    provider_name = "google"
    supported_operations = [AIOperation.EMBED, AIOperation.EXTRACT, AIOperation.REASON]
    
    def __init__(self, model: str = "gemini-2.0-flash", api_key: str = None):
        self.model = model
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.client = httpx.AsyncClient(timeout=120.0)
    
    async def complete(self, prompt: str, system: str = None,
                       temperature: float = 0.3, max_tokens: int = 2000,
                       response_format: str = "text") -> str:
        contents = [{"parts": [{"text": prompt}]}]
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if response_format == "json":
            payload["generationConfig"]["responseMimeType"] = "application/json"
        
        resp = await self.client.post(
            f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}",
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Gemini embedding API
        embeddings = []
        for text in texts:
            resp = await self.client.post(
                f"{self.base_url}/models/text-embedding-004:embedContent?key={self.api_key}",
                json={"content": {"parts": [{"text": text}]}}
            )
            resp.raise_for_status()
            embeddings.append(resp.json()["embedding"]["values"])
        return embeddings
    
    async def transcribe(self, audio_bytes: bytes, format: str = "wav") -> str:
        raise NotImplementedError("Use a dedicated transcription provider")
    
    async def health_check(self) -> bool:
        try:
            resp = await self.client.get(
                f"{self.base_url}/models?key={self.api_key}"
            )
            return resp.status_code == 200
        except Exception:
            return False
```

### 2.5 Local Whisper Provider

```python
# src/harness/providers/local_whisper.py

class LocalWhisperProvider:
    provider_name = "local_whisper"
    supported_operations = [AIOperation.TRANSCRIBE]
    
    def __init__(self, model_size: str = "base"):
        """
        Uses faster-whisper for local transcription.
        Model sizes: tiny, base, small, medium, large-v3
        """
        self.model_size = model_size
        self._model = None
    
    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(self.model_size, compute_type="int8")
        return self._model
    
    async def complete(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError("Whisper only supports transcription")
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Whisper only supports transcription")
    
    async def transcribe(self, audio_bytes: bytes, format: str = "wav") -> str:
        import tempfile, os, asyncio
        
        model = self._get_model()
        with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name
        
        try:
            # Run in thread pool since faster-whisper is synchronous
            segments, _ = await asyncio.to_thread(model.transcribe, temp_path)
            text = " ".join(seg.text.strip() for seg in segments)
            return text
        finally:
            os.unlink(temp_path)
    
    async def health_check(self) -> bool:
        try:
            self._get_model()
            return True
        except Exception:
            return False
```

---

## 3. HARNESS CONFIGURATION

### 3.1 Settings Schema (stored in SQLite `settings` table)

```json
{
  "harness": {
    "embed": {
      "provider": "ollama",
      "model": "nomic-embed-text",
      "base_url": "http://ollama:11434"
    },
    "extract": {
      "provider": "ollama",
      "model": "gemma4",
      "base_url": "http://ollama:11434"
    },
    "reason": {
      "provider": "anthropic",
      "model": "claude-sonnet-4-20250514",
      "api_key": "sk-ant-..."
    },
    "transcribe": {
      "provider": "local_whisper",
      "model": "base"
    }
  }
}
```

### 3.2 Preset Configurations

These are one-click configurations users can choose from in the Settings UI:

**Fully Local (Privacy Maximum)**
```json
{
  "embed":      { "provider": "ollama", "model": "nomic-embed-text" },
  "extract":    { "provider": "ollama", "model": "gemma4" },
  "reason":     { "provider": "ollama", "model": "gemma4" },
  "transcribe": { "provider": "local_whisper", "model": "base" }
}
```

**Local + Cloud Reasoning (Best Balance)**
```json
{
  "embed":      { "provider": "ollama", "model": "nomic-embed-text" },
  "extract":    { "provider": "ollama", "model": "gemma4" },
  "reason":     { "provider": "anthropic", "model": "claude-sonnet-4-20250514" },
  "transcribe": { "provider": "local_whisper", "model": "base" }
}
```

**Fully Cloud (No Local GPU Needed)**
```json
{
  "embed":      { "provider": "openai", "model": "text-embedding-3-small" },
  "extract":    { "provider": "openai", "model": "gpt-4o-mini" },
  "reason":     { "provider": "anthropic", "model": "claude-sonnet-4-20250514" },
  "transcribe": { "provider": "openai", "model": "whisper-1" }
}
```

**Budget Cloud (Minimize API Costs)**
```json
{
  "embed":      { "provider": "google", "model": "text-embedding-004" },
  "extract":    { "provider": "google", "model": "gemini-2.0-flash" },
  "reason":     { "provider": "google", "model": "gemini-2.0-flash" },
  "transcribe": { "provider": "openai", "model": "whisper-1" }
}
```

### 3.3 Environment Variable Overrides

```env
# Provider API keys (can also be set in UI)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...

# Ollama location (for existing homelab instance)
OLLAMA_BASE_URL=http://192.168.4.45:11434

# Default preset to use on first launch
HARNESS_PRESET=local   # "local" | "hybrid" | "cloud" | "budget"
```

---

## 4. HARNESS INTEGRATION WITH PIPELINE

### 4.1 Updated Pipeline Calls

The processing pipeline from the main blueprint now calls through the harness instead of directly to Ollama:

```python
# src/processing/pipeline.py

class ProcessingPipeline:
    def __init__(self, harness: HarnessRouter):
        self.harness = harness
    
    async def extract(self, note: Note) -> ExtractionResult:
        """Stage 3: Use the EXTRACT operation."""
        prompt = build_extraction_prompt(note)
        result = await self.harness.complete(
            operation=AIOperation.EXTRACT,
            prompt=prompt,
            system="You are a knowledge librarian. Extract structured metadata.",
            response_format="json",
            temperature=0.1,    # Low temp for structured extraction
        )
        return parse_extraction_result(result)
    
    async def embed(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        """Stage 4: Use the EMBED operation."""
        texts = [chunk.text for chunk in chunks]
        vectors = await self.harness.embed(texts)
        return [
            EmbeddedChunk(chunk=chunk, embedding=vec)
            for chunk, vec in zip(chunks, vectors)
        ]
    
    async def link(self, note: Note, candidates: list[Note]) -> list[Connection]:
        """Stage 5: Use the REASON operation for connection validation."""
        connections = []
        for candidate in candidates:
            prompt = build_link_validation_prompt(note, candidate)
            result = await self.harness.complete(
                operation=AIOperation.REASON,  # Reasoning = higher quality model
                prompt=prompt,
                system="You are a knowledge connector.",
                response_format="json",
                temperature=0.2,
            )
            conn = parse_connection_result(result)
            if conn and conn.strength > 0.5:
                connections.append(conn)
        return connections
    
    async def synthesize(self, note: Note, connections: list[Connection]) -> str:
        """Stage 6: Use the REASON operation."""
        prompt = build_synthesis_prompt(note, connections)
        return await self.harness.complete(
            operation=AIOperation.REASON,
            prompt=prompt,
            system="You are the user's second brain.",
            temperature=0.5,    # Slightly creative for synthesis
        )
    
    async def transcribe(self, audio_bytes: bytes, format: str) -> str:
        """Voice capture transcription."""
        return await self.harness.transcribe(audio_bytes, format=format)
```

### 4.2 Why Split Extract vs Reason?

This is a deliberate design decision:

- **Extract** runs on every single note. It needs to be fast and cheap. Structured JSON output. A small local model (gemma4, phi3, llama3.2) handles this perfectly.

- **Reason** runs selectively — connection validation, synthesis, daily briefs, Q&A. These require nuance, creativity, and judgment. A more capable model (Claude, GPT-4o, or a larger local model) produces meaningfully better output here.

By splitting them, you can run 90% of the pipeline on free local compute and only pay for the 10% where quality matters most.

---

## 5. HARNESS API ENDPOINTS

```
GET  /api/harness/config
  Response: current harness configuration for all 4 operations

PUT  /api/harness/config
  Body: full or partial harness config
  Response: updated config
  Note: hot-reloads the harness router without restart

GET  /api/harness/presets
  Response: list of available preset configurations

POST /api/harness/presets/{preset_name}/apply
  Response: applies preset, returns new config

GET  /api/harness/health
  Response: { embed: true, extract: true, reason: false, transcribe: true }
  Note: checks connectivity to each configured provider

GET  /api/harness/providers
  Response: list of available providers with their supported operations

POST /api/harness/test
  Body: { operation: "reason", prompt: "Hello, are you working?" }
  Response: { success: true, response: "...", latency_ms: 342, provider: "anthropic" }
  Note: test a specific operation without processing a note
```

---

## 6. HARNESS SETTINGS UI

### 6.1 Settings Page Section: "AI Engine"

```
┌─────────────────────────────────────────────────────────────┐
│  AI Engine Configuration                                     │
│                                                              │
│  Presets: [Fully Local] [Local + Cloud ✓] [Cloud] [Budget]  │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Embeddings                                              ││
│  │  Provider: [Ollama ▼]                                    ││
│  │  Model:    [nomic-embed-text]                            ││
│  │  URL:      [http://192.168.4.45:11434]                   ││
│  │  Status:   ● Connected                                   ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Extraction (metadata, tagging)                          ││
│  │  Provider: [Ollama ▼]                                    ││
│  │  Model:    [gemma4]                                      ││
│  │  URL:      [http://192.168.4.45:11434]                   ││
│  │  Status:   ● Connected                                   ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Reasoning (synthesis, connections, briefs)              ││
│  │  Provider: [Anthropic ▼]                                 ││
│  │  Model:    [claude-sonnet-4-20250514 ▼]                          ││
│  │  API Key:  [sk-ant-••••••••••••]                         ││
│  │  Status:   ● Connected                                   ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Transcription                                           ││
│  │  Provider: [Local Whisper ▼]                             ││
│  │  Model:    [base ▼]                                      ││
│  │  Status:   ● Ready                                       ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [Test All Connections]              [Save Configuration]   │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. FALLBACK & RESILIENCE

### 7.1 Fallback Chain

Each operation can have a fallback provider in case the primary is unavailable:

```python
@dataclass
class ProviderConfig:
    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None
    options: dict | None = None
    fallback: "ProviderConfig | None" = None  # Try this if primary fails
```

Example: Reason with Claude, fall back to local Gemma if API is down:

```json
{
  "reason": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "api_key": "sk-ant-...",
    "fallback": {
      "provider": "ollama",
      "model": "gemma4"
    }
  }
}
```

### 7.2 Retry Logic

```python
async def complete_with_retry(self, operation: AIOperation, prompt: str, **kwargs) -> str:
    """
    Try primary provider. On failure, try fallback. On fallback failure, queue for retry.
    
    Retry policy:
    - 3 attempts on primary with exponential backoff (1s, 3s, 9s)
    - If primary exhausted, try fallback (1 attempt)
    - If all fail, raise and let the pipeline error handler queue for later
    
    Rate limit handling:
    - 429 responses → backoff with Retry-After header if present
    - Track usage per provider to avoid hitting limits
    """
```

### 7.3 Embedding Consistency

**Critical constraint:** If you change your embedding provider or model, existing embeddings become incompatible. The harness handles this:

```python
async def embed_with_consistency_check(self, texts: list[str]) -> list[list[float]]:
    """
    Before embedding, check if the current embedding config matches
    what's stored in ChromaDB metadata.
    
    If config changed:
    1. Warn the user via the UI
    2. Offer to re-embed all existing notes (background job)
    3. Block new embeddings until user decides
    
    Store embedding config hash in ChromaDB collection metadata
    to detect changes.
    """
```

---

## 8. COST TRACKING

### 8.1 Usage Logging

```sql
CREATE TABLE ai_usage_log (
    id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,        -- 'embed' | 'extract' | 'reason' | 'transcribe'
    provider TEXT NOT NULL,         -- 'ollama' | 'anthropic' | 'openai' | 'google'
    model TEXT NOT NULL,
    input_tokens INTEGER,          -- Estimated from prompt length
    output_tokens INTEGER,         -- Estimated from response length
    latency_ms INTEGER,
    cost_usd REAL,                 -- Estimated cost (0 for local)
    note_id TEXT,                  -- Which note triggered this (if applicable)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 8.2 Cost Estimation

```python
# Approximate costs per 1M tokens (updated as needed)
COST_PER_MILLION_TOKENS = {
    "anthropic": {
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    },
    "openai": {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "text-embedding-3-small": {"input": 0.02, "output": 0},
    },
    "google": {
        "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    },
    "ollama": {
        "*": {"input": 0, "output": 0},  # Local = free
    },
}
```

### 8.3 Dashboard Widget

The Settings UI shows a "Usage & Cost" section:

```
This Month:
  Embeddings:     12,340 calls   |  Local (free)
  Extraction:      1,847 calls   |  Local (free)  
  Reasoning:         423 calls   |  Anthropic   ~$2.14
  Transcription:      12 calls   |  Local (free)
  
  Estimated total: $2.14
```

---

## 9. CUSTOM / OPENAI-COMPATIBLE PROVIDERS

The OpenAI provider doubles as a generic adapter for any OpenAI-compatible API. This covers:

- **LM Studio** → `base_url: "http://localhost:1234"`
- **vLLM** → `base_url: "http://localhost:8000"`
- **text-generation-webui** (oobabooga) → `base_url: "http://localhost:5000"`
- **Together AI** → `base_url: "https://api.together.xyz"` + API key
- **Groq** → `base_url: "https://api.groq.com/openai"` + API key
- **OpenRouter** → `base_url: "https://openrouter.ai/api"` + API key
- **Any self-hosted model** with an OpenAI-compatible wrapper

Configuration example for Groq:

```json
{
  "reason": {
    "provider": "openai",
    "model": "llama-3.3-70b-versatile",
    "base_url": "https://api.groq.com/openai",
    "api_key": "gsk_..."
  }
}
```

This means Mimir works with essentially any LLM backend that exists today or will exist tomorrow, without code changes.

---

## 10. UPDATED DIRECTORY STRUCTURE (Harness Addition)

```
backend/src/
├── harness/
│   ├── __init__.py          # AIOperation enum, AIProvider protocol
│   ├── router.py            # HarnessRouter, HarnessConfig, factory
│   ├── cost_tracker.py      # Usage logging and cost estimation
│   ├── consistency.py       # Embedding consistency checks
│   └── providers/
│       ├── __init__.py
│       ├── ollama.py
│       ├── anthropic.py
│       ├── openai.py        # Also covers all OpenAI-compatible APIs
│       ├── google.py
│       └── local_whisper.py
├── ...rest of backend unchanged
```

---

## 11. INTEGRATION CHECKLIST

When building Mimir with Claude Code, apply the harness in this order:

1. **Build the harness layer first** — `AIProvider` protocol, `HarnessRouter`, Ollama provider
2. **Wire the processing pipeline** to call through `self.harness.complete()` and `self.harness.embed()` instead of direct HTTP calls
3. **Add the settings API** — `/api/harness/config`, `/api/harness/health`
4. **Build the Settings UI** — AI Engine section with provider dropdowns
5. **Add Anthropic provider** — enables hybrid mode
6. **Add OpenAI provider** — covers OpenAI + all compatible APIs
7. **Add Google provider** — budget option
8. **Add Local Whisper** — transcription
9. **Add fallback chains** — resilience
10. **Add cost tracking** — usage log + dashboard widget
11. **Add embedding consistency checks** — prevent silent corruption on model switch
12. **Add presets** — one-click configurations

---

*This addendum should be read alongside the main Mimir blueprint. The harness replaces all direct Ollama references in the main document. Every `await self.client.post("http://ollama:11434/...")` becomes `await self.harness.complete(AIOperation.X, ...)` instead.*
