"""Wizard Step 4: Capture sources — IMAP, API key, Chrome extension, webhook."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Button, Label, Static, Markdown

import httpx


class CaptureStep(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Step 4: Capture Sources", classes="panel-title")
        yield Static("Configure optional capture methods. All fields are optional.")

        yield Static("")
        yield Label("📧 Email Capture (IMAP)", classes="panel-title")
        yield Label("IMAP Host")
        yield Input(placeholder="imap.gmail.com", id="w-imap-host")
        yield Label("IMAP Port")
        yield Input(value="993", id="w-imap-port")
        yield Label("IMAP User")
        yield Input(placeholder="you@gmail.com", id="w-imap-user")
        yield Label("IMAP Password")
        yield Input(placeholder="app-specific password", password=True, id="w-imap-pass")
        yield Button("Test IMAP Connection", id="btn-test-imap")
        yield Static("", id="imap-status")

        yield Static("")
        yield Label("🔔 Webhook Notifications", classes="panel-title")
        yield Input(placeholder="https://hooks.slack.com/...", id="w-webhook-url")
        yield Button("Send Test Webhook", id="btn-test-webhook")
        yield Static("", id="webhook-status")

        yield Static("")
        yield Label("🌐 Chrome Extension", classes="panel-title")
        yield Markdown(
            "To install the Chrome extension:\n\n"
            "1. Open Chrome → `chrome://extensions`\n"
            "2. Enable **Developer mode**\n"
            "3. Click **Load unpacked** → select `extensions/chrome/`\n"
            "4. Click the extension → **Settings**\n"
            "5. Enter your Mimir server URL and API key\n"
        )

        yield Static("")
        yield Label("✅ Summary", classes="panel-title")
        yield Static("Press [bold]Finish[/] to save your configuration and start using Mimir.", id="summary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-test-imap":
            self.run_worker(self._test_imap())
        elif event.button.id == "btn-test-webhook":
            self.run_worker(self._test_webhook())

    def on_input_changed(self, event: Input.Changed) -> None:
        state = self.app.state
        if event.input.id == "w-imap-host":
            state.imap_host = event.value
        elif event.input.id == "w-imap-port":
            try:
                state.imap_port = int(event.value)
            except ValueError:
                pass
        elif event.input.id == "w-imap-user":
            state.imap_user = event.value
        elif event.input.id == "w-imap-pass":
            state.imap_password = event.value
        elif event.input.id == "w-webhook-url":
            state.webhook_url = event.value

    async def _test_imap(self) -> None:
        status = self.query_one("#imap-status", Static)
        state = self.app.state

        if not state.imap_host or not state.imap_user:
            status.update("[yellow]Fill in host and user first[/]")
            return

        try:
            import imaplib
            conn = imaplib.IMAP4_SSL(state.imap_host, state.imap_port)
            conn.login(state.imap_user, state.imap_password)
            conn.select(state.imap_folder)
            status_code, data = conn.search(None, "ALL")
            count = len(data[0].split()) if data[0] else 0
            conn.close()
            conn.logout()
            status.update(f"[green]✓ Connected! {count} emails in {state.imap_folder}[/]")
        except Exception as e:
            status.update(f"[red]✗ Failed: {e}[/]")

    async def _test_webhook(self) -> None:
        status = self.query_one("#webhook-status", Static)
        url = self.app.state.webhook_url

        if not url:
            status.update("[yellow]Enter a webhook URL first[/]")
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json={
                    "text": "🧠 Mimir test notification — your webhook is working!",
                })
                resp.raise_for_status()
            status.update("[green]✓ Webhook test sent successfully![/]")
        except Exception as e:
            status.update(f"[red]✗ Failed: {e}[/]")
