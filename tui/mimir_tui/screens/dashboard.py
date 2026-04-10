"""Dashboard screen — stats, daily brief, resurface items, recent notes."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, DataTable, Markdown, Button


class DashboardScreen(Screen):
    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("g", "generate_brief", "Gen Brief"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            # Stats bar
            with Horizontal(classes="stats-bar"):
                yield Label("Notes: -", id="stat-notes", classes="stat-card")
                yield Label("Concepts: -", id="stat-concepts", classes="stat-card")
                yield Label("Connections: -", id="stat-connections", classes="stat-card")
                yield Label("Entities: -", id="stat-entities", classes="stat-card")

            # Daily brief
            with Vertical(classes="brief-panel"):
                yield Label("📰 Daily Brief", classes="panel-title")
                yield Markdown("*No brief yet. Press [g] to generate.*", id="brief-content")

            # Resurface
            with Vertical(classes="panel"):
                yield Label("🔔 Resurface", classes="panel-title")
                yield DataTable(id="resurface-table")

            # Recent notes
            with Vertical(classes="panel"):
                yield Label("📋 Recent Captures", classes="panel-title")
                yield DataTable(id="recent-table")

        yield Footer()

    def on_mount(self) -> None:
        # Setup resurface table
        rt = self.query_one("#resurface-table", DataTable)
        rt.add_columns("Title", "Reason", "Type")
        rt.cursor_type = "row"

        # Setup recent table
        nt = self.query_one("#recent-table", DataTable)
        nt.add_columns("Title", "Source", "Status", "Date")
        nt.cursor_type = "row"

        # Initial load
        self.action_refresh()
        self.set_interval(10, self._refresh_stats)
        self.set_interval(30, self._refresh_all)

    def action_refresh(self) -> None:
        self.run_worker(self._refresh_all())

    def action_generate_brief(self) -> None:
        self.run_worker(self._gen_brief())

    async def _refresh_stats(self) -> None:
        try:
            stats = await self.app.client.get_stats()
            self.query_one("#stat-notes").update(f"Notes: {stats['notes']}")
            self.query_one("#stat-concepts").update(f"Concepts: {stats['concepts']}")
            self.query_one("#stat-connections").update(f"Connections: {stats['connections']}")
            self.query_one("#stat-entities").update(f"Entities: {stats['entities']}")
        except Exception:
            pass

    async def _refresh_all(self) -> None:
        await self._refresh_stats()
        await self._refresh_brief()
        await self._refresh_resurface()
        await self._refresh_recent()

    async def _refresh_brief(self) -> None:
        try:
            data = await self.app.client.get_brief()
            brief = data.get("brief")
            md = self.query_one("#brief-content", Markdown)
            if brief and brief.get("content"):
                await md.update(f"**{brief['brief_date']}**\n\n{brief['content']}")
            else:
                await md.update("*No brief yet. Press [g] to generate.*")
        except Exception:
            pass

    async def _refresh_resurface(self) -> None:
        try:
            data = await self.app.client.get_resurface(limit=5)
            table = self.query_one("#resurface-table", DataTable)
            table.clear()
            for item in data.get("items", []):
                table.add_row(
                    item.get("note_title", "Untitled")[:40],
                    item.get("reason", "")[:50],
                    item.get("queue_type", "").replace("_", " "),
                    key=item["id"],
                )
        except Exception:
            pass

    async def _refresh_recent(self) -> None:
        try:
            data = await self.app.client.get_notes(sort="recent", limit=10)
            table = self.query_one("#recent-table", DataTable)
            table.clear()
            for note in data.get("notes", []):
                title = (note.get("title") or note.get("raw_content", "")[:40] or "Untitled")[:45]
                date = (note.get("created_at") or "")[:16]
                status = note.get("processing_status", "")
                table.add_row(title, note.get("source_type", ""), status, date, key=note["id"])
        except Exception:
            pass

    async def _gen_brief(self) -> None:
        try:
            await self.app.client.generate_brief()
            await self._refresh_brief()
        except Exception:
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        note_id = str(event.row_key.value)
        # Check if it's from resurface or recent table
        if event.data_table.id == "resurface-table":
            self.run_worker(self._click_resurface(note_id))
        else:
            from mimir_tui.screens.note_detail import NoteDetailScreen
            self.app.push_screen(NoteDetailScreen(note_id))

    async def _click_resurface(self, item_id: str) -> None:
        try:
            # Get the note_id from the resurface item
            data = await self.app.client.get_resurface(limit=20)
            for item in data.get("items", []):
                if item["id"] == item_id:
                    await self.app.client.click_resurface(item_id)
                    from mimir_tui.screens.note_detail import NoteDetailScreen
                    self.app.push_screen(NoteDetailScreen(item["note_id"]))
                    break
            await self._refresh_resurface()
        except Exception:
            pass
