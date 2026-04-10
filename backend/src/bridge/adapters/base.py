"""Abstract base for platform adapters."""

from abc import ABC, abstractmethod

from src.bridge.models import OutboundMessage


class PlatformAdapter(ABC):
    platform: str = ""

    @abstractmethod
    async def send(self, message: OutboundMessage) -> bool:
        ...

    @abstractmethod
    def format_text(self, text: str) -> str:
        ...

    @abstractmethod
    async def download_media(self, media_ref: str) -> tuple[bytes, str]:
        ...
