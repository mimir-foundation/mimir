import click

from mimir_tui.commands.capture import add, url, clip
from mimir_tui.commands.query import search, ask, show, errored
from mimir_tui.commands.agent import brief, resurface, scan, interests
from mimir_tui.commands.browse import ls_cmd, concepts, entities
from mimir_tui.commands.manage import retry, star, delete, export, import_cmd
from mimir_tui.commands.system import status, config_group


COMMAND_SECTIONS = [
    ("Capture", ["add", "url", "clip"]),
    ("Query", ["search", "ask", "show", "errored"]),
    ("Browse", ["ls", "concepts", "entities"]),
    ("Agent", ["brief", "resurface", "scan", "interests"]),
    ("Manage", ["retry", "star", "delete", "export", "import"]),
    ("System", ["status", "config", "setup"]),
]


class SectionGroup(click.Group):
    def format_commands(self, ctx, formatter):
        commands = {name: self.commands[name] for name in self.commands}
        listed = set()

        for section, names in COMMAND_SECTIONS:
            rows = []
            for name in names:
                cmd = commands.get(name)
                if cmd is None:
                    continue
                listed.add(name)
                help_text = cmd.get_short_help_str(limit=formatter.width)
                rows.append((name, help_text))
            if rows:
                with formatter.section(section):
                    formatter.write_dl(rows)

        # Any commands not in a section (shouldn't happen, but safety net)
        remaining = [(name, commands[name].get_short_help_str(limit=formatter.width))
                     for name in sorted(commands) if name not in listed]
        if remaining:
            with formatter.section("Other"):
                formatter.write_dl(remaining)


@click.group(cls=SectionGroup, invoke_without_command=True)
@click.option("--url", "url_override", default=None, help="Mimir backend URL (overrides config)")
@click.option("--api-key", default=None, help="API key (overrides config)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def main(ctx, url_override, api_key, as_json):
    """Mimir — your second brain in the terminal.

    Run without a command to launch the interactive TUI.
    """
    ctx.ensure_object(dict)
    ctx.obj["url_override"] = url_override
    ctx.obj["api_key_override"] = api_key
    ctx.obj["as_json"] = as_json

    if ctx.invoked_subcommand is None:
        from mimir_tui.app import MimirApp
        app = MimirApp(url_override=url_override, api_key_override=api_key)
        app.run()


@main.command()
def setup():
    """Interactive setup wizard for Mimir."""
    from mimir_tui.wizard.wizard_app import WizardApp
    WizardApp().run()


# Capture
main.add_command(add)
main.add_command(url)
main.add_command(clip)

# Query
main.add_command(search)
main.add_command(ask)
main.add_command(show)
main.add_command(errored)

# Agent
main.add_command(brief)
main.add_command(resurface)
main.add_command(scan)
main.add_command(interests)

# Browse
main.add_command(ls_cmd)
main.add_command(concepts)
main.add_command(entities)

# Manage
main.add_command(retry)
main.add_command(star)
main.add_command(delete)
main.add_command(export)
main.add_command(import_cmd)

# System
main.add_command(status)
main.add_command(config_group)
