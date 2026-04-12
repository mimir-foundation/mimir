"""Query commands: search, ask, show, errored."""

import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from mimir_tui.helpers import output, run_async, truncate


@click.command()
@click.argument("query")
@click.option("-s", "--source", default=None, help="Filter by source type")
@click.option("-l", "--limit", default=10, help="Max results")
@click.pass_context
def search(ctx, query, source, limit):
    """Search the knowledge base."""

    def _run(client):
        return client.search(query, source_type=source, limit=limit)

    data = run_async(ctx, _run)

    def _table(d):
        results = d.get("results", [])
        tbl = Table(title=f"Search: {query}")
        tbl.add_column("Score", width=6)
        tbl.add_column("Title", min_width=20)
        tbl.add_column("Source", width=10)
        tbl.add_column("Date", width=10)
        for r in results:
            tbl.add_row(
                f"{r.get('score', 0):.2f}",
                truncate(r.get("title", "Untitled"), 50),
                r.get("source_type", ""),
                str(r.get("created_at", ""))[:10],
            )
        Console().print(tbl)

    output(ctx, data, _table)


@click.command()
@click.argument("question")
@click.pass_context
def ask(ctx, question):
    """Ask a question over your knowledge base."""

    def _run(client):
        return client.ask_with_conversation(question, [])

    data = run_async(ctx, _run)

    def _table(d):
        console = Console()
        answer = d.get("answer", "")
        console.print(Markdown(answer))
        sources = d.get("sources", [])
        if sources:
            console.print("\n[bold]Sources:[/bold]")
            for s in sources:
                title = s.get("title", "Untitled")
                nid = str(s.get("id", s.get("note_id", "")))[:8]
                console.print(f"  - {title} ({nid})")

    output(ctx, data, _table)


@click.command()
@click.argument("id")
@click.pass_context
def show(ctx, id):
    """Show a note by ID."""

    def _run(client):
        return client.get_note(id)

    data = run_async(ctx, _run)

    def _table(d):
        content = d.get("content", "")
        if sys.stdout.isatty():
            Console().print(Markdown(content))
        else:
            click.echo(content)

    output(ctx, data, _table)


@click.command()
@click.pass_context
def errored(ctx):
    """List notes that failed processing."""

    def _run(client):
        return client.get_errored_notes()

    data = run_async(ctx, _run)

    def _table(d):
        notes = d if isinstance(d, list) else d.get("notes", d.get("items", []))
        tbl = Table(title="Errored Notes")
        tbl.add_column("ID", width=8)
        tbl.add_column("Title", min_width=20)
        tbl.add_column("Error", min_width=20)
        tbl.add_column("Retries", width=7)
        tbl.add_column("Date", width=10)
        for n in notes:
            tbl.add_row(
                str(n.get("id", ""))[:8],
                truncate(n.get("title", "Untitled"), 40),
                truncate(n.get("error", ""), 40),
                str(n.get("retry_count", 0)),
                str(n.get("created_at", ""))[:10],
            )
        Console().print(tbl)

    output(ctx, data, _table)
