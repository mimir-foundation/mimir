"""Connections screen — filtered list of note connections."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Label, Input, Select


class ConnectionsScreen(Screen):
    BINDINGS = [Binding("r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with Vertical(classes="panel"):
                yield Label("🔗 Connections", classes="panel-title")
                with Horizontal():
                    yield Input(placeholder="Min strength (0.0-1.0)", value="0.3", id="min-strength")
                    yield Select(
                        [("All types", ""), ("Related", "related"), ("Builds on", "builds_on"),
                         ("Contradicts", "contradicts"), ("Supports", "supports"),
                         ("Inspired by", "inspired_by")],
                        value="", id="conn-type-filter", prompt="Type",
                    )
                yield DataTable(id="conn-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#conn-table", DataTable)
        table.add_columns("Source", "Target", "Type", "Strength", "Explanation")
        table.cursor_type = "row"
        self.action_refresh()

    def action_refresh(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        try:
            min_str = self.query_one("#min-strength", Input).value.strip()
            try:
                min_strength = float(min_str)
            except ValueError:
                min_strength = 0.3

            conn_type = self.query_one("#conn-type-filter", Select).value or None

            data = await self.app.client.get_connections(
                connection_type=conn_type, min_strength=min_strength
            )
            table = self.query_one("#conn-table", DataTable)
            table.clear()

            # We need note titles — fetch them
            for c in data.get("connections", []):
                source_id = c.get("source_note_id", "")
                target_id = c.get("target_note_id", "")

                # Fetch titles (best effort)
                source_title = source_id[:8]
                target_title = target_id[:8]
                try:
                    sn = await self.app.client.get_note(source_id)
                    source_title = (sn.get("title") or "Untitled")[:25]
                except Exception:
                    pass
                try:
                    tn = await self.app.client.get_note(target_id)
                    target_title = (tn.get("title") or "Untitled")[:25]
                except Exception:
                    pass

                table.add_row(
                    source_title,
                    target_title,
                    c.get("connection_type", ""),
                    f"{c.get('strength', 0):.2f}",
                    (c.get("explanation") or "")[:35],
                    key=c.get("source_note_id", ""),
                )
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "min-strength":
            self.run_worker(self._load())

    def on_select_changed(self, event: Select.Changed) -> None:
        self.run_worker(self._load())

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        note_id = str(event.row_key.value)
        if note_id:
            from mimir_tui.screens.note_detail import NoteDetailScreen
            self.app.push_screen(NoteDetailScreen(note_id))
