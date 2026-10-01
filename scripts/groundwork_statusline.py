#!/usr/bin/env python3
"""Groundwork 2.1 statusLine — a Claude Code `statusLine` command rendering Groundwork-specific
state. See openspec/changes/add-statusline/ for the full design.

Every displayed field is exactly one of:
  LIVE                 stdin JSON Claude Code supplies on every refresh, or a fast (short-timeout)
                        `git` call scoped to the current working directory.
  LAST-COMPLETED-TURN   read from the existing telemetry log (hooks/groundwork_telemetry.py's
                        events.jsonl), filtered to the CURRENT session's own session_id only —
                        never another session's most recent record. Rendered with a leading `~` so
                        it is never mistaken for the in-progress turn's state.
  CACHED                the capability profile (config.json), the Integration Catalog readiness
                        cache (integrations/cache.json, written only by
                        `groundwork_integrations.py refresh` — NEVER by this script), and the
                        installed Groundwork version (VERSION).
  UNAVAILABLE           review/MUST-FIX state, role/persona, evidence-label counts — no durable
                        source exists anywhere in Groundwork today. Never displayed, never guessed.

This process performs NO integration probes (no `claude mcp list`, no `gh auth status`, no
network call, no cloud/CLI probe) and no unbounded repository scan. Its only subprocess call is
one short-timeout `git status` read. It never raises and never exits non-zero for a rendering
problem — worst case it prints a minimal fallback line.

Usage (as Claude Code's statusLine command): stdin gets the JSON payload; stdout is the rendered
line(s). Configure via ~/.claude/groundwork/statusline-config.json (compact/detailed, per-section
show/hide, plain-text-vs-Unicode-symbol) — a small file, deliberately separate from config.json
(see design.md Decision 6: groundwork_config.py's `init --force` unconditionally rewrites
config.json on every `--configure`, which would silently discard personalization stored there).
"""
import argparse
import calendar
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
CONFIG_PATH = CLAUDE_DIR / "groundwork" / "config.json"
TELEMETRY_PATH = (
    Path(os.path.expanduser(os.environ.get("GROUNDWORK_TELEMETRY_PATH", "")))
    if os.environ.get("GROUNDWORK_TELEMETRY_PATH")
    else CLAUDE_DIR / "groundwork" / "telemetry" / "events.jsonl"
)
INTEGRATIONS_CACHE_PATH = CLAUDE_DIR / "groundwork" / "integrations" / "cache.json"
VERSION_PATH = CLAUDE_DIR / "groundwork" / "VERSION"
STATUSLINE_CONFIG_PATH = CLAUDE_DIR / "groundwork" / "statusline-config.json"

GIT_TIMEOUT_S = 2.0  # short and bounded — a hang here must never block the statusLine render
TAIL_INITIAL_BYTES = 65536       # first backward-scan window for events.jsonl
TAIL_MAX_BYTES = 4 * 65536       # hard cap — see design.md Decision 4's documented trade-off
STALE_AFTER_S = 15 * 60          # cached integration readiness older than this is marked stale

DEFAULT_STATUSLINE_CONFIG = {
    "mode": "compact",           # "compact" | "detailed"
    "show_integrations": True,
    "show_context": True,
    "show_cost": False,
    "show_validation": True,
    "plain_text": False,         # True: ASCII-only fallback, no Unicode symbols
    "max_integrations": 4,       # compact mode only; detailed shows all cached, non-empty entries
    "integrations_min_state": "available",  # "available" | "configured" | "connected" — lowest
                                             # summary state still shown (e.g. "connected" hides
                                             # ○ AVAILABLE-only and ◐ CONFIGURED-but-not-connected
                                             # entries, such as a plugin-installed MCP server never
                                             # actually signed into); default keeps existing behavior
}

SUMMARY_SYMBOL = {"CONNECTED": "●", "CONFIGURED": "◐", "AVAILABLE": "○"}  # ● ◐ ○
SUMMARY_PLAIN = {"CONNECTED": "connected", "CONFIGURED": "configured", "AVAILABLE": "available"}
SUMMARY_RANK = {"AVAILABLE": 0, "CONFIGURED": 1, "CONNECTED": 2}  # ordering for integrations_min_state

# One entry per DEFAULT_STATUSLINE_CONFIG key, used only by the `config` CLI below (get/set/unset/
# list) to validate a value before writing it — the renderer itself never consults this; it stays
# permissive and fails safe on anything malformed (see _load_statusline_config()).
KEY_SCHEMA = {
    "mode": ("choice", ["compact", "detailed"]),
    "show_integrations": ("bool", None),
    "show_context": ("bool", None),
    "show_cost": ("bool", None),
    "show_validation": ("bool", None),
    "plain_text": ("bool", None),
    "max_integrations": ("int", None),
    "integrations_min_state": ("choice", ["available", "configured", "connected"]),
}


# ---------------------------------------------------------------------------------------------
# Readers — every one fails safe to "no data" on any error; none ever raises.
# ---------------------------------------------------------------------------------------------
def _read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_profile() -> Optional[str]:
    try:
        cfg = json.loads(CONFIG_PATH.read_text())
        if isinstance(cfg, dict):
            p = cfg.get("profile")
            if isinstance(p, str) and p:
                return p
    except Exception:
        pass
    return None


def _load_version() -> Optional[str]:
    try:
        v = VERSION_PATH.read_text().strip()
        return v or None
    except Exception:
        return None


def _load_statusline_config() -> dict:
    cfg = dict(DEFAULT_STATUSLINE_CONFIG)
    try:
        data = json.loads(STATUSLINE_CONFIG_PATH.read_text())
        if isinstance(data, dict):
            for key in DEFAULT_STATUSLINE_CONFIG:
                if key in data and isinstance(data[key], type(DEFAULT_STATUSLINE_CONFIG[key])):
                    cfg[key] = data[key]
    except Exception:
        pass  # malformed/missing: documented defaults, never a crash
    return cfg


def _load_integrations_cache() -> dict:
    """Read-only. This is the ONLY way Integration Catalog readiness reaches the statusLine —
    never a live probe (see module docstring and design.md's Performance requirement)."""
    try:
        data = json.loads(INTEGRATIONS_CACHE_PATH.read_text())
        integrations = data.get("integrations") if isinstance(data, dict) else None
        return integrations if isinstance(integrations, dict) else {}
    except Exception:
        return {}


def _cache_age_seconds(checked_at: str) -> Optional[int]:
    try:
        t = time.strptime(checked_at, "%Y-%m-%dT%H:%M:%SZ")
        checked_epoch = calendar.timegm(t)  # `t` is UTC (the "Z" in the format) — timegm, not mktime
        return max(0, int(time.time()) - checked_epoch)
    except Exception:
        return None


def _age_label(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _git_status(cwd: Optional[str]):
    """One subprocess call (branch + dirty in a single `git status --porcelain --branch`), short
    timeout, scoped to the stdin JSON's own working directory — inherently session/worktree-safe
    because it is live, not a shared file. Returns (branch, dirty) or None on any failure/timeout."""
    if not cwd:
        return None
    try:
        r = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain", "--branch"],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_S,
        )
        if r.returncode != 0:
            return None
        lines = r.stdout.splitlines()
        if not lines or not lines[0].startswith("##"):
            return None
        header = lines[0][3:]
        # An unborn/empty repo (no commits yet) prints "## No commits yet on <branch>", not
        # "## <branch>...<upstream>" — naively splitting that would misparse "No" as the branch
        # name (a false LIVE field, live-reproduced during review). Handle it explicitly.
        no_commits_prefix = "No commits yet on "
        if header.startswith(no_commits_prefix):
            branch = header[len(no_commits_prefix):].strip()
        else:
            branch = header.split("...")[0].split(" ")[0].strip()
        if not branch:
            return None
        dirty = len(lines) > 1
        return branch, dirty
    except Exception:
        return None


def _last_turn_for_session(session_id: Optional[str]) -> Optional[dict]:
    """Bounded backward scan of the shared telemetry log for the most recent record whose
    session_id matches the CURRENT session — never the file's last line unfiltered (that could
    belong to a different, more recently-stopped concurrent session). Grows the read window up to
    TAIL_MAX_BYTES; if no match is found within that bound, returns None (UNAVAILABLE for this
    render) rather than paying an unbounded full-file scan — see design.md Decision 4."""
    if not session_id:
        return None
    try:
        if not TELEMETRY_PATH.exists():
            return None
        size = TELEMETRY_PATH.stat().st_size
        if size == 0:
            return None
        read_size = min(size, TAIL_INITIAL_BYTES)
        with TELEMETRY_PATH.open("rb") as f:
            while True:
                f.seek(max(0, size - read_size))
                chunk = f.read()
                lines = chunk.split(b"\n")
                if read_size < size:
                    lines = lines[1:]  # first line may be a partial line — drop unless at file start
                for raw_line in reversed(lines):
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(record, dict) and record.get("session_id") == session_id:
                        return record
                if read_size >= size or read_size >= TAIL_MAX_BYTES:
                    return None
                read_size = min(read_size * 4, TAIL_MAX_BYTES, size)
    except Exception:
        return None


def _last_turn_fields(record: Optional[dict]) -> dict:
    if not isinstance(record, dict):
        return {}
    declared = record.get("declared")
    observed = record.get("observed")
    declared = declared if isinstance(declared, dict) else {}
    observed = observed if isinstance(observed, dict) else {}
    return {
        "playbook": declared.get("playbook"),
        "execution_mode": declared.get("execution_mode"),
        "tests_run": observed.get("tests_run"),
    }


# ---------------------------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------------------------
def _fmt_git(git, plain: bool) -> Optional[str]:
    if git is None:
        return None
    branch, dirty = git
    if plain:
        return f"{branch} (dirty)" if dirty else f"{branch} (clean)"
    return f"{branch}✗" if dirty else f"{branch}✓"  # branch✗ / branch✓


def _fmt_context(stdin: dict) -> Optional[str]:
    cw = stdin.get("context_window")
    if not isinstance(cw, dict):
        return None
    pct = cw.get("used_percentage")
    if not isinstance(pct, (int, float)):
        return None
    return f"ctx {pct:.0f}%"


def _fmt_cost(stdin: dict) -> Optional[str]:
    cost = stdin.get("cost")
    if not isinstance(cost, dict):
        return None
    usd = cost.get("total_cost_usd")
    if not isinstance(usd, (int, float)):
        return None
    return f"${usd:.2f}"


def _fmt_last_turn(fields: dict, plain: bool, show_validation: bool) -> Optional[str]:
    if not fields:
        return None
    parts = []
    playbook = fields.get("playbook")
    if playbook and playbook != "unknown":
        parts.append(playbook)
    mode = fields.get("execution_mode")
    if mode and mode not in ("single_agent", "unknown"):
        parts.append({"subagents": "subagent", "agent_team": "agent team"}.get(mode, mode))
    if show_validation and fields.get("tests_run") is True:
        parts.append("tests run")
    if not parts:
        return None
    marker = "last: " if plain else "~"
    sep = " - " if plain else " · "  # ' - ' / ' · '
    return marker + sep.join(parts)


def _fmt_integrations(cache: dict, cfg: dict, plain: bool) -> Optional[str]:
    if not cache:
        return None
    min_state = cfg.get("integrations_min_state", "available")
    min_rank = SUMMARY_RANK.get(str(min_state).upper(), 0)  # unrecognized value falls back to "available"
    entries = []
    for name, obs in sorted(cache.items()):
        if not isinstance(obs, dict):
            continue
        summary = obs.get("summary")
        if summary not in SUMMARY_SYMBOL:  # NOT CONFIGURED entries add noise, not signal — skip
            continue
        if SUMMARY_RANK[summary] < min_rank:  # below the configured floor (e.g. "connected") — skip
            continue
        checked_at = obs.get("checked_at")
        age_s = _cache_age_seconds(checked_at) if isinstance(checked_at, str) else None
        label = SUMMARY_PLAIN[summary] if plain else SUMMARY_SYMBOL[summary]
        text = f"{name} {label}"
        # Every cached observation shows its age — even fresh — so CACHED is never visually
        # mistaken for LIVE (a fresh cache entry is still "connected as of a moment ago", not
        # "connected right now"). A stale entry (>= STALE_AFTER_S) additionally gets a leading
        # "!" on the age itself, so it stays distinguishable from a merely-fresh one at a glance,
        # without a verbose "CACHED:"/"stale:" label.
        if age_s is not None:
            age_label = _age_label(age_s)
            if age_s >= STALE_AFTER_S:
                age_label = "!" + age_label
            sep = " - " if plain else " · "
            text += f"{sep}{age_label}"
        entries.append(text)
    if not entries:
        return None
    if cfg.get("mode") != "detailed":
        entries = entries[: max(1, int(cfg.get("max_integrations", 4)))]
    return (" | " if plain else " │ ").join(entries)


def render(stdin: dict, cfg: dict) -> str:
    plain = bool(cfg.get("plain_text"))
    sep = " | " if plain else " │ "  # ' | ' / ' │ '

    profile = _load_profile()
    version = _load_version()
    session_id = stdin.get("session_id")
    workspace = stdin.get("workspace")
    cwd = workspace.get("current_dir") if isinstance(workspace, dict) else stdin.get("cwd")

    git = _git_status(cwd)
    last_turn = _last_turn_fields(_last_turn_for_session(session_id))
    integrations_cache = _load_integrations_cache() if cfg.get("show_integrations", True) else {}

    head = "GROUNDWORK"
    if profile:
        head += f" - {profile}" if plain else f" · {profile}"
    if cfg.get("mode") == "detailed" and version:
        head += f" (v{version})" if plain else f" · v{version}"

    line2_parts = []
    git_s = _fmt_git(git, plain)
    if git_s:
        line2_parts.append(git_s)
    if cfg.get("show_context", True):
        ctx_s = _fmt_context(stdin)
        if ctx_s:
            line2_parts.append(ctx_s)
    if cfg.get("show_cost", False):
        cost_s = _fmt_cost(stdin)
        if cost_s:
            line2_parts.append(cost_s)
    lt_s = _fmt_last_turn(last_turn, plain, cfg.get("show_validation", True))
    if lt_s:
        line2_parts.append(lt_s)

    if cfg.get("mode") == "detailed":
        lines = [head]
        if line2_parts:
            lines.append(sep.join(line2_parts))
        integ_s = _fmt_integrations(integrations_cache, cfg, plain) if cfg.get("show_integrations", True) else None
        if integ_s:
            lines.append(integ_s)
        return "\n".join(lines)

    # compact: everything on one line
    compact_parts = [head] + line2_parts
    integ_s = _fmt_integrations(integrations_cache, cfg, plain) if cfg.get("show_integrations", True) else None
    if integ_s:
        compact_parts.append(integ_s)
    return sep.join(compact_parts)


def main() -> int:
    stdin = _read_stdin_json()
    try:
        cfg = _load_statusline_config()
        print(render(stdin, cfg))
    except Exception:
        print("GROUNDWORK")  # last-resort fallback — never blank, never a traceback, never non-zero
    return 0


# ---------------------------------------------------------------------------------------------
# `groundwork statusline config` — reachable only via explicit argv (never how Claude Code invokes
# this script, which always runs it with zero arguments and JSON on stdin — see main() above).
# Reads/writes statusline-config.json directly; never touches config.json, consistent with this
# file's whole design (see the module docstring's statusline-config.json note).

def _parse_value(key: str, raw: str):
    kind, choices = KEY_SCHEMA[key]
    if kind == "bool":
        low = raw.strip().lower()
        if low in ("true", "1", "yes", "on"):
            return True
        if low in ("false", "0", "no", "off"):
            return False
        raise ValueError(f"'{raw}' is not a valid boolean — use true/false")
    if kind == "int":
        try:
            value = int(raw)
        except ValueError:
            raise ValueError(f"'{raw}' is not a valid integer")
        if value < 1:
            raise ValueError("must be at least 1")
        return value
    if kind == "choice":
        if raw not in choices:
            raise ValueError(f"'{raw}' is not one of: {', '.join(choices)}")
        return raw
    raise AssertionError(key)  # unreachable — every KEY_SCHEMA entry has a handled kind


def _read_custom_statusline_config() -> dict:
    """The raw on-disk override file only, never merged with defaults — distinct from
    _load_statusline_config(), which returns the full effective (default+override) config the
    renderer actually uses. Used by the config CLI to know what's actually been customized."""
    try:
        data = json.loads(STATUSLINE_CONFIG_PATH.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_custom_statusline_config(data: dict) -> None:
    STATUSLINE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUSLINE_CONFIG_PATH.write_text(json.dumps(data, indent=2) + "\n")


def cmd_config_list(_args) -> int:
    custom = _read_custom_statusline_config()
    effective = _load_statusline_config()
    for key in DEFAULT_STATUSLINE_CONFIG:
        is_custom = key in custom and isinstance(custom[key], type(DEFAULT_STATUSLINE_CONFIG[key]))
        source = "custom" if is_custom else "default"
        print(f"{key:<24} {json.dumps(effective[key]):<10} ({source})")
    return 0


def cmd_config_get(args) -> int:
    if args.key not in DEFAULT_STATUSLINE_CONFIG:
        print(f"config get: unknown key '{args.key}' — run 'groundwork statusline config list' for valid keys",
              file=sys.stderr)
        return 1
    effective = _load_statusline_config()
    print(json.dumps(effective[args.key]))
    return 0


def cmd_config_set(args) -> int:
    if args.key not in KEY_SCHEMA:
        print(f"config set: unknown key '{args.key}' — run 'groundwork statusline config list' for valid keys",
              file=sys.stderr)
        return 1
    try:
        value = _parse_value(args.key, args.value)
    except ValueError as e:
        print(f"config set: {e}", file=sys.stderr)
        return 1
    custom = _read_custom_statusline_config()
    custom[args.key] = value
    _write_custom_statusline_config(custom)
    print(f"{args.key} = {json.dumps(value)}")
    return 0


def cmd_config_unset(args) -> int:
    if args.key not in DEFAULT_STATUSLINE_CONFIG:
        print(f"config unset: unknown key '{args.key}' — run 'groundwork statusline config list' for valid keys",
              file=sys.stderr)
        return 1
    custom = _read_custom_statusline_config()
    if args.key in custom:
        del custom[args.key]
        _write_custom_statusline_config(custom)
    print(f"{args.key} reverted to default ({json.dumps(DEFAULT_STATUSLINE_CONFIG[args.key])})")
    return 0


def cmd_config(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="groundwork statusline config",
        description="View or change statusline display settings (statusline-config.json). "
                     "Never touches config.json and is never overwritten by install.sh/--configure.",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    p_list = sub.add_parser("list", help="show every setting, its current value, and whether it's default or custom")
    p_list.set_defaults(func=cmd_config_list)
    p_get = sub.add_parser("get", help="print one setting's current effective value")
    p_get.add_argument("key")
    p_get.set_defaults(func=cmd_config_get)
    p_set = sub.add_parser("set", help="set a setting")
    p_set.add_argument("key")
    p_set.add_argument("value")
    p_set.set_defaults(func=cmd_config_set)
    p_unset = sub.add_parser("unset", help="remove a setting, reverting it to its default")
    p_unset.add_argument("key")
    p_unset.set_defaults(func=cmd_config_unset)
    args = parser.parse_args(argv)
    return args.func(args)


def _print_statusline_cli_usage() -> None:
    print("usage: groundwork statusline config {list,get,set,unset} ...\n"
          "  config list              show every statusline setting, value, and whether it's default or custom\n"
          "  config get KEY           print one setting's current effective value\n"
          "  config set KEY VALUE     set a setting (persists in statusline-config.json)\n"
          "  config unset KEY         remove a setting, reverting it to its default",
          file=sys.stderr)


if __name__ == "__main__":
    # Claude Code's statusLine mechanism always invokes this script with zero arguments and JSON
    # on stdin (see main() above) — argv dispatch here is reachable only from an explicit CLI call
    # ("groundwork statusline config ..."), never from a real statusLine render, so it can never
    # collide with or slow down the render path.
    if len(sys.argv) > 1:
        if sys.argv[1] == "config":
            sys.exit(cmd_config(sys.argv[2:]))
        _print_statusline_cli_usage()
        sys.exit(0 if sys.argv[1] in ("-h", "--help") else 1)
    sys.exit(main())
