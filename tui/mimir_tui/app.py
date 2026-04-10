"""Main Mimir TUI application."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label
from textual.containers import Center, Vertical

from mimir_tui.client import MimirClient
from mimir_tui.config import load_config


class ConnectionErrorScreen(Screen):
    """Shown when the backend is unreachable."""

    BINDINGS = [
        Binding("r", "retry", "Retry"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(classes="panel"):
                yield Label("⚠ Cannot connect to Mimir backend", classes="panel-title")
                yield Static(
                    "Make sure the backend is running:\n\n"
                    "  docker-compose up -d\n\n"
                    "Or run the setup wizard:\n\n"
                    "  mimir setup\n\n"
                    "Press [bold]r[/] to retry, [bold]q[/] to quit."
                )
        yield Footer()

    def action_retry(self):
        self.app.pop_screen()
        self.app.push_screen("dashboard")

    def action_quit(self):
        self.app.exit()


class MimirApp(App):
    """Mimir Terminal UI."""

    TITLE = "Mimir"
    SUB_TITLE = "Your Second Brain"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("1", "switch_screen('dashboard')", "Dashboard", priority=True),
        Binding("2", "switch_screen('search')", "Search", priority=True),
        Binding("3", "switch_screen('browse')", "Browse", priority=True),
        Binding("4", "switch_screen('agent')", "Agent", priority=True),
        Binding("5", "switch_screen('connections')", "Connections", priority=True),
        Binding("6", "switch_screen('settings')", "Settings", priority=True),
        Binding("c", "push_screen('capture')", "Capture", priority=True),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, url_override: str | None = None, api_key_override: str | None = None):
        super().__init__()
        self._url_override = url_override
        self._api_key_override = api_key_override
        self.client: MimirClient | None = None

    def on_mount(self) -> None:
        cfg = load_config()
        base_url = self._url_override or cfg.base_url
        api_key = self._api_key_override or cfg.api_key
        self.client = MimirClient(base_url, api_key)

        # Register lazy screens
        from mimir_tui.screens.dashboard import DashboardScreen
        from mimir_tui.screens.search import SearchScreen
        from mimir_tui.screens.browse import BrowseScreen
        from mimir_tui.screens.note_detail import NoteDetailScreen
        from mimir_tui.screens.capture import CaptureScreen
        from mimir_tui.screens.connections import ConnectionsScreen
        from mimir_tui.screens.agent import AgentScreen
        from mimir_tui.screens.settings import SettingsScreen

        self.install_screen(DashboardScreen(), "dashboard")
        self.install_screen(SearchScreen(), "search")
        self.install_screen(BrowseScreen(), "browse")
        self.install_screen(CaptureScreen(), "capture")
        self.install_screen(ConnectionsScreen(), "connections")
        self.install_screen(AgentScreen(), "agent")
        self.install_screen(SettingsScreen(), "settings")

        # Health check then show dashboard
        self.run_worker(self._check_health())

    async def _check_health(self):
        try:
            await self.client.health()
            self.push_screen("dashboard")
        except Exception:
            self.push_screen(ConnectionErrorScreen())

    async def on_unmount(self) -> None:
        if self.client:
            await self.client.aclose()
