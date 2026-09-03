#!/usr/bin/env python3
"""Reverse of merge_settings.py — removes exactly the entries Groundwork's installer
added, leaving everything else in settings.json untouched. See merge_settings.py for
the list of keys this owns.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge_settings import GROUNDWORK_DENY, GROUNDWORK_ENV_DEFAULTS  # noqa: E402


def remove_hook(hooks: dict, event: str, target_command: str, removed: list) -> None:
    groups = hooks.get(event)
    if not groups:
        return
    new_groups = []
    found = False
    for group in groups:
        remaining = [h for h in group.get("hooks", []) if h.get("command") != target_command]
        if len(remaining) != len(group.get("hooks", [])):
            found = True
        if remaining:
            new_group = dict(group)
            new_group["hooks"] = remaining
            new_groups.append(new_group)
        # else: this group only ever contained our hook — drop the whole group
    if found:
        removed.append(f"hooks.{event}: {target_command}")
    if new_groups:
        hooks[event] = new_groups
    else:
        hooks.pop(event, None)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.path.expanduser("~/.claude/settings.json"))
    if not path.exists():
        print(f"{path} does not exist — nothing to remove.")
        return

    data = json.loads(path.read_text() or "{}")
    removed: list = []

    hooks = data.get("hooks", {})
    remove_hook(hooks, "PreToolUse", "python3 ~/.claude/hooks/block_protected_push.py", removed)
    remove_hook(hooks, "Stop", "python3 ~/.claude/hooks/require_material_review.py", removed)

    deny = data.get("permissions", {}).get("deny", [])
    for rule in GROUNDWORK_DENY:
        if rule in deny:
            deny.remove(rule)
            removed.append(f"permissions.deny: {rule}")

    env = data.get("env", {})
    for key, value in GROUNDWORK_ENV_DEFAULTS.items():
        if env.get(key) == value:
            del env[key]
            removed.append(f"env.{key}")

    path.write_text(json.dumps(data, indent=2) + "\n")
    if removed:
        print(f"Updated {path}:")
        for r in removed:
            print(f"  - {r}")
    else:
        print(f"No Groundwork entries found in {path}.")


if __name__ == "__main__":
    main()
