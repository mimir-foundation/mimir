"""Capture commands: add, url, clip."""

import sys

import click

from mimir_tui.helpers import clipboard_read, output, run_async


@click.command()
@click.argument("content", nargs=-1)
@click.option("-t", "--title", default=None, help="Note title")
@click.option("--tag", multiple=True, help="Tag (repeatable)")
@click.pass_context
def add(ctx, content, title, tag):
    """Capture a note. Reads from stdin if no CONTENT given."""
    text = " ".join(content) if content else None
    if not text:
        if sys.stdin.isatty():
            raise click.UsageError("Provide CONTENT as arguments or pipe via stdin.")
        text = sys.stdin.read().strip()
    if not text:
        raise click.UsageError("Empty content.")

    tags = list(tag) if tag else None

    def _run(client):
        return client.capture_note(text, title=title, tags=tags)

    data = run_async(ctx, _run)
    output(ctx, data, lambda d: click.echo(d.get("note_id", d.get("id", ""))))


@click.command()
@click.argument("url")
@click.option("-c", "--context", "context_", default=None, help="Additional context")
@click.pass_context
def url(ctx, url, context_):
    """Capture a URL."""

    def _run(client):
        return client.capture_url(url, context=context_)

    data = run_async(ctx, _run)
    output(ctx, data, lambda d: click.echo(d.get("note_id", d.get("id", ""))))


@click.command()
@click.pass_context
def clip(ctx):
    """Capture clipboard contents."""
    text = clipboard_read()
    if not text and not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    if not text:
        raise click.UsageError("Clipboard is empty and no stdin provided.")

    def _run(client):
        return client.capture_clipboard(text)

    data = run_async(ctx, _run)
    output(ctx, data, lambda d: click.echo(d.get("note_id", d.get("id", ""))))
