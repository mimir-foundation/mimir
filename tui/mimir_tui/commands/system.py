"""System commands: status, config."""

import json

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mimir_tui.config import load_config, save_config, TuiConfig
from mimir_tui.helpers import output, run_async


@click.command()
@click.pass_context
def status(ctx):
    """Show backend status and stats."""

    async def _run(client):
        health = await client.health()
        stats = await client.get_stats()
        return {"health": health, "stats": stats}

    data = run_async(ctx, _run)

    def _table(d):
        console = Console()
        health = d.get("health", {})
        stats = d.get("stats", {})
        cfg = load_config()
        base_url = ctx.obj.get("url_override") or cfg.base_url

        lines = [
            f"[bold]Backend:[/bold] {base_url}",
            f"[bold]Status:[/bold]  {health.get('status', 'unknown')}",
            f"[bold]Version:[/bold] {health.get('version', '?')}",
        ]
        console.print(Panel("\n".join(lines), title="Mimir"))

        tbl = Table(title="Stats")
        tbl.add_column("Metric", min_width=15)
        tbl.add_column("Value", min_width=8)
        for key, val in stats.items():
            style = "yellow" if key == "errored" and val and int(val) > 0 else None
            tbl.add_row(key, str(val), style=style)
        console.print(tbl)

    output(ctx, data, _table)


@click.group("config")
def config_group():
    """View or update local CLI configuration."""
    pass


@config_group.command("show")
@click.pass_context
def config_show(ctx):
    """Show current configuration."""
    cfg = load_config()
    data = {"base_url": cfg.base_url, "api_key": cfg.api_key}
    if ctx.obj.get("as_json"):
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"base_url: {cfg.base_url}")
        click.echo(f"api_key:  {cfg.api_key or '(not set)'}")


@config_group.command("set")
@click.argument("key", type=click.Choice(["base_url", "api_key"]))
@click.argument("value")
def config_set(key, value):
    """Set a configuration value (base_url or api_key)."""
    cfg = load_config()
    setattr(cfg, key, value)
    save_config(cfg)
    click.echo(f"{key} = {value}")
