import click


@click.group(invoke_without_command=True)
@click.option("--url", default=None, help="Mimir backend URL (overrides config)")
@click.option("--api-key", default=None, help="API key (overrides config)")
@click.pass_context
def main(ctx, url, api_key):
    """Mimir — your second brain in the terminal."""
    ctx.ensure_object(dict)
    ctx.obj["url_override"] = url
    ctx.obj["api_key_override"] = api_key

    if ctx.invoked_subcommand is None:
        from mimir_tui.app import MimirApp
        app = MimirApp(url_override=url, api_key_override=api_key)
        app.run()


@main.command()
def setup():
    """Interactive setup wizard for Mimir."""
    from mimir_tui.wizard.wizard_app import WizardApp
    WizardApp().run()
