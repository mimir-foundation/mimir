"""Search screen — search + ask mode with debounced input."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Header, Footer, Input, DataTable, RichLog, RadioButton, RadioSet, Select, Static


class SearchScreen(Screen):
    BINDINGS = [Binding("escape", "app.switch_screen('dashboard')", "Back")]

    def __init__(self):
        super().__init__()
        self._debounce_timer: Timer | None = None
        self._mode = "search"

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with RadioSet(id="mode-toggle"):
                yield RadioButton("Search", value=True, id="mode-search")
                yield RadioButton("Ask", id="mode-ask")
            yield Select(
                [("All sources", ""), ("Manual", "manual"), ("URL", "url"),
                 ("File", "file"), ("Email", "email")],
                value="",
                id="source-filter",
                prompt="Source type",
            )
            yield Input(placeholder="Search your knowledge base...", id="search-input")
            yield DataTable(id="results-table")
            yield RichLog(id="ask-output", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.add_columns("Title", "Source", "Score", "Date")
        table.cursor_type = "row"
        self.query_one("#ask-output").display = False
        self.query_one("#search-input").focus()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self._mode = "ask" if event.pressed.id == "mode-ask" else "search"
        table = self.query_one("#results-table")
        ask_out = self.query_one("#ask-output")
        source = self.query_one("#source-filter")
        table.display = self._mode == "search"
        ask_out.display = self._mode == "ask"
        source.display = self._mode == "search"

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "search-input":
            return
        if self._debounce_timer:
            self._debounce_timer.stop()
        self._debounce_timer = self.set_timer(0.4, self._do_search)

    def _do_search(self) -> None:
        query = self.query_one("#search-input", Input).value.strip()
        if len(query) < 2:
            return
        self.run_worker(self._execute_search(query))

    async def _execute_search(self, query: str) -> None:
        try:
            source = self.query_one("#source-filter", Select).value
            source_type = source if source else None

            if self._mode == "ask":
                data = await self.app.client.search(query, mode="ask")
                log = self.query_one("#ask-output", RichLog)
                log.clear()
                log.write(f"[bold cyan]Question:[/] {query}\n")
                log.write(f"\n{data.get('answer', 'No answer available.')}\n")
                sources = data.get("sources", [])
                if sources:
                    log.write("\n[dim]Sources:[/]")
                    for s in sources:
                        log.write(f"  • {s.get('title', 'Untitled')} (score: {s.get('score', 0):.4f})")
            else:
                data = await self.app.client.search(query, mode="search", source_type=source_type)
                table = self.query_one("#results-table", DataTable)
                table.clear()
                for r in data.get("results", []):
                    title = (r.get("title") or "Untitled")[:45]
                    date = (r.get("created_at") or "")[:10]
                    table.add_row(
                        title,
                        r.get("source_type", ""),
                        f"{r.get('score', 0):.4f}",
                        date,
                        key=r["note_id"],
                    )
        except Exception as e:
            if self._mode == "ask":
                log = self.query_one("#ask-output", RichLog)
                log.clear()
                log.write(f"[red]Error: {e}[/]")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        note_id = str(event.row_key.value)
        from mimir_tui.screens.note_detail import NoteDetailScreen
        self.app.push_screen(NoteDetailScreen(note_id))
