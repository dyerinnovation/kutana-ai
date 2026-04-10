#!/usr/bin/env python3
"""Sync Kutana managed agent system prompts to the Anthropic console.

Reads prompts from managed-agent-system-prompts.md, renders templates with
empty org_sop/custom_instructions (for default agents), then calls
client.beta.agents.update() for each pre-created agent ID in the registry.

Usage:
    # Sync all tiers
    uv run python scripts/sync_agents.py

    # Sync a single tier
    uv run python scripts/sync_agents.py --tier default
    uv run python scripts/sync_agents.py --tier haiku
    uv run python scripts/sync_agents.py --tier opus

    # Dry run — print prompts without calling the API
    uv run python scripts/sync_agents.py --dry-run

    # Verbose — show rendered prompt for each agent
    uv run python scripts/sync_agents.py --verbose
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_PROMPTS_FILE = REPO_ROOT / "internal-docs/development/managed-agent-system-prompts.md"
API_KEY_FILE = Path.home() / "Documents/dev/z-api-keys-and-tokens/ANTHROPIC_API_KEY_TEST.txt"

# Add the api-server src to sys.path so we can import agent_registry
sys.path.insert(0, str(REPO_ROOT / "services/api-server/src"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_api_key() -> str:
    """Load API key from ANTHROPIC_API_KEY env var, falling back to file."""
    import os

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key and API_KEY_FILE.exists():
        key = API_KEY_FILE.read_text().strip()
    if not key:
        print(f"ERROR: Set ANTHROPIC_API_KEY or place key in {API_KEY_FILE}")
        sys.exit(1)
    return key


def parse_system_prompts(md_path: Path) -> dict[str, str]:
    """Parse system prompts from managed-agent-system-prompts.md.

    Returns a dict mapping agent name -> raw prompt text (with template vars).
    """
    content = md_path.read_text()
    prompts: dict[str, str] = {}
    pattern = r"### \d+\.\s+(.+?)\n\n```\n(.*?)```"
    for match in re.finditer(pattern, content, re.DOTALL):
        name = match.group(1).strip()
        prompt = match.group(2).strip()
        prompts[name] = prompt
    return prompts


def render_prompt(
    raw_prompt: str,
    org_sop: str = "",
    custom_instructions: str = "",
) -> str:
    """Render a prompt template, substituting org_sop and custom_instructions.

    Uses $-style substitution to avoid conflicts with Jinja/double-brace
    in the prompt text. We do a literal string replace instead of Template
    because the prompts use {{var}} syntax (double braces), not $var.
    """
    rendered = raw_prompt.replace("{{org_sop}}", org_sop)
    rendered = rendered.replace("{{custom_instructions}}", custom_instructions)
    return rendered


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------

# Maps display name in managed-agent-system-prompts.md → registry slug
DISPLAY_NAME_TO_SLUG: dict[str, str] = {
    "Meeting Notetaker": "meeting-notetaker",
    "Meeting Summarizer": "meeting-summarizer",
    "Action Item Tracker": "action-item-tracker",
    "Decision Logger": "decision-logger",
    "Standup Facilitator": "standup-facilitator",
    "Code Discussion Tracker": "code-discussion-tracker",
    "Sprint Retro Coach": "sprint-retro-coach",
    "Sprint Planner": "sprint-planner",
    "User Interviewer": "user-interviewer",
    "Initial Interviewer": "initial-interviewer",
}


def sync_agents(
    *,
    tier_filter: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Sync all (or filtered) agents to the Anthropic console.

    Args:
        tier_filter: If set, only sync agents that have an entry for this tier.
        dry_run: Print what would be done without calling the API.
        verbose: Print rendered prompts.

    Returns:
        Number of agents successfully updated (or would-be updated in dry_run).
    """
    from api_server.agent_registry import AGENT_REGISTRY

    # Load prompts
    if not SYSTEM_PROMPTS_FILE.exists():
        print(f"ERROR: System prompts file not found: {SYSTEM_PROMPTS_FILE}")
        sys.exit(1)

    raw_prompts = parse_system_prompts(SYSTEM_PROMPTS_FILE)
    print(f"Loaded {len(raw_prompts)} system prompts.")

    # Set up client (skip in dry_run)
    client = None
    if not dry_run:
        import anthropic

        api_key = load_api_key()
        client = anthropic.Anthropic(api_key=api_key)

    updated = 0
    errors = 0

    for display_name, slug in DISPLAY_NAME_TO_SLUG.items():
        tiers = AGENT_REGISTRY.get(slug)
        if not tiers:
            print(f"  SKIP {display_name}: not in registry")
            continue

        raw_prompt = raw_prompts.get(display_name)
        if not raw_prompt:
            print(f"  SKIP {display_name}: no system prompt found in markdown")
            continue

        # Render once (default: empty org_sop / custom_instructions)
        rendered = render_prompt(raw_prompt)

        # Iterate over tiers in registry
        for tier, agent_id in sorted(tiers.items()):
            if tier_filter and tier != tier_filter:
                continue

            label = f"{display_name} [{tier}] ({agent_id})"

            if dry_run:
                print(f"\n  DRY RUN — would update: {label}")
                if verbose:
                    print(f"  Prompt ({len(rendered)} chars):\n{rendered[:300]}...")
                updated += 1
                continue

            print(f"\n  Syncing: {label}")
            if verbose:
                print(f"  Prompt ({len(rendered)} chars):\n{rendered[:300]}...")

            try:
                # Retrieve current agent to get its version (required for update)
                assert client is not None
                current = client.beta.agents.retrieve(agent_id)
                version = current.version

                # Update system prompt only; preserve everything else
                client.beta.agents.update(
                    agent_id,
                    version=version,
                    system=rendered,
                )
                print(f"    OK — updated to version {version + 1}")
                updated += 1

            except Exception as exc:
                print(f"    ERROR: {exc}")
                errors += 1

    print(f"\n{'DRY RUN — ' if dry_run else ''}Done: {updated} updated, {errors} errors.")
    return updated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync Kutana agent system prompts to the Anthropic console."
    )
    parser.add_argument(
        "--tier",
        choices=["default", "haiku", "opus"],
        default=None,
        help="Sync only agents of this tier (omit to sync all).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without calling the API.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print rendered prompt previews.",
    )
    args = parser.parse_args()

    sync_agents(
        tier_filter=args.tier,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
