"""Wizard state — dataclass holding all configuration gathered during setup."""

from dataclasses import dataclass, field


@dataclass
class WizardState:
    # Step 1: Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_connected: bool = False
    models_pulled: list[str] = field(default_factory=list)
    gpu_detected: bool = False

    # Step 2: Harness
    preset: str = "local"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    # Step 3: Data paths
    data_path: str = "./data"
    inbox_path: str = "./data/inbox"
    api_key: str = ""
    brief_time: str = "07:00"
    launch_docker: bool = False

    # Step 4: Capture
    telegram_bot_token: str = ""
    telegram_user_id: str = ""
    mattermost_url: str = ""
    mattermost_bot_token: str = ""
    mattermost_channel_id: str = ""
    bridge_webhook_base_url: str = ""

    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    webhook_url: str = ""
    webhook_type: str = "generic"

    def generate_env(self) -> str:
        """Generate .env file content from wizard state."""
        lines = [
            f"DATA_PATH={self.data_path}",
            f"OLLAMA_MODELS_PATH=./ollama-models",
            f"",
            f"LLM_MODEL=gemma4",
            f"EMBEDDING_MODEL=nomic-embed-text",
            f"OLLAMA_BASE_URL={self.ollama_url}",
            f"",
            f"BRIEF_TIME={self.brief_time}",
            f"HARNESS_PRESET={self.preset}",
        ]

        if self.api_key:
            lines.append(f"API_KEY={self.api_key}")
        if self.anthropic_api_key:
            lines.append(f"ANTHROPIC_API_KEY={self.anthropic_api_key}")
        if self.openai_api_key:
            lines.append(f"OPENAI_API_KEY={self.openai_api_key}")
        if self.google_api_key:
            lines.append(f"GOOGLE_API_KEY={self.google_api_key}")

        if self.imap_host:
            lines.extend([
                f"",
                f"IMAP_HOST={self.imap_host}",
                f"IMAP_PORT={self.imap_port}",
                f"IMAP_USER={self.imap_user}",
                f"IMAP_PASSWORD={self.imap_password}",
                f"IMAP_FOLDER={self.imap_folder}",
            ])

        # Messaging bridge
        if self.telegram_bot_token:
            lines.extend([
                f"",
                f"TELEGRAM_BOT_TOKEN={self.telegram_bot_token}",
            ])
            if self.telegram_user_id:
                lines.append(f"TELEGRAM_USER_ID={self.telegram_user_id}")
            if self.bridge_webhook_base_url:
                lines.append(f"BRIDGE_WEBHOOK_BASE_URL={self.bridge_webhook_base_url}")

        if self.mattermost_url:
            lines.extend([
                f"",
                f"MATTERMOST_URL={self.mattermost_url}",
            ])
            if self.mattermost_bot_token:
                lines.append(f"MATTERMOST_BOT_TOKEN={self.mattermost_bot_token}")
            if self.mattermost_channel_id:
                lines.append(f"MATTERMOST_CHANNEL_ID={self.mattermost_channel_id}")

        return "\n".join(lines) + "\n"
