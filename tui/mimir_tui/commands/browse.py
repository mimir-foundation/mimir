"""Browse commands: ls, concepts, entities."""

import click
from rich.console import Console
from rich.table import Table

from mimir_tui.helpers import output, run_async, truncate


@click.command("ls")
@click.option("--sort", default="recent", help="Sort order: recent, starred, alphabetical")
@click.option("--source", default=None, help="Filter by source type")
@click.option("-l", "--limit", default=20, help="Max results")
@click.pass_context
def ls_cmd(ctx, sort, source, limit):
    """List notes."""

    def _run(client):
        return client.get_notes(sort=sort, source_type=source, limit=limit)

    data = run_async(ctx, _run)

    def _table(d):
        notes = d.get("notes", d.get("items", []))
        total = d.get("total", len(notes))
        tbl = Table(title="Notes")
        tbl.add_column("ID", width=8)
        tbl.add_column("\u2605", width=2)
        tbl.add_column("Title", min_width=25)
        tbl.add_column("Source", width=10)
        tbl.add_column("Concepts", width=15)
        tbl.add_column("Date", width=10)
        for n in notes:
            raw = n.get("concepts", [])
            concepts = ", ".join(c.get("name", "") if isinstance(c, dict) else str(c) for c in raw)
            tbl.add_row(
                str(n.get("id", ""))[:8],
                "\u2605" if n.get("is_starred") else "",
                truncate(n.get("title", "Untitled"), 40),
                n.get("source_type", ""),
                truncate(concepts, 15),
                str(n.get("created_at", ""))[:10],
            )
        Console().print(tbl)
        click.echo(f"Showing {len(notes)} of {total}")

    output(ctx, data, _table)


@click.command()
@click.pass_context
def concepts(ctx):
    """List concepts."""

    def _run(client):
        return client.get_concepts()

    data = run_async(ctx, _run)

    def _table(d):
        items = d if isinstance(d, list) else d.get("concepts", d.get("items", []))
        tbl = Table(title="Concepts")
        tbl.add_column("Name", min_width=20)
        tbl.add_column("Notes", width=6)
        tbl.add_column("Description", min_width=30)
        for c in items:
            tbl.add_row(
                truncate(c.get("name", ""), 30),
                str(c.get("note_count", c.get("notes", 0))),
                truncate(c.get("description", ""), 50),
            )
        Console().print(tbl)

    output(ctx, data, _table)


@click.command()
@click.option("-t", "--type", "entity_type", default=None, help="Filter by entity type")
@click.pass_context
def entities(ctx, entity_type):
    """List entities."""

    def _run(client):
        return client.get_entities(entity_type=entity_type)

    data = run_async(ctx, _run)

    def _table(d):
        items = d if isinstance(d, list) else d.get("entities", d.get("items", []))
        tbl = Table(title="Entities")
        tbl.add_column("Name", min_width=25)
        tbl.add_column("Type", width=12)
        for e in items:
            tbl.add_row(
                truncate(e.get("name", ""), 40),
                e.get("entity_type", e.get("type", "")),
            )
        Console().print(tbl)

    output(ctx, data, _table)
