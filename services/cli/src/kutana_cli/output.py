"""Output helpers for consistent CLI formatting."""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

_console = Console()
_err_console = Console(stderr=True)


def print_json(data: Any) -> None:
    """Print data as formatted JSON to stdout.

    Args:
        data: Any JSON-serializable value.
    """
    print(json.dumps(data, indent=2, default=str))


def print_pretty(data: Any) -> None:
    """Print data in a human-friendly rich format.

    Renders dicts as panels and lists as tables. Falls back to JSON for
    types that do not map cleanly to rich widgets.

    Args:
        data: Data to display.
    """
    if isinstance(data, dict):
        _print_dict_pretty(data)
    elif isinstance(data, list):
        _print_list_pretty(data)
    else:
        _console.print(data)


def _print_dict_pretty(data: dict[str, Any]) -> None:
    """Render a dict as a rich Panel with key-value rows."""
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("Key", style="bold cyan", no_wrap=True)
    table.add_column("Value")
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2, default=str)
        table.add_row(str(key), str(value))
    _console.print(Panel(table, expand=False))


def _print_list_pretty(data: list[Any]) -> None:
    """Render a list of dicts as a rich Table."""
    if not data:
        _console.print("[dim]No items.[/dim]")
        return

    if isinstance(data[0], dict):
        table = Table(show_lines=True)
        columns = list(data[0].keys())
        for col in columns:
            table.add_column(col, style="cyan")
        for item in data:
            row = [str(item.get(col, "")) for col in columns]
            table.add_row(*row)
        _console.print(table)
    else:
        for item in data:
            _console.print(f"  - {item}")


def output(data: Any, *, use_json: bool = True) -> None:
    """Dispatch to JSON or pretty output based on flag.

    Args:
        data: Data to display.
        use_json: If True, output JSON. Otherwise, pretty-print.
    """
    if use_json:
        print_json(data)
    else:
        print_pretty(data)


def print_error(message: str, *, code: int = 1) -> None:
    """Print a structured JSON error to stderr and exit.

    Args:
        message: Human-readable error description.
        code: Process exit code (default 1).
    """
    error_payload = {"error": message}
    print(json.dumps(error_payload), file=sys.stderr)
    sys.exit(code)


def print_success(message: str) -> None:
    """Print a success message to stderr (keeps stdout clean for JSON).

    Args:
        message: Human-readable success description.
    """
    _err_console.print(f"[green]{message}[/green]")
