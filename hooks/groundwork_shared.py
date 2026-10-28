"""Small helpers shared by Groundwork's own hooks. Not a hook itself — never registered in
settings.json, never invoked directly by Claude Code. Installed alongside the hook files
(install.sh copies all of hooks/*.py) so the hooks that import it can find it as a sibling
module on their default sys.path.

Kept deliberately tiny: only what at least two hooks genuinely need identically. If a
helper is used by only one hook, it stays in that hook.
"""
import json
import os
import re
import stat
import subprocess
import time
from pathlib import Path

# Bash commands that look like a real test/validation run, not just any command. Originally
# defined only in groundwork_telemetry.py; moved here in Groundwork 2.0 Phase 4 because
# require_material_review.py's strengthened review-evidence check needs the exact same
# classification (has a validation command run since the last review?) and duplicating the
# pattern would risk the two hooks silently drifting apart on what counts as "tested".
TEST_CMD = re.compile(
    r"\b(pytest|npm test|npm run test|yarn test|go test|cargo test|make test|tox|nox|"
    r"unittest|terraform validate|terraform plan|kubectl .* --dry-run)\b|"
    r"python3?\s+\S*(?:tests?/|test_)\S*\.py\b"
)


def dirty_change_names(cwd: str) -> set[str]:
    """Names of openspec/changes/<name> directories that git shows as modified or untracked.

    Parses each porcelain line's path into segments instead of substring-matching the raw
    output: with `thing` (committed) and `add-thing` (dirty) in the same repo, a substring
    test wrongly flagged `thing` too (found by independent review of 1.1.0).
    """
    try:
        status = subprocess.run(
            # --untracked-files=all: a brand-new change directory otherwise collapses to one
            # "?? openspec/changes/" line instead of listing its files (caught by the 1.0.0 tests).
            ["git", "-C", cwd, "status", "--porcelain", "--untracked-files=all", "--", "openspec/changes"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return set()
    if status.returncode != 0:
        return set()
    names = set()
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:  # rename: "old -> new"
            path = path.split(" -> ", 1)[1]
        path = path.strip().strip('"')
        parts = path.split("/")
        if len(parts) > 2 and parts[0] == "openspec" and parts[1] == "changes":
            names.add(parts[2])
    return names


# ---- Which tools did this turn use? ---------------------------------------------------------------
# The Stop hooks (reply check, task brief) read the turn's tool calls from the session transcript. A session that
# is not saved (`claude -p --no-session-persistence`, some CI and SDK runs) has no transcript, so they fell silent
# there (found by the 2.5 benchmark). Fallback: the reply check marks each prompt's start time, and the turn's tool
# calls are this session's records in Groundwork's per-tool-call telemetry since then. With telemetry off, or no
# marker, the fallback finds nothing and the hooks stay silent, as before (fail-open).
TURN_MARKER_KEEP_S = 8 * 86400
TOOL_EVENTS_TAIL = 2 * 1024 * 1024


def _config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))


def _turn_marker(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", session_id)[:80] or "unknown"
    return _config_dir() / "groundwork" / "state" / "turns" / f"{safe}.json"


def mark_turn_start(session_id: str) -> None:
    """Record when the current prompt was submitted (UTC, whole seconds, the telemetry's own format)."""
    if not session_id:
        return
    marker = _turn_marker(session_id)
    marker.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = marker.with_name(f"{marker.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
    os.replace(tmp, marker)
    now = time.time()
    for old in marker.parent.glob("*.json"):
        try:
            if now - old.stat().st_mtime > TURN_MARKER_KEEP_S:
                old.unlink()
        except OSError:
            pass


def tools_since_turn_start(session_id: str) -> list:
    """Tool names this session recorded in telemetry since its last prompt; [] when unknown."""
    try:
        start = json.loads(_turn_marker(session_id).read_text()).get("ts")
    except (OSError, ValueError):
        return []
    override = os.environ.get("GROUNDWORK_TOOL_TELEMETRY_PATH")
    path = Path(os.path.expanduser(override)) if override else _config_dir() / "groundwork" / "telemetry" / "tool_events.jsonl"
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            f.seek(max(0, size - TOOL_EVENTS_TAIL))
            raw = f.read()
    except OSError:
        return []
    session_id = session_id[:64]  # telemetry stores the id cut to 64 chars (groundwork_telemetry.build_tool_record)
    tools = []
    for line in raw.splitlines():
        if session_id.encode() not in line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("session_id") == session_id and str(rec.get("ts") or "") >= start:
            name = str(rec.get("tool") or "")
            if name and name not in tools:
                tools.append(name)
    return tools


def turn_tools(data: dict, current_turn, turn_facts) -> list:
    """The turn's tool names: from the transcript when it exists, else from telemetry since the prompt."""
    path = str(data.get("transcript_path") or "")
    if path and os.path.isfile(path) and current_turn is not None:
        return turn_facts(current_turn(path) or []).get("tools", [])
    return tools_since_turn_start(str(data.get("session_id") or ""))


SAFE_ID = re.compile(r"[\w.:-]{1,100}")  # same rule as groundwork_telemetry.safe_id


def signals_path() -> Path:
    override = os.environ.get("GROUNDWORK_SIGNALS_PATH")
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))
    return Path(os.path.expanduser(override)) if override else base / "groundwork" / "telemetry" / "signals.jsonl"


def append_signal(rec: dict) -> None:
    """Owner-only append of one record to telemetry/signals.jsonl. Never follows a symlink, never blocks on a FIFO,
    and writes only to a regular file (openspec/changes/add-accuracy-signals D6). Raises on failure; callers catch."""
    if os.environ.get("GROUNDWORK_TELEMETRY", "").lower() == "off":
        return
    path = signals_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("signals path is not a regular file")
        os.write(fd, (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
    finally:
        os.close(fd)


def record_guardrail(session_id: str, prompt_id: str, hook: str, decision: str, cause: str = "policy",
                     tool_use_id: str = "") -> None:
    """One guardrail decision: hook, decision, cause and ids only. Silent and fail-open. An id is stored only when it
    looks like an id, so a malformed payload cannot put text into the record."""
    try:
        safe = lambda v: isinstance(v, str) and bool(SAFE_ID.fullmatch(v))
        rec = {"schema": 1, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "session_id": session_id if safe(session_id) else "unknown",
               "kind": "guardrail", "hook": hook, "decision": decision,
               "cause": cause if cause in ("policy", "internal_error") else "policy"}
        if safe(prompt_id):
            rec["prompt_id"] = prompt_id
        if safe(tool_use_id):
            rec["tool_use_id"] = tool_use_id
        append_signal(rec)
    except Exception:
        pass
