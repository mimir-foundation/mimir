"""Wizard Step 5: Messaging Bridge — Telegram and Mattermost configuration."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Button, Label, Static, Markdown

import httpx


class MessagingStep(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Step 5: Messaging Bridge", classes="panel-title")
        yield Static("Connect Telegram and/or Mattermost for capture, search, and notifications. All fields are optional.")

        # Telegram
        yield Static("")
        yield Label("Telegram", classes="panel-title")
        yield Markdown(
            "1. Message [@BotFather](https://t.me/BotFather) on Telegram\n"
            "2. Send `/newbot` and follow the prompts\n"
            "3. Copy the **bot token** below\n"
            "4. Send a message to your bot, then get your user ID via [@userinfobot](https://t.me/userinfobot)\n"
        )
        yield Label("Bot Token")
        yield Input(placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11", password=True, id="w-tg-token")
        yield Label("Your User ID (for notifications)")
        yield Input(placeholder="123456789", id="w-tg-user-id")
        yield Label("Webhook Base URL (leave blank for polling)")
        yield Input(placeholder="https://your-server.com", id="w-tg-webhook-url")
        yield Button("Test Telegram", id="btn-test-telegram")
        yield Static("", id="tg-status")

        # Mattermost
        yield Static("")
        yield Label("Mattermost", classes="panel-title")
        yield Markdown(
            "1. Go to **Integrations > Bot Accounts** in Mattermost admin\n"
            "2. Create a bot and copy the **access token**\n"
            "3. Note the **channel ID** from the channel URL\n"
        )
        yield Label("Server URL")
        yield Input(placeholder="https://mattermost.example.com", id="w-mm-url")
        yield Label("Bot Token")
        yield Input(placeholder="abcdefghijklmnop", password=True, id="w-mm-token")
        yield Label("Channel ID")
        yield Input(placeholder="abc123def456", id="w-mm-channel")
        yield Button("Test Mattermost", id="btn-test-mattermost")
        yield Static("", id="mm-status")

    def on_input_changed(self, event: Input.Changed) -> None:
        state = self.app.state
        mapping = {
            "w-tg-token": "telegram_bot_token",
            "w-tg-user-id": "telegram_user_id",
            "w-tg-webhook-url": "bridge_webhook_base_url",
            "w-mm-url": "mattermost_url",
            "w-mm-token": "mattermost_bot_token",
            "w-mm-channel": "mattermost_channel_id",
        }
        attr = mapping.get(event.input.id)
        if attr:
            setattr(state, attr, event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-test-telegram":
            self.run_worker(self._test_telegram())
        elif event.button.id == "btn-test-mattermost":
            self.run_worker(self._test_mattermost())

    async def _test_telegram(self) -> None:
        status = self.query_one("#tg-status", Static)
        token = self.app.state.telegram_bot_token

        if not token:
            status.update("[yellow]Enter a bot token first[/]")
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
                resp.raise_for_status()
                data = resp.json()
                if data.get("ok"):
                    bot = data["result"]
                    status.update(
                        f"[green]Connected! Bot: @{bot.get('username', '?')} ({bot.get('first_name', '')})[/]"
                    )
                else:
                    status.update(f"[red]API returned error: {data.get('description', 'unknown')}[/]")
        except Exception as e:
            status.update(f"[red]Failed: {e}[/]")

    async def _test_mattermost(self) -> None:
        status = self.query_one("#mm-status", Static)
        url = self.app.state.mattermost_url
        token = self.app.state.mattermost_bot_token

        if not url or not token:
            status.update("[yellow]Enter server URL and bot token first[/]")
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{url.rstrip('/')}/api/v4/users/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                user = resp.json()
                status.update(
                    f"[green]Connected! Bot: {user.get('username', '?')}[/]"
                )
        except Exception as e:
            status.update(f"[red]Failed: {e}[/]")
