#!/usr/bin/env python3
"""Merge Groundwork's required settings.json entries into an existing Claude Code
settings file, without touching anything else the user has configured.

Idempotent: safe to run repeatedly (on install, update, or re-run). Never overwrites
the file wholesale — only adds/updates the specific keys Groundwork owns:
  - hooks.PreToolUse / hooks.Stop / hooks.SessionStart: appends Groundwork's four
    hook entries if not already present (matched by command string, so re-running
    never duplicates).
  - permissions.deny: adds Groundwork's destructive-command deny patterns, skipping
    any already present.
  - env.GATEGUARD_EXEMPT_GLOBS / env.NODE_USE_SYSTEM_CA: set only if the user hasn't
    already set that specific key to something else (never clobbers a user override).
  - env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: ONLY with --agent-teams, and only if
    the key is absent (Agent Teams are experimental and change how ordinary
    delegation behaves — see docs/en/agent-teams — so they are opt-in, never silent).
  - pluginConfigs["ecc@ecc"].options.hook_profile: set to "standard" only if unset.

Usage: python3 merge_settings.py [--agent-teams] [path to settings.json]
       (default path: ~/.claude/settings.json)
"""
import json
import os
import sys
from pathlib import Path

PUSH_CMD = "python3 ~/.claude/hooks/block_protected_push.py"
REVIEW_CMD = "python3 ~/.claude/hooks/require_material_review.py"
SNAPSHOT_CMD = "python3 ~/.claude/hooks/groundwork_session_snapshot.py"
TELEMETRY_CMD = "python3 ~/.claude/hooks/groundwork_telemetry.py"

GROUNDWORK_DENY = [
    "Bash(sudo *)",
    "Bash(rm -rf /*)",
    "Bash(rm -rf ~*)",
    "Bash(chmod -R 777 *)",
    "Bash(chmod 777 *)",
    "Bash(git push --force*)",
    "Bash(git push -f *)",
    "Bash(dd *)",
    "Bash(mkfs*)",
    "Bash(diskutil erase*)",
]

GROUNDWORK_ENV_DEFAULTS = {
    "GATEGUARD_EXEMPT_GLOBS": "**/*.md,**/*.txt,**/*.rst",
    # Works around a macOS/Node 22 hang where Node blocks at process exit loading
    # keychain CA certs (see docs/TROUBLESHOOTING.md). Harmless on Linux/Windows.
    "NODE_USE_SYSTEM_CA": "0",
}

AGENT_TEAMS_ENV = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"


def write_atomic(path: Path, text: str) -> None:
    """Write via a temp file + os.replace so a crash mid-write never truncates settings.json."""
    tmp = path.with_name(path.name + ".groundwork.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def hook_entry(command: str, status_message: str, matcher: str | None = None, timeout: int | None = None) -> dict:
    entry = {"type": "command", "command": command, "statusMessage": status_message}
    if timeout is not None:
        entry["timeout"] = timeout
    hooks_block = {"hooks": [entry]}
    if matcher is not None:
        hooks_block["matcher"] = matcher
    return hooks_block


def has_command(entries: list, command: str) -> bool:
    for group in entries:
        for h in group.get("hooks", []):
            if h.get("command") == command:
                return True
    return False


def parse_args(argv: list[str]) -> tuple[bool, Path]:
    agent_teams = False
    path = None
    for arg in argv:
        if arg == "--agent-teams":
            agent_teams = True
        elif arg.startswith("-"):
            raise SystemExit(f"unknown option: {arg}")
        elif path is not None:
            raise SystemExit(f"unexpected extra argument: {arg}")
        else:
            path = Path(arg)
    if path is None:
        path = Path(os.path.expanduser("~/.claude/settings.json"))
    return agent_teams, path


def merge(data: dict, agent_teams: bool = False) -> list[str]:
    """Apply Groundwork's additive merge to a settings dict in place; return the change list."""
    changed = []

    hooks = data.setdefault("hooks", {})

    pre = hooks.setdefault("PreToolUse", [])
    if not has_command(pre, PUSH_CMD):
        pre.append(hook_entry(PUSH_CMD, "Checking protected-branch push guard...", matcher="Bash"))
        changed.append("hooks.PreToolUse: block_protected_push.py")

    stop = hooks.setdefault("Stop", [])
    if not has_command(stop, REVIEW_CMD):
        stop.append(hook_entry(REVIEW_CMD, "Checking material-change review gate..."))
        changed.append("hooks.Stop: require_material_review.py")
    if not has_command(stop, TELEMETRY_CMD):
        stop.append(hook_entry(TELEMETRY_CMD, "Recording Groundwork task telemetry...", timeout=10))
        changed.append("hooks.Stop: groundwork_telemetry.py")

    start = hooks.setdefault("SessionStart", [])
    if not has_command(start, SNAPSHOT_CMD):
        start.append(hook_entry(SNAPSHOT_CMD, "Building Groundwork project snapshot...", timeout=10))
        changed.append("hooks.SessionStart: groundwork_session_snapshot.py")

    permissions = data.setdefault("permissions", {})
    deny = permissions.setdefault("deny", [])
    for rule in GROUNDWORK_DENY:
        if rule not in deny:
            deny.append(rule)
            changed.append(f"permissions.deny: {rule}")

    env = data.setdefault("env", {})
    for key, value in GROUNDWORK_ENV_DEFAULTS.items():
        if key not in env:
            env[key] = value
            changed.append(f"env.{key}={value}")
    if agent_teams and AGENT_TEAMS_ENV not in env:
        env[AGENT_TEAMS_ENV] = "1"
        changed.append(f"env.{AGENT_TEAMS_ENV}=1 (opt-in)")

    plugin_configs = data.setdefault("pluginConfigs", {})
    ecc_config = plugin_configs.setdefault("ecc@ecc", {}).setdefault("options", {})
    if "hook_profile" not in ecc_config:
        ecc_config["hook_profile"] = "standard"
        changed.append("pluginConfigs['ecc@ecc'].options.hook_profile=standard")

    return changed


def main() -> None:
    agent_teams, path = parse_args(sys.argv[1:])
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {}
    if path.exists():
        text = path.read_text().strip()
        if text:
            data = json.loads(text)

    changed = merge(data, agent_teams=agent_teams)
    write_atomic(path, json.dumps(data, indent=2) + "\n")

    if changed:
        print(f"Updated {path}:")
        for c in changed:
            print(f"  + {c}")
    else:
        print(f"{path} already has all Groundwork entries — nothing to do.")


if __name__ == "__main__":
    main()
