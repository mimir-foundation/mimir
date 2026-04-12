"""Manage commands: retry, star, delete, export, import."""

from datetime import date
from pathlib import Path

import click

from mimir_tui.helpers import output, run_async


@click.command()
@click.argument("id")
@click.pass_context
def retry(ctx, id):
    """Retry processing for a failed note."""

    def _run(client):
        return client.retry_note(id)

    data = run_async(ctx, _run)
    output(ctx, data, lambda d: click.echo(f"Retry queued for {id[:8]}"))


@click.command()
@click.argument("id")
@click.pass_context
def star(ctx, id):
    """Toggle star on a note."""

    async def _run(client):
        note = await client.get_note(id)
        current = note.get("is_starred", False)
        await client.update_note(id, {"is_starred": not current})
        return {"is_starred": not current}

    data = run_async(ctx, _run)

    def _table(d):
        if d.get("is_starred"):
            click.echo("Starred")
        else:
            click.echo("Unstarred")

    output(ctx, data, _table)


@click.command()
@click.argument("id")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def delete(ctx, id, yes):
    """Delete a note."""
    if not yes:
        # Fetch title for confirmation prompt
        def _get(client):
            return client.get_note(id)

        note = run_async(ctx, _get)
        title = note.get("title", "Untitled") if note else "Untitled"
        click.confirm(f'Delete "{title}"?', abort=True)

    def _run(client):
        return client.delete_note(id)

    data = run_async(ctx, _run)
    output(ctx, data, lambda d: click.echo(f"Deleted {id[:8]}"))


@click.command()
@click.option("--format", "fmt", type=click.Choice(["json", "md"]), default="json", help="Export format")
@click.option("-o", "--output", "output_path", default=None, help="Output file path")
@click.option("--note", "note_id", default=None, help="Export a single note by ID")
@click.pass_context
def export(ctx, fmt, output_path, note_id):
    """Export knowledge base."""
    if note_id:
        # Single note export
        def _run(client):
            return client.export_note(note_id)

        content = run_async(ctx, _run)
        if output_path:
            Path(output_path).write_bytes(content)
            click.echo(f"Exported to {output_path}")
        else:
            click.echo(content.decode("utf-8", errors="replace"))
        return

    ext = "json" if fmt == "json" else "zip"
    if not output_path:
        output_path = f"mimir-export-{date.today().strftime('%Y%m%d')}.{ext}"

    if fmt == "json":
        def _run(client):
            return client.export_json()
    else:
        def _run(client):
            return client.export_markdown()

    content = run_async(ctx, _run)
    Path(output_path).write_bytes(content)
    click.echo(f"Exported to {output_path}")


@click.command("import")
@click.argument("source", type=click.Choice(["notion", "obsidian", "bookmarks"]))
@click.argument("file", type=click.Path(exists=True))
@click.pass_context
def import_cmd(ctx, source, file):
    """Import from an external source (notion, obsidian, bookmarks)."""

    def _run(client):
        return client.import_file(source, file)

    data = run_async(ctx, _run)
    output(ctx, data, lambda d: click.echo(f"Import complete: {d.get('imported', d.get('count', '?'))} items"))
