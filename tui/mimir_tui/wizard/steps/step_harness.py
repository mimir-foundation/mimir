"""Wizard Step 2: AI harness preset selection."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Button, Label, Static, RadioButton, RadioSet


class HarnessStep(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Step 2: AI Engine Preset", classes="panel-title")
        yield Static("Choose how Mimir routes AI operations. You can change this later.")
        yield Static("")

        with RadioSet(id="preset-select"):
            yield RadioButton("Local — all via Ollama (free, private, requires GPU for speed)", id="w-local", value=True)
            yield RadioButton("Hybrid — local embeddings + cloud reasoning (best balance)", id="w-hybrid")
            yield RadioButton("Cloud — all cloud APIs (best quality, costs money)", id="w-cloud")
            yield RadioButton("Budget — local + cheap cloud model", id="w-budget")

        yield Static("")
        yield Label("API Keys (only needed for hybrid/cloud/budget)", classes="panel-title")
        yield Label("Anthropic API Key")
        yield Input(placeholder="sk-ant-...", password=True, id="w-anthropic-key")
        yield Label("OpenAI API Key")
        yield Input(placeholder="sk-...", password=True, id="w-openai-key")
        yield Label("Google API Key")
        yield Input(placeholder="AIza...", password=True, id="w-google-key")
        yield Static("", id="harness-status")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        preset_map = {
            "w-local": "local",
            "w-hybrid": "hybrid",
            "w-cloud": "cloud",
            "w-budget": "budget",
        }
        self.app.state.preset = preset_map.get(event.pressed.id, "local")

    def on_input_changed(self, event: Input.Changed) -> None:
        state = self.app.state
        if event.input.id == "w-anthropic-key":
            state.anthropic_api_key = event.value
        elif event.input.id == "w-openai-key":
            state.openai_api_key = event.value
        elif event.input.id == "w-google-key":
            state.google_api_key = event.value
