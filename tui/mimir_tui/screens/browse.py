"""Browse screen — notes, concepts, entities in tabs."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Button, Label, TabbedContent, TabPane, Select


class BrowseScreen(Screen):
    BINDINGS = [
        Binding("n", "next_page", "Next"),
        Binding("p", "prev_page", "Prev"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self):
        super().__init__()
        self._page = 0
        self._sort = "recent"
        self._limit = 20

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Notes", id="tab-notes"):
                with Horizontal():
                    yield Select(
                        [("Recent", "recent"), ("Starred", "starred"), ("Most Connected", "most_connected")],
                        value="recent", id="sort-select", prompt="Sort",
                    )
                yield DataTable(id="notes-table")
                with Horizontal():
                    yield Button("← Prev", id="btn-prev")
                    yield Label("Page 1", id="page-label")
                    yield Button("Next →", id="btn-next")

            with TabPane("Concepts", id="tab-concepts"):
                yield DataTable(id="concepts-table")

            with TabPane("Entities", id="tab-entities"):
                yield Select(
                    [("All", ""), ("Person", "person"), ("Company", "company"),
                     ("Project", "project"), ("Tool", "tool"), ("Book", "book"),
                     ("Place", "place"), ("Event", "event")],
                    value="", id="entity-type-select", prompt="Type",
                )
                yield DataTable(id="entities-table")
        yield Footer()

    def on_mount(self) -> None:
        nt = self.query_one("#notes-table", DataTable)
        nt.add_columns("Title", "Source", "Concepts", "Status", "Date")
        nt.cursor_type = "row"

        ct = self.query_one("#concepts-table", DataTable)
        ct.add_columns("Name", "Notes", "Description")
        ct.cursor_type = "row"

        et = self.query_one("#entities-table", DataTable)
        et.add_columns("Name", "Type")
        et.cursor_type = "row"

        self.action_refresh()

    def action_refresh(self) -> None:
        self.run_worker(self._load_all())

    async def _load_all(self) -> None:
        await self._load_notes()
        await self._load_concepts()
        await self._load_entities()

    async def _load_notes(self) -> None:
        try:
            data = await self.app.client.get_notes(
                sort=self._sort, limit=self._limit, offset=self._page * self._limit
            )
            table = self.query_one("#notes-table", DataTable)
            table.clear()
            for n in data.get("notes", []):
                title = (n.get("title") or n.get("raw_content", "")[:35] or "Untitled")[:40]
                concepts = ", ".join(n.get("concepts", [])[:3])
                date = (n.get("created_at") or "")[:10]
                table.add_row(
                    title, n.get("source_type", ""), concepts,
                    n.get("processing_status", ""), date, key=n["id"],
                )
            total = data.get("total", 0)
            pages = max(1, (total + self._limit - 1) // self._limit)
            self.query_one("#page-label", Label).update(f"Page {self._page + 1}/{pages}")
        except Exception:
            pass

    async def _load_concepts(self) -> None:
        try:
            data = await self.app.client.get_concepts()
            table = self.query_one("#concepts-table", DataTable)
            table.clear()
            for c in data.get("concepts", []):
                table.add_row(
                    c["name"], str(c.get("note_count", 0)),
                    (c.get("description") or "")[:50], key=c["id"],
                )
        except Exception:
            pass

    async def _load_entities(self) -> None:
        try:
            etype = self.query_one("#entity-type-select", Select).value
            data = await self.app.client.get_entities(entity_type=etype or None)
            table = self.query_one("#entities-table", DataTable)
            table.clear()
            for e in data.get("entities", []):
                table.add_row(e["name"], e.get("entity_type", ""), key=e["id"])
        except Exception:
            pass

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "sort-select":
            self._sort = event.value
            self._page = 0
            self.run_worker(self._load_notes())
        elif event.select.id == "entity-type-select":
            self.run_worker(self._load_entities())

    def action_next_page(self) -> None:
        self._page += 1
        self.run_worker(self._load_notes())

    def action_prev_page(self) -> None:
        self._page = max(0, self._page - 1)
        self.run_worker(self._load_notes())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-next":
            self.action_next_page()
        elif event.button.id == "btn-prev":
            self.action_prev_page()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        table_id = event.data_table.id
        if table_id == "notes-table":
            from mimir_tui.screens.note_detail import NoteDetailScreen
            self.app.push_screen(NoteDetailScreen(key))
