#!/usr/bin/env python3
"""Reverse of merge_settings.py — removes exactly the entries Groundwork's installer
added, leaving everything else in settings.json untouched. See merge_settings.py for
the list of keys this owns.

CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS is removed only when --agent-teams is passed AND
its value is "1" (the value the installer sets) — the installer cannot tell a value it
set from one the user set, so by default it leaves it alone and says so.

Known limitation (stateless by design — no Groundwork bookkeeping key is written into
settings.json): a value you had set yourself that equals what the installer sets is
removed on unmerge — a permissions.deny rule that is also one of Groundwork's rules
(e.g. "Bash(sudo *)"), an env default with the same value, or
pluginConfigs["ecc@ecc"].options.hook_profile == "standard". Re-add it afterwards if you
want to keep it. The merge side never duplicates or overwrites such a value.

Usage: python3 unmerge_settings.py [--agent-teams] [path to settings.json]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge_settings import (  # noqa: E402  (must follow the sys.path insert)
    AGENT_TEAMS_ENV,
    GROUNDWORK_DENY,
    GROUNDWORK_ENV_DEFAULTS,
    PUSH_CMD,
    REVIEW_CMD,
    SNAPSHOT_CMD,
    parse_args,
    write_atomic,
)


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


def unmerge(data: dict, agent_teams: bool = False) -> list[str]:
    """Remove Groundwork-owned entries from a settings dict in place; return what was removed."""
    removed: list = []

    hooks = data.get("hooks", {})
    remove_hook(hooks, "PreToolUse", PUSH_CMD, removed)
    remove_hook(hooks, "Stop", REVIEW_CMD, removed)
    remove_hook(hooks, "SessionStart", SNAPSHOT_CMD, removed)
    if "hooks" in data and not data["hooks"]:
        del data["hooks"]

    permissions = data.get("permissions", {})
    deny = permissions.get("deny", [])
    for rule in GROUNDWORK_DENY:
        if rule in deny:
            deny.remove(rule)
            removed.append(f"permissions.deny: {rule}")
    if "permissions" in data and "deny" in permissions and not deny:
        del permissions["deny"]
    if "permissions" in data and not permissions:
        del data["permissions"]

    env = data.get("env", {})
    for key, value in GROUNDWORK_ENV_DEFAULTS.items():
        if env.get(key) == value:
            del env[key]
            removed.append(f"env.{key}")
    if agent_teams and env.get(AGENT_TEAMS_ENV) == "1":
        del env[AGENT_TEAMS_ENV]
        removed.append(f"env.{AGENT_TEAMS_ENV}")
    if "env" in data and not env:
        del data["env"]

    plugin_configs = data.get("pluginConfigs", {})
    ecc = plugin_configs.get("ecc@ecc", {})
    options = ecc.get("options", {}) if isinstance(ecc, dict) else {}
    if options.get("hook_profile") == "standard":
        del options["hook_profile"]
        removed.append("pluginConfigs['ecc@ecc'].options.hook_profile")
    if isinstance(ecc, dict) and "options" in ecc and not options:
        del ecc["options"]
    if "ecc@ecc" in plugin_configs and not ecc:
        del plugin_configs["ecc@ecc"]
    if "pluginConfigs" in data and not plugin_configs:
        del data["pluginConfigs"]

    return removed


def main() -> None:
    agent_teams, path = parse_args(sys.argv[1:])
    if not path.exists():
        print(f"{path} does not exist — nothing to remove.")
        return

    data = json.loads(path.read_text().strip() or "{}")
    removed = unmerge(data, agent_teams=agent_teams)

    write_atomic(path, json.dumps(data, indent=2) + "\n")
    if removed:
        print(f"Updated {path}:")
        for r in removed:
            print(f"  - {r}")
    else:
        print(f"No Groundwork entries found in {path}.")
    if not agent_teams and data.get("env", {}).get(AGENT_TEAMS_ENV) is not None:
        print(f"Left env.{AGENT_TEAMS_ENV} in place (pass --agent-teams to remove a value of \"1\").")


if __name__ == "__main__":
    main()
