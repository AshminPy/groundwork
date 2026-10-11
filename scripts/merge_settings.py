#!/usr/bin/env python3
"""Merge Groundwork's required settings.json entries into an existing Claude Code
settings file, without touching anything else the user has configured.

Idempotent: safe to run repeatedly (on install, update, or re-run). Never overwrites
the file wholesale — only adds/updates the specific keys Groundwork owns:
  - hooks.PreToolUse / hooks.Stop / hooks.SessionStart / hooks.PostToolUse /
    hooks.PostToolUseFailure: appends Groundwork's six hook entries (four hook
    scripts; groundwork_telemetry.py is registered three times — Stop for its
    per-turn record, PostToolUse/PostToolUseFailure for its per-tool-call record,
    added in the Usage Telemetry change) if not already present (matched by
    command string, so re-running never duplicates).
  - permissions.deny: adds Groundwork's destructive-command deny patterns, skipping
    any already present.
  - env.GATEGUARD_EXEMPT_GLOBS / env.NODE_USE_SYSTEM_CA: set only if the user hasn't
    already set that specific key to something else (never clobbers a user override).
  - env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: ONLY with --agent-teams, and only if
    the key is absent (Agent Teams are experimental and change how ordinary
    delegation behaves — see docs/en/agent-teams — so they are opt-in, never silent).
  - pluginConfigs["ecc@ecc"].options.hook_profile: set to "standard" only if unset.
  - statusLine: set to Groundwork's statusline script ONLY if the key is entirely
    absent — a user's own configured statusLine is never touched or replaced.
  - outputStyle: set to the built-in "Concise" style ONLY if the key is entirely
    absent — a user's own configured outputStyle (any value) is never touched.

outputStyle ownership: unlike statusLine (Groundwork's own absolute script path, which a
user could not plausibly set independently), "Concise" is a plain built-in Claude Code
style name a user could reasonably have already selected before ever installing
Groundwork. Value-equality alone (the pattern every other key here uses) cannot tell
"the user already had Concise" from "Groundwork set Concise" — so whenever merge() sets
outputStyle because the key was absent, a small sidecar file next to settings.json
(<settings.json>.groundwork-owned.json) records that Groundwork made that specific write.
unmerge_settings.py only removes outputStyle when this sidecar confirms Groundwork set it
AND the current value still matches — never from value-equality alone. This is not a
general settings-ownership framework: it exists for this one collision-prone key.

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
STATUSLINE_CMD = "python3 ~/.claude/groundwork/bin/groundwork_statusline.py"
STATUSLINE_VALUE = {"type": "command", "command": STATUSLINE_CMD}
# Built-in Claude Code output style (code.claude.com/docs/en/output-styles) that leads with the
# result and drops preamble/narration/recaps, while keeping full detail for anything needed to act
# safely (errors, failing tests, security warnings, destructive-action confirmations). Case-sensitive.
OUTPUT_STYLE_VALUE = "Concise"

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
PROFILE_ENV = "GROUNDWORK_PROFILE"  # machine-specific label recorded by telemetry; set via --profile, never shipped


def write_atomic(path: Path, text: str) -> None:
    """Write via a temp file + os.replace so a crash mid-write never truncates settings.json."""
    tmp = path.with_name(path.name + ".groundwork.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def ownership_path(settings_path: Path) -> Path:
    """Sidecar file path for the outputStyle-ownership record, colocated next to the settings
    file it tracks (never under CLAUDE_CONFIG_DIR/groundwork — that directory can be removed
    entirely before unmerge runs during uninstall, and a per-directory location would also let
    unrelated settings.json files share one record in tests). One settings.json, one sidecar."""
    return settings_path.with_name(settings_path.name + ".groundwork-owned.json")


def read_owned(owned_path: Path) -> dict:
    if not owned_path.exists():
        return {}
    try:
        data = json.loads(owned_path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_owned(owned_path: Path, owned: dict) -> None:
    """Empty record -> delete the sidecar entirely, so uninstall leaves no stray file behind."""
    if owned:
        write_atomic(owned_path, json.dumps(owned, indent=2) + "\n")
    elif owned_path.exists():
        owned_path.unlink()


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


PROFILE_OPT: dict = {"value": None}


def parse_args(argv: list[str]) -> tuple[bool, Path]:
    agent_teams = False
    path = None
    it = iter(argv)
    for arg in it:
        if arg == "--agent-teams":
            agent_teams = True
        elif arg == "--profile":
            PROFILE_OPT["value"] = next(it, None) or ""
        elif arg.startswith("-"):
            raise SystemExit(f"unknown option: {arg}")
        elif path is not None:
            raise SystemExit(f"unexpected extra argument: {arg}")
        else:
            path = Path(arg)
    if path is None:
        path = Path(os.path.expanduser("~/.claude/settings.json"))
    return agent_teams, path


def merge(data: dict, agent_teams: bool = False, profile: str | None = None) -> list[str]:
    """Apply Groundwork's additive merge to a settings dict in place; return the change list."""
    changed = []
    if profile:
        env0 = data.setdefault("env", {})
        if env0.get(PROFILE_ENV) != profile:
            env0[PROFILE_ENV] = profile
            changed.append(f"env.{PROFILE_ENV}={profile}")

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

    # Per-tool-call telemetry (Usage Telemetry, added alongside the per-turn Stop record above):
    # same script, same file, two more events — fires on every tool call, so matcher="" (every
    # tool) and a short timeout, since this must never add noticeable latency to a tool call.
    post = hooks.setdefault("PostToolUse", [])
    if not has_command(post, TELEMETRY_CMD):
        post.append(hook_entry(TELEMETRY_CMD, "Recording Groundwork tool-call telemetry...", matcher="", timeout=5))
        changed.append("hooks.PostToolUse: groundwork_telemetry.py")
    post_fail = hooks.setdefault("PostToolUseFailure", [])
    if not has_command(post_fail, TELEMETRY_CMD):
        post_fail.append(hook_entry(TELEMETRY_CMD, "Recording Groundwork tool-call telemetry...", matcher="", timeout=5))
        changed.append("hooks.PostToolUseFailure: groundwork_telemetry.py")

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

    if "statusLine" not in data:
        data["statusLine"] = dict(STATUSLINE_VALUE)
        changed.append(f"statusLine={STATUSLINE_CMD}")

    if "outputStyle" not in data:
        data["outputStyle"] = OUTPUT_STYLE_VALUE
        changed.append(f"outputStyle={OUTPUT_STYLE_VALUE}")

    return changed


def main() -> None:
    agent_teams, path = parse_args(sys.argv[1:])
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {}
    if path.exists():
        text = path.read_text().strip()
        if text:
            data = json.loads(text)

    changed = merge(data, agent_teams=agent_teams, profile=PROFILE_OPT["value"])
    write_atomic(path, json.dumps(data, indent=2) + "\n")

    if any(c.startswith("outputStyle=") for c in changed):
        # merge() just set outputStyle because the key was absent -> Groundwork owns this
        # write; record it so unmerge can later prove ownership instead of guessing from value.
        owned_path = ownership_path(path)
        owned = read_owned(owned_path)
        owned["outputStyle"] = data["outputStyle"]
        write_owned(owned_path, owned)

    if changed:
        print(f"Updated {path}:")
        for c in changed:
            print(f"  + {c}")
    else:
        print(f"{path} already has all Groundwork entries — nothing to do.")


if __name__ == "__main__":
    main()
