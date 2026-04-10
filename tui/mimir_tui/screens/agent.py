"""Agent screen — brief/scan/taxonomy controls, interests, activity log."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Label, DataTable, RichLog, Static


class AgentScreen(Screen):
    BINDINGS = [Binding("r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            # Controls
            with Vertical(classes="panel"):
                yield Label("🤖 Agent Controls", classes="panel-title")
                with Horizontal():
                    yield Button("Generate Brief", id="btn-brief", variant="primary")
                    yield Button("Deep Scan", id="btn-scan", variant="warning")
                    yield Button("Rebuild Taxonomy", id="btn-taxonomy")
                yield Static("", id="action-status")

            # Interests
            with Vertical(classes="panel"):
                yield Label("🎯 Current Interests", classes="panel-title")
                yield DataTable(id="interests-table")

            # Activity Log
            with Vertical(classes="panel"):
                yield Label("📋 Activity Log", classes="panel-title")
                yield RichLog(id="activity-log", markup=True, max_lines=100)
        yield Footer()

    def on_mount(self) -> None:
        it = self.query_one("#interests-table", DataTable)
        it.add_columns("Topic", "Score")
        it.cursor_type = "row"
        self.action_refresh()
        self.set_interval(15, self._refresh_log)

    def action_refresh(self) -> None:
        self.run_worker(self._refresh_all())

    async def _refresh_all(self) -> None:
        await self._refresh_interests()
        await self._refresh_log()

    async def _refresh_interests(self) -> None:
        try:
            data = await self.app.client.get_interests()
            table = self.query_one("#interests-table", DataTable)
            table.clear()
            for i in data.get("interests", [])[:15]:
                table.add_row(i["topic"], f"{i['score']:.2f}")
        except Exception:
            pass

    async def _refresh_log(self) -> None:
        try:
            data = await self.app.client.get_activity(limit=20)
            log = self.query_one("#activity-log", RichLog)
            log.clear()
            for entry in data.get("log", []):
                status_color = {
                    "complete": "green",
                    "running": "blue",
                    "error": "red",
                }.get(entry.get("status", ""), "white")

                ts = (entry.get("started_at") or "")[:19]
                action = entry.get("action_type", "").replace("_", " ")
                status = entry.get("status", "")
                err = entry.get("error_message", "")

                line = f"[dim]{ts}[/] [{status_color}]{status:>8}[/] {action}"
                if err:
                    line += f" [red]({err[:40]})[/]"
                log.write(line)
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        status = self.query_one("#action-status", Static)
        if event.button.id == "btn-brief":
            status.update("[blue]Generating brief...[/]")
            self.run_worker(self._run_action("brief"))
        elif event.button.id == "btn-scan":
            status.update("[blue]Running deep scan...[/]")
            self.run_worker(self._run_action("scan"))
        elif event.button.id == "btn-taxonomy":
            status.update("[blue]Rebuilding taxonomy...[/]")
            self.run_worker(self._run_action("taxonomy"))

    async def _run_action(self, action: str) -> None:
        status = self.query_one("#action-status", Static)
        try:
            if action == "brief":
                result = await self.app.client.generate_brief()
                status.update("[green]✓ Brief generated[/]")
            elif action == "scan":
                result = await self.app.client.trigger_deep_scan()
                r = result.get("result", {})
                status.update(f"[green]✓ Deep scan: {r.get('connections_found', 0)} connections found[/]")
            elif action == "taxonomy":
                result = await self.app.client.trigger_taxonomy_rebuild()
                r = result.get("result", {})
                status.update(f"[green]✓ Taxonomy: {r.get('merged', 0)} merged, {r.get('pruned', 0)} pruned[/]")
            await self._refresh_log()
        except Exception as e:
            status.update(f"[red]Error: {e}[/]")
