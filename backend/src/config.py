from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    data_path: str = "./data"
    database_path: str = "/data/mimir.db"
    chroma_path: str = "/data/chroma"
    documents_path: str = "/data/documents"
    inbox_path: str = "/data/inbox"

    # Ollama
    ollama_base_url: str = "http://ollama:11434"
    llm_model: str = "gemma3"
    embedding_model: str = "nomic-embed-text"

    # Security
    api_key: Optional[str] = None

    # Agent
    brief_time: str = "07:00"
    brief_webhook_url: Optional[str] = None

    # Harness preset
    harness_preset: str = "local"

    # Provider API keys (optional)
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    # Email capture (IMAP)
    imap_host: Optional[str] = None
    imap_port: int = 993
    imap_user: Optional[str] = None
    imap_password: Optional[str] = None
    imap_folder: str = "INBOX"
    imap_poll_interval: int = 300

    # Messaging bridge
    telegram_bot_token: Optional[str] = None
    telegram_user_id: Optional[str] = None
    mattermost_url: Optional[str] = None
    mattermost_bot_token: Optional[str] = None
    mattermost_channel_id: Optional[str] = None
    bridge_webhook_base_url: Optional[str] = None

    # Logging
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
