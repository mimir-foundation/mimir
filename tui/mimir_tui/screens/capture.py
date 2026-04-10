"""Capture screen — modal overlay for quick note/URL/clipboard capture."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Input, TextArea, Button, Label, TabbedContent, TabPane, Static


class CaptureScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("📝 Capture", classes="panel-title")
            with TabbedContent():
                with TabPane("Note", id="tab-note"):
                    yield Input(placeholder="Title (optional)", id="note-title")
                    yield TextArea(id="note-content")
                    yield Input(placeholder="Tags (comma-separated)", id="note-tags")

                with TabPane("URL", id="tab-url"):
                    yield Input(placeholder="https://...", id="url-input")
                    yield Input(placeholder="Context (optional)", id="url-context")

                with TabPane("Clipboard", id="tab-clipboard"):
                    yield Static("Paste content below:")
                    yield TextArea(id="clipboard-content")

            yield Static("", id="capture-status")
            with Horizontal():
                yield Button("Cancel", id="btn-cancel")
                yield Button("Capture", id="btn-capture", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#note-content", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-capture":
            self.run_worker(self._capture())

    async def _capture(self) -> None:
        status = self.query_one("#capture-status", Static)

        try:
            # Determine which tab is active
            tabs = self.query_one(TabbedContent)
            active = tabs.active

            if active == "tab-note":
                content = self.query_one("#note-content", TextArea).text.strip()
                if not content:
                    status.update("[red]Content is required[/]")
                    return
                title = self.query_one("#note-title", Input).value.strip() or None
                tags_str = self.query_one("#note-tags", Input).value.strip()
                tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else None
                await self.app.client.capture_note(content, title=title, tags=tags)

            elif active == "tab-url":
                url = self.query_one("#url-input", Input).value.strip()
                if not url:
                    status.update("[red]URL is required[/]")
                    return
                context = self.query_one("#url-context", Input).value.strip() or None
                await self.app.client.capture_url(url, context=context)

            elif active == "tab-clipboard":
                content = self.query_one("#clipboard-content", TextArea).text.strip()
                if not content:
                    status.update("[red]Content is required[/]")
                    return
                await self.app.client.capture_clipboard(content)

            status.update("[green]✓ Captured![/]")
            # Clear fields
            for input_w in self.query(Input):
                input_w.value = ""
            for ta in self.query(TextArea):
                ta.clear()
            # Auto-dismiss after short delay
            self.set_timer(1.0, self.dismiss)

        except Exception as e:
            status.update(f"[red]Error: {e}[/]")

    def action_dismiss(self) -> None:
        self.dismiss()
