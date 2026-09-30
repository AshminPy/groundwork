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
}

SUMMARY_SYMBOL = {"CONNECTED": "●", "CONFIGURED": "◐", "AVAILABLE": "○"}  # ● ◐ ○
SUMMARY_PLAIN = {"CONNECTED": "connected", "CONFIGURED": "configured", "AVAILABLE": "available"}


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
    entries = []
    for name, obs in sorted(cache.items()):
        if not isinstance(obs, dict):
            continue
        summary = obs.get("summary")
        if summary not in SUMMARY_SYMBOL:  # NOT CONFIGURED entries add noise, not signal — skip
            continue
        checked_at = obs.get("checked_at")
        age_s = _cache_age_seconds(checked_at) if isinstance(checked_at, str) else None
        label = SUMMARY_PLAIN[summary] if plain else SUMMARY_SYMBOL[summary]
        text = f"{name} {label}"
        if age_s is not None and age_s >= STALE_AFTER_S:
            text += f" ({_age_label(age_s)})"
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


if __name__ == "__main__":
    sys.exit(main())
