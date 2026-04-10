from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class AIProvider(Protocol):
    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: Optional[str] = None,
    ) -> str: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def health_check(self) -> bool: ...

    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...
