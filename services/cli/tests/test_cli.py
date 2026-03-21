"""Basic tests for the Convene CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from convene_cli.main import app

runner = CliRunner()


def test_help() -> None:
    """CLI shows help without errors."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Convene AI" in result.output


def test_agents_help() -> None:
    """Agents subcommand shows help."""
    result = runner.invoke(app, ["agents", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "create" in result.output


def test_meetings_help() -> None:
    """Meetings subcommand shows help."""
    result = runner.invoke(app, ["meetings", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "create" in result.output


def test_keys_help() -> None:
    """Keys subcommand shows help."""
    result = runner.invoke(app, ["keys", "--help"])
    assert result.exit_code == 0
    assert "generate" in result.output


def test_status_not_authenticated() -> None:
    """Status shows 'not authenticated' when no token stored."""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Not authenticated" in result.output or "Authenticated" in result.output


def test_agents_list_requires_auth(tmp_path: object, monkeypatch: object) -> None:
    """Agents list requires login."""
    # Ensure no token is configured
    import convene_cli.config as cfg

    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.json")  # type: ignore[operator]
    result = runner.invoke(app, ["agents", "list"])
    assert result.exit_code == 1
    assert "Not logged in" in result.output
