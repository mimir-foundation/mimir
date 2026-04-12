"""Agent commands: brief, resurface, scan, interests."""

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from mimir_tui.helpers import output, run_async, truncate


@click.command()
@click.option("--generate", is_flag=True, help="Generate a fresh brief")
@click.pass_context
def brief(ctx, generate):
    """Show or generate today's daily brief."""

    async def _run(client):
        if generate:
            return await client.generate_brief()
        data = await client.get_brief()
        content = data.get("brief", {}).get("content", "")
        if not content:
            data = await client.generate_brief()
        return data

    data = run_async(ctx, _run)

    def _table(d):
        content = d.get("brief", {}).get("content", "")
        if content:
            Console().print(Markdown(content))
        else:
            click.echo("No brief available.")

    output(ctx, data, _table)


@click.command()
@click.option("-l", "--limit", default=5, help="Number of items")
@click.pass_context
def resurface(ctx, limit):
    """Show resurfaced knowledge items."""

    def _run(client):
        return client.get_resurface(limit=limit)

    data = run_async(ctx, _run)

    def _table(d):
        items = d if isinstance(d, list) else d.get("items", [])
        tbl = Table(title="Resurface")
        tbl.add_column("Reason", width=20)
        tbl.add_column("Title", min_width=25)
        tbl.add_column("Score", width=6)
        for item in items:
            tbl.add_row(
                truncate(item.get("trigger_type", ""), 20),
                truncate(item.get("title", item.get("note_title", "")), 40),
                f"{item.get('score', 0):.2f}",
            )
        Console().print(tbl)

    output(ctx, data, _table)


@click.command()
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def scan(ctx, yes):
    """Trigger a connection deep scan."""
    if not yes:
        click.confirm("Run a deep scan? This may take a while.", abort=True)

    def _run(client):
        return client.trigger_deep_scan()

    data = run_async(ctx, _run)
    output(ctx, data, lambda d: click.echo("Deep scan triggered."))


@click.command()
@click.pass_context
def interests(ctx):
    """Show tracked interest signals."""

    def _run(client):
        return client.get_interests()

    data = run_async(ctx, _run)

    def _table(d):
        items = d if isinstance(d, list) else d.get("interests", d.get("items", []))
        tbl = Table(title="Interests")
        tbl.add_column("Topic", min_width=25)
        tbl.add_column("Score", width=8)
        for item in items:
            tbl.add_row(
                truncate(item.get("topic", item.get("name", "")), 40),
                f"{item.get('score', item.get('strength', 0)):.2f}",
            )
        Console().print(tbl)

    output(ctx, data, _table)
