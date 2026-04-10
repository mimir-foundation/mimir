"""Wizard Step 3: Data paths + .env generation."""

import secrets
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Button, Label, Static, TextArea, Checkbox


class DataStep(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Step 3: Data Paths & Configuration", classes="panel-title")
        yield Static("Configure where Mimir stores its data and generate the .env file.")
        yield Static("")

        yield Label("Data directory")
        yield Input(value="./data", id="w-data-path")

        yield Label("Inbox folder (file watcher)")
        yield Input(value="./data/inbox", id="w-inbox-path")

        yield Label("API Key (secures your capture endpoints)")
        yield Input(value=secrets.token_urlsafe(24), id="w-api-key")

        yield Label("Daily brief time (HH:MM)")
        yield Input(value="07:00", id="w-brief-time")

        yield Static("")
        yield Button("Preview .env", id="btn-preview-env", variant="primary")
        yield TextArea(id="env-preview", read_only=True)

        yield Static("")
        yield Checkbox("Launch docker-compose after finishing wizard", id="w-launch-docker")

        yield Static("", id="data-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-preview-env":
            self._update_state()
            preview = self.query_one("#env-preview", TextArea)
            env_content = self.app.state.generate_env()
            preview.clear()
            preview.insert(env_content)

    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_state()

    def _update_state(self) -> None:
        state = self.app.state
        state.data_path = self.query_one("#w-data-path", Input).value.strip()
        state.inbox_path = self.query_one("#w-inbox-path", Input).value.strip()
        state.api_key = self.query_one("#w-api-key", Input).value.strip()
        state.brief_time = self.query_one("#w-brief-time", Input).value.strip()
        state.launch_docker = self.query_one("#w-launch-docker", Checkbox).value
