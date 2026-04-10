import logging
from dataclasses import dataclass, field
from typing import Optional

from src.config import Settings
from src.harness import AIOperation
from src.harness.providers.ollama import OllamaProvider

logger = logging.getLogger("mimir.harness")


@dataclass
class ProviderConfig:
    provider: str = "ollama"
    model: str = "gemma3"
    base_url: str = "http://ollama:11434"
    api_key: Optional[str] = None
    embed_model: Optional[str] = None


@dataclass
class HarnessConfig:
    embed: ProviderConfig = field(default_factory=ProviderConfig)
    extract: ProviderConfig = field(default_factory=ProviderConfig)
    reason: ProviderConfig = field(default_factory=ProviderConfig)
    transcribe: ProviderConfig = field(default_factory=ProviderConfig)


PRESETS = {
    "local": lambda s: HarnessConfig(
        embed=ProviderConfig(provider="ollama", model=s.embedding_model, base_url=s.ollama_base_url),
        extract=ProviderConfig(provider="ollama", model=s.llm_model, base_url=s.ollama_base_url),
        reason=ProviderConfig(provider="ollama", model=s.llm_model, base_url=s.ollama_base_url),
        transcribe=ProviderConfig(provider="ollama", model=s.llm_model, base_url=s.ollama_base_url),
    ),
    "hybrid": lambda s: HarnessConfig(
        embed=ProviderConfig(provider="ollama", model=s.embedding_model, base_url=s.ollama_base_url),
        extract=ProviderConfig(provider="ollama", model=s.llm_model, base_url=s.ollama_base_url),
        reason=ProviderConfig(provider="anthropic", model="claude-sonnet-4-20250514", api_key=s.anthropic_api_key),
        transcribe=ProviderConfig(provider="ollama", model=s.llm_model, base_url=s.ollama_base_url),
    ),
    "cloud": lambda s: HarnessConfig(
        embed=ProviderConfig(provider="openai", model="text-embedding-3-small", api_key=s.openai_api_key),
        extract=ProviderConfig(provider="anthropic", model="claude-sonnet-4-20250514", api_key=s.anthropic_api_key),
        reason=ProviderConfig(provider="anthropic", model="claude-sonnet-4-20250514", api_key=s.anthropic_api_key),
        transcribe=ProviderConfig(provider="openai", model="whisper-1", api_key=s.openai_api_key),
    ),
    "budget": lambda s: HarnessConfig(
        embed=ProviderConfig(provider="ollama", model=s.embedding_model, base_url=s.ollama_base_url),
        extract=ProviderConfig(provider="ollama", model=s.llm_model, base_url=s.ollama_base_url),
        reason=ProviderConfig(provider="anthropic", model="claude-haiku-4-5-20251001", api_key=s.anthropic_api_key),
        transcribe=ProviderConfig(provider="ollama", model=s.llm_model, base_url=s.ollama_base_url),
    ),
}


def load_harness_config(settings: Settings) -> HarnessConfig:
    preset_name = settings.harness_preset
    if preset_name in PRESETS:
        return PRESETS[preset_name](settings)
    return PRESETS["local"](settings)


def _create_provider(config: ProviderConfig):
    if config.provider == "ollama":
        return OllamaProvider(
            base_url=config.base_url,
            model=config.model,
            embed_model=config.embed_model,
        )
    # Stub for other providers — fall back to Ollama for now
    logger.warning(f"Provider '{config.provider}' not implemented, falling back to ollama")
    return OllamaProvider(
        base_url=config.base_url or "http://ollama:11434",
        model=config.model,
    )


class HarnessRouter:
    def __init__(self, config: HarnessConfig):
        self.config = config
        self._providers: dict[str, object] = {}
        self._init_providers()

    def _init_providers(self):
        self._providers = {
            AIOperation.EMBED: _create_provider(self.config.embed),
            AIOperation.EXTRACT: _create_provider(self.config.extract),
            AIOperation.REASON: _create_provider(self.config.reason),
            AIOperation.TRANSCRIBE: _create_provider(self.config.transcribe),
        }

    async def complete(
        self,
        operation: AIOperation,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: Optional[str] = None,
    ) -> str:
        provider = self._providers[operation]
        return await provider.complete(
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        provider = self._providers[AIOperation.EMBED]
        return await provider.embed(texts)

    async def health(self) -> dict[str, bool]:
        results = {}
        for op, provider in self._providers.items():
            try:
                results[op] = await provider.health_check()
            except Exception:
                results[op] = False
        return results

    def reload(self, config: HarnessConfig):
        self.config = config
        self._init_providers()
        logger.info("Harness reloaded with new config")
