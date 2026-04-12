"""First-run welcome wizard for Mimir CLI."""

import asyncio
import sys

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.text import Text

from mimir_tui.config import CONFIG_FILE, TuiConfig, save_config
from mimir_tui.client import MimirClient

BRAIN = r"""
           _---~~(~~-_.
         _{        )   )
       ,   ) -~~- ( ,-' )_
      (  `-,_..`., )-- '_,)
     ( ` _)  (  -~( -_ `,  }
     (_-  _  ~_-~~~~`,  ,' )
       `~ -^(    __;-,((()))
             ~~~~ {_ -_(())
                    `\  }
                      { }"""


def is_first_run() -> bool:
    return not CONFIG_FILE.exists()


def welcome():
    """Run the first-run welcome wizard."""
    console = Console()
    try:
        _welcome_screen(console)
        base_url, api_key = _connect(console)
        _telegram(console, base_url, api_key)
        _first_capture(console, base_url, api_key)
        _cheatsheet(console)
        save_config(TuiConfig(base_url=base_url, api_key=api_key))
        console.print("[bold green]Setup complete![/] Config saved to "
                      f"[dim]{CONFIG_FILE}[/dim]\n")
    except (KeyboardInterrupt, click.Abort):
        console.print("\n[dim]Setup cancelled. Run [bold]mimir[/bold] again to restart.[/dim]\n")
        sys.exit(0)


# -- Steps ----------------------------------------------------------------- #

def _welcome_screen(console: Console):
    from rich.console import Group

    brain = Align.center(Text(BRAIN, style="bold cyan"))
    title = Align.center(Text("M I M I R", style="bold white"))
    tagline = Align.center(Text("Your AI-powered second brain", style="dim"))

    console.print()
    console.print(Panel(Group(brain, Text(), title, tagline, Text()), border_style="cyan", padding=(1, 4)))
    console.print()
    console.print("  [dim]Let's get you set up. This takes about 2 minutes.[/dim]\n")
    click.pause("  Press Enter to begin...")
    console.print()


def _connect(console: Console) -> tuple[str, str | None]:
    console.rule("[bold]Step 1 [dim]Connect to backend[/dim][/bold]")
    console.print()

    base_url = click.prompt(
        "  Backend URL", default="http://localhost:3080", show_default=True
    ).rstrip("/")

    # Test connection with retries
    while True:
        console.print()
        try:
            resp = httpx.get(f"{base_url}/api/health", timeout=5.0)
            resp.raise_for_status()
            version = resp.json().get("version", "?")
            console.print(f"  [green]>[/green] Connected — Mimir v{version}")
            break
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
            console.print(f"  [red]x[/red] Cannot reach {base_url}")
            console.print("  [dim]Make sure your backend is running:[/dim]")
            console.print("  [dim]  docker-compose up -d[/dim]")
            console.print()
            if not click.confirm("  Retry?", default=True):
                raise click.Abort()
            base_url = click.prompt(
                "  Backend URL", default=base_url, show_default=True
            ).rstrip("/")

    # API key
    console.print()
    api_key = click.prompt(
        "  API key (from .env, or blank to skip)",
        default="", show_default=False,
    ).strip() or None

    if api_key:
        try:
            resp = httpx.get(
                f"{base_url}/api/stats",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5.0,
            )
            resp.raise_for_status()
            console.print(f"  [green]>[/green] Authenticated")
        except httpx.HTTPStatusError:
            console.print("  [yellow]![/yellow] Key not accepted — continuing anyway")
    else:
        console.print("  [dim]  No key — skipping auth[/dim]")

    console.print()
    return base_url, api_key


def _telegram(console: Console, base_url: str, api_key: str | None):
    console.rule("[bold]Step 2 [dim]Connect Telegram[/dim] [dim italic](optional)[/dim italic][/bold]")
    console.print()
    console.print("  [dim]Capture notes, search, and get daily briefs right from Telegram.[/dim]")
    console.print()

    if not click.confirm("  Set up Telegram?", default=True):
        console.print()
        return

    # --- Bot token ---
    console.print()
    console.print("  [bold]Create your bot:[/bold]")
    console.print("    1. Open Telegram, message [bold]@BotFather[/bold]")
    console.print("    2. Send [bold]/newbot[/bold]")
    console.print("    3. Pick a name (e.g. \"My Mimir\")")
    console.print("    4. Pick a username (e.g. my_mimir_bot)")
    console.print("    5. Copy the token it gives you")
    console.print()

    bot_token = click.prompt("  Bot token").strip()

    try:
        resp = httpx.get(
            f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10.0
        )
        data = resp.json()
        if data.get("ok"):
            bot_name = data["result"].get("first_name", "Bot")
            username = data["result"].get("username", "")
            console.print(f"  [green]>[/green] Bot verified: {bot_name} (@{username})")
        else:
            console.print("  [yellow]![/yellow] Token not recognized — double-check it")
            console.print()
            return
    except Exception:
        console.print("  [yellow]![/yellow] Couldn't reach Telegram API — skipping")
        console.print()
        return

    # --- User ID ---
    console.print()
    console.print("  [bold]Get your user ID:[/bold]")
    console.print("    1. Message [bold]@userinfobot[/bold] on Telegram")
    console.print("    2. It will reply with your numeric ID")
    console.print()

    user_id = click.prompt("  Your Telegram user ID").strip()

    # --- Save to backend ---
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    bridge_config = {
        "telegram": {"bot_token": bot_token, "user_id": user_id},
        "enabled_platforms": ["telegram"],
        "security": {"allowed_sender_ids": {"telegram": [user_id]}},
        "outbound_channels": {
            "daily_brief": [{"platform": "telegram", "recipient_id": user_id}],
            "resurface": [{"platform": "telegram", "recipient_id": user_id}],
        },
    }

    try:
        resp = httpx.patch(
            f"{base_url}/api/bridge/config",
            json=bridge_config,
            headers=headers,
            timeout=10.0,
        )
        resp.raise_for_status()
        console.print()
        console.print("  [green]>[/green] Telegram configured!")
        console.print(f"  [dim]Send a message to @{username} to try it out.[/dim]")
    except httpx.HTTPStatusError as exc:
        console.print()
        console.print(f"  [yellow]![/yellow] Backend returned {exc.response.status_code}")
        if exc.response.status_code == 401:
            console.print("  [dim]API key mismatch — try: docker compose restart mimir-backend[/dim]")
        console.print("  [dim]You can configure it later with: mimir setup[/dim]")
    except Exception as exc:
        console.print()
        console.print(f"  [yellow]![/yellow] Couldn't save bridge config: {exc}")
        console.print("  [dim]You can configure it later with: mimir setup[/dim]")

    console.print()


def _first_capture(console: Console, base_url: str, api_key: str | None):
    console.rule("[bold]Step 3 [dim]Your first capture[/dim][/bold]")
    console.print()

    if not click.confirm("  Capture your first note right now?", default=True):
        console.print()
        return

    console.print()
    thought = click.prompt("  Type a thought, idea, or anything").strip()
    if not thought:
        console.print("  [dim]Skipped — nothing entered.[/dim]\n")
        return

    async def _capture():
        client = MimirClient(base_url, api_key)
        try:
            return await client.capture_note(thought)
        finally:
            await client.aclose()

    try:
        result = asyncio.run(_capture())
        note_id = str(result.get("note_id", result.get("id", "")))[:8]
        console.print()
        console.print(f"  [green]>[/green] Captured! [bold]{note_id}[/bold]")
        console.print()
        console.print(
            Panel(
                "[dim]Mimir is now processing your note in the background —\n"
                "extracting concepts, finding connections, and building\n"
                "your knowledge graph.[/dim]",
                border_style="dim",
                padding=(1, 4),
            )
        )
    except Exception:
        console.print()
        console.print("  [yellow]![/yellow] Couldn't capture — check that the backend is running")

    console.print()


def _cheatsheet(console: Console):
    console.rule("[bold]You're ready[/bold]")
    console.print()

    tbl = Table(show_header=False, box=None, padding=(0, 2), show_edge=False, pad_edge=False)
    tbl.add_column(style="bold cyan", min_width=36)
    tbl.add_column(style="dim")

    tbl.add_row("  mimir add \"your thought\"",     "Capture a note")
    tbl.add_row("  mimir url https://...",           "Save a link")
    tbl.add_row("  echo \"...\" | mimir add",       "Pipe from stdin")
    tbl.add_row("  mimir search \"query\"",          "Search everything")
    tbl.add_row("  mimir ask \"question?\"",         "Q&A over your knowledge")
    tbl.add_row("  mimir brief",                     "Today's daily brief")
    tbl.add_row("  mimir ls",                        "List recent notes")
    tbl.add_row("  mimir ls --json | jq ...",        "Pipe-friendly JSON")
    tbl.add_row("  mimir",                           "Launch the full TUI")
    tbl.add_row("  mimir setup",                     "Email, webhooks, AI presets & more")

    console.print(tbl)
    console.print()
