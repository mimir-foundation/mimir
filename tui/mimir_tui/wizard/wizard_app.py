"""Setup wizard — interactive configuration for Mimir."""

import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Label, Static, ProgressBar
from textual.widget import Widget

from mimir_tui.wizard.wizard_state import WizardState
from mimir_tui.wizard.steps.step_ollama import OllamaStep
from mimir_tui.wizard.steps.step_harness import HarnessStep
from mimir_tui.wizard.steps.step_data import DataStep
from mimir_tui.wizard.steps.step_capture import CaptureStep
from mimir_tui.wizard.steps.step_messaging import MessagingStep


STEP_NAMES = ["Ollama", "AI Engine", "Data Paths", "Capture Sources", "Messaging Bridge"]


class WizardApp(App):
    """Mimir Setup Wizard."""

    TITLE = "Mimir Setup"
    CSS = """
    Screen {
        background: #0f172a;
    }
    Header {
        background: #1e1b4b;
        color: #c7d2fe;
    }
    Footer {
        background: #1e293b;
    }
    .wizard-header {
        height: 5;
        padding: 1 2;
        background: #1e293b;
    }
    .wizard-body {
        padding: 1 2;
    }
    .wizard-nav {
        height: 3;
        padding: 0 2;
        dock: bottom;
        background: #1e293b;
    }
    #nav-spacer {
        width: 1fr;
    }
    #btn-back, #btn-next {
        width: auto;
    }
    .panel-title {
        color: #818cf8;
        text-style: bold;
        margin-bottom: 1;
    }
    Input {
        background: #111827;
        border: solid #374151;
        margin-bottom: 1;
    }
    Input:focus {
        border: solid #6366f1;
    }
    Button {
        margin: 0 1;
    }
    TextArea {
        background: #111827;
        border: solid #374151;
        height: 12;
    }
    RichLog {
        background: #111827;
        border: solid #374151;
        height: 10;
    }
    """

    BINDINGS = [Binding("q", "quit", "Quit")]

    def __init__(self):
        super().__init__()
        self.state = WizardState()
        self._current_step = 0
        self._steps: list[Widget] = []

    def compose(self) -> ComposeResult:
        yield Header()

        # Progress header
        with Vertical(classes="wizard-header"):
            yield Label("", id="step-label")
            yield ProgressBar(total=len(STEP_NAMES), id="wizard-progress", show_eta=False)

        # Step content area
        with Vertical(id="step-container", classes="wizard-body"):
            yield OllamaStep(id="step-0")
            yield HarnessStep(id="step-1")
            yield DataStep(id="step-2")
            yield CaptureStep(id="step-3")
            yield MessagingStep(id="step-4")

        # Navigation
        with Horizontal(classes="wizard-nav"):
            yield Button("← Back", id="btn-back")
            yield Static("", id="nav-spacer")
            yield Button("Next →", id="btn-next", variant="primary")

        yield Footer()

    def on_mount(self) -> None:
        # Hide all steps except the first
        for i in range(len(STEP_NAMES)):
            widget = self.query_one(f"#step-{i}")
            widget.display = i == 0
            self._steps.append(widget)

        self._update_ui()

    def _update_ui(self) -> None:
        step = self._current_step
        total = len(STEP_NAMES)

        self.query_one("#step-label", Label).update(
            f"Step {step + 1} of {total}: {STEP_NAMES[step]}"
        )
        self.query_one("#wizard-progress", ProgressBar).update(progress=step + 1)

        # Show/hide steps
        for i, widget in enumerate(self._steps):
            widget.display = i == step

        # Update nav buttons
        back_btn = self.query_one("#btn-back", Button)
        next_btn = self.query_one("#btn-next", Button)
        back_btn.disabled = step == 0
        next_btn.label = "Finish ✓" if step == total - 1 else "Next →"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            if self._current_step > 0:
                self._current_step -= 1
                self._update_ui()
        elif event.button.id == "btn-next":
            if self._current_step < len(STEP_NAMES) - 1:
                self._current_step += 1
                self._update_ui()
            else:
                self.run_worker(self._finish())

    async def _finish(self) -> None:
        """Save configuration and optionally launch Docker."""
        # Save TUI config
        from mimir_tui.config import TuiConfig, save_config

        base_url = f"http://localhost:3080"
        save_config(TuiConfig(base_url=base_url, api_key=self.state.api_key))

        # Generate .env file
        env_content = self.state.generate_env()
        env_path = Path(".env")
        env_path.write_text(env_content)

        # Launch Docker if requested
        if self.state.launch_docker:
            try:
                subprocess.Popen(
                    ["docker-compose", "up", "-d", "--build"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                try:
                    subprocess.Popen(
                        ["docker", "compose", "up", "-d", "--build"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except FileNotFoundError:
                    pass

        self.exit(message="✓ Setup complete! Run 'mimir' to launch the TUI.")
