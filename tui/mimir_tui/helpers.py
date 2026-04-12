"""Shared helpers for Mimir CLI commands."""

import asyncio
import json
import platform
import subprocess
import sys

import click
import httpx

from mimir_tui.config import load_config
from mimir_tui.client import MimirClient


def run_async(ctx, coro_fn):
    """Create a MimirClient from context, run an async function, handle errors.

    coro_fn receives the client and should return data or None.
    """
    cfg = load_config()
    base_url = ctx.obj.get("url_override") or cfg.base_url
    api_key = ctx.obj.get("api_key_override") or cfg.api_key
    as_json = ctx.obj.get("as_json", False)

    async def _run():
        client = MimirClient(base_url, api_key)
        try:
            return await coro_fn(client)
        finally:
            await client.aclose()

    try:
        return asyncio.run(_run())
    except httpx.ConnectError:
        _error(f"Cannot reach backend at {base_url}", as_json)
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("detail", "")
        except Exception:
            detail = exc.response.text[:200]
        _error(f"HTTP {exc.response.status_code}: {detail}", as_json)


def _error(msg: str, as_json: bool):
    if as_json:
        click.echo(json.dumps({"error": msg}))
    else:
        click.echo(f"Error: {msg}", err=True)
    sys.exit(1)


def output(ctx, data, table_fn=None):
    """Route output to JSON or a Rich table."""
    if ctx.obj.get("as_json"):
        click.echo(json.dumps(data, indent=2, default=str))
    elif table_fn:
        table_fn(data)
    else:
        click.echo(data)


def clipboard_read() -> str | None:
    """Read clipboard content, platform-aware."""
    system = platform.system()
    cmds = {
        "Darwin": ["pbpaste"],
        "Windows": ["powershell", "-command", "Get-Clipboard"],
    }
    if system in cmds:
        try:
            return subprocess.check_output(cmds[system], text=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    # Linux: try xclip, xsel, wl-paste
    for cmd in [["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"], ["wl-paste"]]:
        try:
            return subprocess.check_output(cmd, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    return None


def truncate(s: str | None, n: int = 50) -> str:
    """Truncate string with ellipsis."""
    if not s:
        return ""
    return s if len(s) <= n else s[: n - 1] + "\u2026"
