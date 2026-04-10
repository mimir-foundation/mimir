"""Settings screen — harness config, presets, settings, export."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Label, Button, Static, DataTable, Input, RadioButton, RadioSet, TabbedContent, TabPane


class SettingsScreen(Screen):
    BINDINGS = [Binding("r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Harness", id="tab-harness"):
                with Vertical(classes="panel"):
                    yield Label("AI Engine Configuration", classes="panel-title")
                    yield DataTable(id="harness-table")
                    yield Static("")
                    yield Label("Presets", classes="panel-title")
                    with RadioSet(id="preset-set"):
                        yield RadioButton("Local — all Ollama (free, private)", id="preset-local", value=True)
                        yield RadioButton("Hybrid — local embed + cloud reason", id="preset-hybrid")
                        yield RadioButton("Cloud — all cloud APIs", id="preset-cloud")
                        yield RadioButton("Budget — local + cheap cloud", id="preset-budget")
                    yield Button("Apply Preset", id="btn-apply-preset", variant="primary")
                    yield Static("", id="preset-status")

            with TabPane("Settings", id="tab-settings"):
                with Vertical(classes="panel"):
                    yield Label("General Settings", classes="panel-title")
                    yield Label("Brief time (HH:MM)")
                    yield Input(placeholder="07:00", id="setting-brief-time")
                    yield Label("Webhook URL")
                    yield Input(placeholder="https://hooks.slack.com/...", id="setting-webhook")
                    yield Button("Save Settings", id="btn-save-settings", variant="primary")
                    yield Static("", id="settings-status")

            with TabPane("Export", id="tab-export"):
                with Vertical(classes="panel"):
                    yield Label("Export & Backup", classes="panel-title")
                    yield Static("Download your data for backup or migration.")
                    with Horizontal():
                        yield Button("Export JSON", id="btn-export-json")
                        yield Button("Export Markdown", id="btn-export-md")
                    yield Static("", id="export-status")

        yield Footer()

    def on_mount(self) -> None:
        ht = self.query_one("#harness-table", DataTable)
        ht.add_columns("Operation", "Provider", "Model", "Status")
        self.action_refresh()

    def action_refresh(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        try:
            config = await self.app.client.get_harness_config()
            health = await self.app.client.get_harness_health()
            health_map = health.get("status", {})

            table = self.query_one("#harness-table", DataTable)
            table.clear()
            for op, cfg in config.items():
                ok = health_map.get(op, False)
                status = "✓ OK" if ok else "✗ Down"
                table.add_row(op, cfg.get("provider", ""), cfg.get("model", ""), status)
        except Exception:
            pass

        try:
            settings = await self.app.client.get_settings()
            agent = settings.get("agent", {})
            notif = settings.get("notifications", {})
            self.query_one("#setting-brief-time", Input).value = agent.get("brief_time", "07:00")
            self.query_one("#setting-webhook", Input).value = notif.get("webhook_url", "") or ""
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-apply-preset":
            self.run_worker(self._apply_preset())
        elif bid == "btn-save-settings":
            self.run_worker(self._save_settings())
        elif bid == "btn-export-json":
            self.run_worker(self._export("json"))
        elif bid == "btn-export-md":
            self.run_worker(self._export("markdown"))

    async def _apply_preset(self) -> None:
        status = self.query_one("#preset-status", Static)
        radio = self.query_one("#preset-set", RadioSet)
        pressed = radio.pressed_button
        if not pressed:
            return
        preset = pressed.id.replace("preset-", "")
        try:
            await self.app.client.apply_preset(preset)
            status.update(f"[green]✓ Applied '{preset}' preset[/]")
            await self._load()
        except Exception as e:
            status.update(f"[red]Error: {e}[/]")

    async def _save_settings(self) -> None:
        status = self.query_one("#settings-status", Static)
        try:
            brief_time = self.query_one("#setting-brief-time", Input).value.strip()
            webhook = self.query_one("#setting-webhook", Input).value.strip()

            await self.app.client.put_setting("agent", {
                "brief_enabled": True,
                "brief_time": brief_time or "07:00",
                "brief_delivery": ["dashboard"],
                "connection_scan_interval_hours": 6,
                "max_llm_calls_per_scan": 50,
                "resurface_enabled": True,
                "spaced_rep_enabled": True,
                "spaced_rep_intervals_days": [1, 3, 7, 14, 30, 60, 90],
            })
            await self.app.client.put_setting("notifications", {
                "webhook_url": webhook or None,
                "webhook_type": "generic",
            })
            status.update("[green]✓ Settings saved[/]")
        except Exception as e:
            status.update(f"[red]Error: {e}[/]")

    async def _export(self, fmt: str) -> None:
        status = self.query_one("#export-status", Static)
        try:
            downloads = Path.home() / "Downloads"
            downloads.mkdir(exist_ok=True)

            if fmt == "json":
                data = await self.app.client.export_json()
                path = downloads / "mimir-export.json"
                path.write_bytes(data)
            else:
                data = await self.app.client.export_markdown()
                path = downloads / "mimir-export.zip"
                path.write_bytes(data)

            status.update(f"[green]✓ Saved to {path}[/]")
        except Exception as e:
            status.update(f"[red]Error: {e}[/]")
