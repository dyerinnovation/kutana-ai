"""Kutana CLI entry point -- Click group with global options."""

from __future__ import annotations

import sys

import click

from kutana_cli.auth import auth
from kutana_cli.config import get_api_url, load_config
from kutana_cli.mcp_cmd import mcp
from kutana_cli.meetings import meetings
from kutana_cli.output import print_error
from kutana_cli.session import chat, join, leave, participants, speak, status, transcript
from kutana_cli.tasks import tasks
from kutana_cli.turns import turn


@click.group()
@click.option(
    "--url",
    envvar="KUTANA_URL",
    default=None,
    help="Kutana server URL (overrides config).",
)
@click.option(
    "--api-key",
    envvar="KUTANA_API_KEY",
    default=None,
    help="API key (overrides config).",
)
@click.option(
    "--json/--pretty",
    "use_json",
    default=True,
    help="Output format: --json (default) or --pretty.",
)
@click.pass_context
def cli(ctx: click.Context, url: str | None, api_key: str | None, use_json: bool) -> None:
    """Kutana AI -- meeting intelligence from the command line."""
    ctx.ensure_object(dict)

    config = load_config()

    # CLI args / env vars override saved config
    if url:
        config["url"] = url
    if api_key:
        config["api_key"] = api_key

    ctx.obj["config"] = config
    ctx.obj["use_json"] = use_json
    ctx.obj["api_url"] = get_api_url(config)


# Register subcommand groups
cli.add_command(auth)
cli.add_command(meetings)
cli.add_command(tasks)
cli.add_command(turn)
cli.add_command(mcp)

# Register top-level session commands
cli.add_command(join)
cli.add_command(leave)
cli.add_command(speak)
cli.add_command(chat)
cli.add_command(transcript)
cli.add_command(participants)
cli.add_command(status)


def main() -> None:
    """CLI entry point for direct invocation."""
    try:
        cli()
    except Exception as exc:
        print_error(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
