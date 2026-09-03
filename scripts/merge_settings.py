#!/usr/bin/env python3
"""Merge Groundwork's required settings.json entries into an existing Claude Code
settings file, without touching anything else the user has configured.

Idempotent: safe to run repeatedly (on install, update, or re-run). Never overwrites
the file wholesale — only adds/updates the specific keys Groundwork owns:
  - hooks.PreToolUse / hooks.Stop: appends Groundwork's two hook entries if not
    already present (matched by command string, so re-running never duplicates).
  - permissions.deny: adds Groundwork's destructive-command deny patterns, skipping
    any already present.
  - env.GATEGUARD_EXEMPT_GLOBS / env.NODE_USE_SYSTEM_CA: set only if the user hasn't
    already set that specific key to something else (never clobbers a user override).
  - pluginConfigs["ecc@ecc"].options.hook_profile: set to "standard" only if unset.

Usage: python3 merge_settings.py [path to settings.json, default ~/.claude/settings.json]
"""
import json
import os
import sys
from pathlib import Path

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


def hook_entry(command: str, status_message: str, matcher: str | None = None) -> dict:
    entry = {"type": "command", "command": command, "statusMessage": status_message}
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


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.path.expanduser("~/.claude/settings.json"))
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {}
    if path.exists():
        text = path.read_text().strip()
        if text:
            data = json.loads(text)

    changed = []

    hooks = data.setdefault("hooks", {})

    pre = hooks.setdefault("PreToolUse", [])
    push_cmd = "python3 ~/.claude/hooks/block_protected_push.py"
    if not has_command(pre, push_cmd):
        pre.append(hook_entry(push_cmd, "Checking protected-branch push guard...", matcher="Bash"))
        changed.append("hooks.PreToolUse: block_protected_push.py")

    stop = hooks.setdefault("Stop", [])
    review_cmd = "python3 ~/.claude/hooks/require_material_review.py"
    if not has_command(stop, review_cmd):
        stop.append(hook_entry(review_cmd, "Checking material-change review gate..."))
        changed.append("hooks.Stop: require_material_review.py")

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

    plugin_configs = data.setdefault("pluginConfigs", {})
    ecc_config = plugin_configs.setdefault("ecc@ecc", {}).setdefault("options", {})
    if "hook_profile" not in ecc_config:
        ecc_config["hook_profile"] = "standard"
        changed.append("pluginConfigs['ecc@ecc'].options.hook_profile=standard")

    path.write_text(json.dumps(data, indent=2) + "\n")

    if changed:
        print(f"Updated {path}:")
        for c in changed:
            print(f"  + {c}")
    else:
        print(f"{path} already has all Groundwork entries — nothing to do.")


if __name__ == "__main__":
    main()
