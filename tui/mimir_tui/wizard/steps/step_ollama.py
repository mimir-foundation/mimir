"""Wizard Step 1: Ollama connection + model pull."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Button, Label, RichLog, Static, Checkbox, Select

import httpx


GEMMA4_MODELS = [
    ("gemma4 — 9.6 GB, default balanced (e4b)", "gemma4"),
    ("gemma4:e2b — 7.2 GB, smallest, fast", "gemma4:e2b"),
    ("gemma4:26b — 18 GB, MoE, high quality", "gemma4:26b"),
    ("gemma4:31b — 20 GB, dense, best quality", "gemma4:31b"),
]


class OllamaStep(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Step 1: Ollama Connection", classes="panel-title")
        yield Static("Mimir uses Ollama for local LLM and embedding models.")
        yield Label("Ollama URL")
        yield Input(value="http://localhost:11434", id="ollama-url")
        yield Button("Test Connection", id="btn-test-ollama", variant="primary")
        yield Static("", id="ollama-status")
        yield Static("")
        yield Label("Gemma 4 model variant")
        yield Select(GEMMA4_MODELS, value="gemma4", id="gemma4-select")
        yield Checkbox("Pull selected Gemma 4 model", True, id="pull-gemma4")
        yield Checkbox("Pull nomic-embed-text (embedding model)", True, id="pull-nomic")
        yield Button("Pull Selected Models", id="btn-pull-models")
        yield RichLog(id="ollama-log", markup=True, max_lines=50)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-test-ollama":
            self.run_worker(self._test_connection())
        elif event.button.id == "btn-pull-models":
            self.run_worker(self._pull_models())

    async def _test_connection(self) -> None:
        status = self.query_one("#ollama-status", Static)
        url = self.query_one("#ollama-url", Input).value.strip()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{url}/api/tags")
                resp.raise_for_status()
                data = resp.json()

            models = [m["name"] for m in data.get("models", [])]
            status.update(f"[green]✓ Connected! Models: {', '.join(models) or 'none'}[/]")

            # Update wizard state
            wizard = self.app
            wizard.state.ollama_url = url
            wizard.state.ollama_connected = True

            # Check GPU
            log = self.query_one("#ollama-log", RichLog)
            if models:
                try:
                    show_resp = await httpx.AsyncClient(timeout=10.0).__aenter__()
                    # Simplified: just note models are available
                    log.write(f"[dim]Available models: {', '.join(models)}[/]")
                except Exception:
                    pass

        except Exception as e:
            status.update(f"[red]✗ Connection failed: {e}[/]")

    async def _pull_models(self) -> None:
        url = self.query_one("#ollama-url", Input).value.strip()
        log = self.query_one("#ollama-log", RichLog)
        log.clear()

        models_to_pull = []
        if self.query_one("#pull-gemma4", Checkbox).value:
            selected = self.query_one("#gemma4-select", Select).value
            if selected and selected != Select.BLANK:
                models_to_pull.append(str(selected))
        if self.query_one("#pull-nomic", Checkbox).value:
            models_to_pull.append("nomic-embed-text")

        for model in models_to_pull:
            log.write(f"[cyan]Pulling {model}...[/]")
            try:
                async with httpx.AsyncClient(timeout=600.0) as client:
                    async with client.stream("POST", f"{url}/api/pull", json={"name": model}) as resp:
                        async for line in resp.aiter_lines():
                            if line.strip():
                                import json
                                try:
                                    data = json.loads(line)
                                    status = data.get("status", "")
                                    if "pulling" in status or "downloading" in status:
                                        total = data.get("total", 0)
                                        completed = data.get("completed", 0)
                                        if total > 0:
                                            pct = int(completed / total * 100)
                                            log.write(f"  {status} {pct}%")
                                        else:
                                            log.write(f"  {status}")
                                    elif status:
                                        log.write(f"  {status}")
                                except json.JSONDecodeError:
                                    pass

                log.write(f"[green]✓ {model} pulled successfully[/]")
                self.app.state.models_pulled.append(model)
            except Exception as e:
                log.write(f"[red]✗ Failed to pull {model}: {e}[/]")
