"""Convene CLI — command-line interface for the Convene AI platform."""

from __future__ import annotations

from datetime import datetime, timezone

import typer
from rich.console import Console
from rich.table import Table

from convene_cli.api import ApiError, ConveneClient, run_async
from convene_cli.config import get_token, load_config, save_config

app = typer.Typer(
    name="convene",
    help="CLI for the Convene AI meeting platform.",
    no_args_is_help=True,
)
agents_app = typer.Typer(help="Manage agents.", no_args_is_help=True)
meetings_app = typer.Typer(help="Manage meetings.", no_args_is_help=True)
keys_app = typer.Typer(help="Manage API keys.", no_args_is_help=True)

app.add_typer(agents_app, name="agents")
app.add_typer(meetings_app, name="meetings")
app.add_typer(keys_app, name="keys")

console = Console()


def _require_auth() -> None:
    """Exit with an error if the user is not logged in."""
    if not get_token():
        console.print("[red]Not logged in. Run 'convene login' first.[/red]")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@app.command()
def login(
    email: str = typer.Option(..., prompt=True, help="Your email address."),
    password: str = typer.Option(
        ..., prompt=True, hide_input=True, help="Your password."
    ),
    api_url: str = typer.Option(
        "http://localhost:8000", "--api-url", help="Convene API base URL."
    ),
) -> None:
    """Authenticate with the Convene API and store credentials."""
    client = ConveneClient(base_url=api_url)
    try:
        result = run_async(client.login(email, password))
    except ApiError as exc:
        console.print(f"[red]Login failed: {exc.detail}[/red]")
        raise typer.Exit(1) from exc

    config = load_config()
    config["api_url"] = api_url
    config["token"] = result["token"]
    save_config(config)

    user = result["user"]
    console.print(f"[green]Logged in as {user['name']} ({user['email']})[/green]")


@app.command()
def status() -> None:
    """Show current authentication status."""
    config = load_config()
    token = config.get("token")
    api_url = config.get("api_url", "http://localhost:8000")
    if token:
        console.print(f"[green]Authenticated[/green] — API: {api_url}")
    else:
        console.print("[yellow]Not authenticated. Run 'convene login'.[/yellow]")


@app.command()
def logout() -> None:
    """Clear stored credentials."""
    config = load_config()
    config["token"] = None
    save_config(config)
    console.print("[green]Logged out.[/green]")


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


@agents_app.command("list")
def agents_list() -> None:
    """List your agents."""
    _require_auth()
    client = ConveneClient()
    try:
        result = run_async(client.list_agents())
    except ApiError as exc:
        console.print(f"[red]Error: {exc.detail}[/red]")
        raise typer.Exit(1) from exc

    items = result.get("items", [])
    if not items:
        console.print("[dim]No agents found.[/dim]")
        return

    table = Table(title="Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Capabilities")
    table.add_column("Created")

    for agent in items:
        caps = ", ".join(agent.get("capabilities", [])) or "—"
        created = agent.get("created_at", "")[:19]
        table.add_row(str(agent["id"]), agent["name"], caps, created)

    console.print(table)


@agents_app.command("create")
def agents_create(
    name: str = typer.Argument(..., help="Agent name."),
    system_prompt: str = typer.Option(
        "You are a helpful meeting assistant.",
        "--prompt",
        "-p",
        help="System prompt for the agent.",
    ),
) -> None:
    """Create a new agent."""
    _require_auth()
    client = ConveneClient()
    try:
        agent = run_async(client.create_agent(name, system_prompt))
    except ApiError as exc:
        console.print(f"[red]Error: {exc.detail}[/red]")
        raise typer.Exit(1) from exc

    console.print(f"[green]Agent created:[/green] {agent['name']} (ID: {agent['id']})")


# ---------------------------------------------------------------------------
# Meetings
# ---------------------------------------------------------------------------


@meetings_app.command("list")
def meetings_list() -> None:
    """List meetings."""
    _require_auth()
    client = ConveneClient()
    try:
        result = run_async(client.list_meetings())
    except ApiError as exc:
        console.print(f"[red]Error: {exc.detail}[/red]")
        raise typer.Exit(1) from exc

    items = result.get("items", [])
    if not items:
        console.print("[dim]No meetings found.[/dim]")
        return

    table = Table(title="Meetings")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Status")
    table.add_column("Scheduled")

    for meeting in items:
        title = meeting.get("title") or "—"
        scheduled = meeting.get("scheduled_at", "")[:19]
        table.add_row(str(meeting["id"]), title, meeting["status"], scheduled)

    console.print(table)


@meetings_app.command("create")
def meetings_create(
    title: str = typer.Argument(..., help="Meeting title."),
    scheduled_at: str = typer.Option(
        None,
        "--at",
        help="ISO 8601 datetime (defaults to now).",
    ),
) -> None:
    """Create a new meeting."""
    _require_auth()
    if scheduled_at is None:
        scheduled_at = datetime.now(tz=timezone.utc).isoformat()

    client = ConveneClient()
    try:
        meeting = run_async(client.create_meeting(title, scheduled_at))
    except ApiError as exc:
        console.print(f"[red]Error: {exc.detail}[/red]")
        raise typer.Exit(1) from exc

    console.print(
        f"[green]Meeting created:[/green] {meeting.get('title', 'Untitled')} "
        f"(ID: {meeting['id']})"
    )


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------


@keys_app.command("generate")
def keys_generate(
    agent_id: str = typer.Argument(..., help="Agent UUID."),
    name: str = typer.Option("default", "--name", "-n", help="Key name."),
) -> None:
    """Generate a new API key for an agent."""
    _require_auth()
    client = ConveneClient()
    try:
        key = run_async(client.generate_key(agent_id, name))
    except ApiError as exc:
        console.print(f"[red]Error: {exc.detail}[/red]")
        raise typer.Exit(1) from exc

    console.print("[green]API key generated.[/green]")
    console.print(f"[bold yellow]Key: {key['raw_key']}[/bold yellow]")
    console.print("[dim]Save this key — it will not be shown again.[/dim]")


if __name__ == "__main__":
    app()
