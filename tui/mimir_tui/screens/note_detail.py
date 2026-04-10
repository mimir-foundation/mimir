"""Note detail screen — markdown content + metadata sidebar."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, Markdown, Button, DataTable


class NoteDetailScreen(Screen):
    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("s", "toggle_star", "Star"),
        Binding("a", "toggle_archive", "Archive"),
        Binding("delete", "delete_note", "Delete"),
    ]

    def __init__(self, note_id: str):
        super().__init__()
        self.note_id = note_id
        self._note_data: dict = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            # Main content
            with VerticalScroll(id="content-area"):
                yield Label("Loading...", id="note-title", classes="panel-title")
                yield Static("", id="synthesis-box", classes="brief-panel")
                yield Markdown("", id="note-content")

            # Sidebar
            with Vertical(classes="sidebar"):
                yield Label("", id="meta-source")
                yield Label("", id="meta-date")
                yield Label("", id="meta-words")
                yield Label("", id="meta-status")
                yield Static("")  # spacer
                with Horizontal():
                    yield Button("★ Star", id="btn-star", variant="warning")
                    yield Button("Archive", id="btn-archive")
                yield Static("")
                yield Label("Concepts", classes="panel-title")
                yield Static("", id="concepts-list")
                yield Label("Entities", classes="panel-title")
                yield Static("", id="entities-list")
                yield Label("Connections", classes="panel-title")
                yield DataTable(id="connections-table")
        yield Footer()

    def on_mount(self) -> None:
        ct = self.query_one("#connections-table", DataTable)
        ct.add_columns("Title", "Type", "Str")
        ct.cursor_type = "row"
        self.run_worker(self._load_note())

    async def _load_note(self) -> None:
        try:
            note = await self.app.client.get_note(self.note_id)
            self._note_data = note

            title = note.get("title") or "Untitled"
            self.query_one("#note-title", Label).update(title)

            synthesis = note.get("synthesis", "")
            self.query_one("#synthesis-box", Static).update(synthesis or "[dim]No synthesis yet[/]")

            content = note.get("processed_content") or note.get("raw_content", "")
            await self.query_one("#note-content", Markdown).update(content)

            # Sidebar metadata
            self.query_one("#meta-source").update(f"Source: {note.get('source_type', '')}")
            self.query_one("#meta-date").update(f"Date: {(note.get('created_at') or '')[:16]}")
            wc = note.get("word_count")
            self.query_one("#meta-words").update(f"Words: {wc}" if wc else "")
            self.query_one("#meta-status").update(f"Status: {note.get('processing_status', '')}")

            star_btn = self.query_one("#btn-star", Button)
            star_btn.label = "★ Starred" if note.get("is_starred") else "☆ Star"

            # Concepts
            concepts = note.get("concepts", [])
            concept_text = ", ".join(
                c.get("name", c) if isinstance(c, dict) else str(c) for c in concepts
            ) or "[dim]None[/]"
            self.query_one("#concepts-list", Static).update(concept_text)

            # Entities
            entities = note.get("entities", [])
            entity_text = ", ".join(
                f"{e['name']} ({e.get('entity_type', '')})" for e in entities
            ) or "[dim]None[/]"
            self.query_one("#entities-list", Static).update(entity_text)

            # Connections
            table = self.query_one("#connections-table", DataTable)
            table.clear()
            for c in note.get("connections", []):
                table.add_row(
                    (c.get("target_title") or "Untitled")[:30],
                    c.get("connection_type", ""),
                    f"{c.get('strength', 0):.1f}",
                    key=c.get("target_note_id", ""),
                )
        except Exception as e:
            self.query_one("#note-title", Label).update(f"Error: {e}")

    def action_toggle_star(self) -> None:
        starred = not self._note_data.get("is_starred", False)
        self.run_worker(self._update({"is_starred": starred}))

    def action_toggle_archive(self) -> None:
        archived = not self._note_data.get("is_archived", False)
        self.run_worker(self._update({"is_archived": archived}))

    def action_delete_note(self) -> None:
        self.run_worker(self._delete())

    async def _update(self, data: dict) -> None:
        try:
            await self.app.client.update_note(self.note_id, data)
            await self._load_note()
        except Exception:
            pass

    async def _delete(self) -> None:
        try:
            await self.app.client.delete_note(self.note_id)
            self.app.pop_screen()
        except Exception:
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        target_id = str(event.row_key.value)
        if target_id:
            self.app.push_screen(NoteDetailScreen(target_id))

    def action_pop_screen(self) -> None:
        self.app.pop_screen()
