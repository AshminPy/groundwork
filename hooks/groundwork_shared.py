"""Small helpers shared by Groundwork's own hooks. Not a hook itself — never registered in
settings.json, never invoked directly by Claude Code. Installed alongside the hook files
(install.sh copies all of hooks/*.py) so the hooks that import it can find it as a sibling
module on their default sys.path.

Kept deliberately tiny: only what at least two hooks genuinely need identically. If a
helper is used by only one hook, it stays in that hook.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
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


def dirty_change_names(cwd: str, base: str | None = None) -> set[str]:
    """Names of openspec/changes/<name> directories that git shows as modified or untracked.

    `base` is the directory that holds openspec/ when it is not `cwd` (an OpenSpec store, see
    openspec_location()); a store is its own git repository, so git runs there.

    Parses each porcelain line's path into segments instead of substring-matching the raw
    output: with `thing` (committed) and `add-thing` (dirty) in the same repo, a substring
    test wrongly flagged `thing` too (found by independent review of 1.1.0).
    """
    try:
        status = subprocess.run(
            # --untracked-files=all: a brand-new change directory otherwise collapses to one
            # "?? openspec/changes/" line instead of listing its files (caught by the 1.0.0 tests).
            ["git", "-C", str(base or cwd), "status", "--porcelain", "--untracked-files=all", "--", "openspec/changes"],
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


# ---- Where OpenSpec changes live ------------------------------------------------------------------
# Default: <repo>/openspec/changes. Opt-in: with `openspec_store` (a store id registered with
# `openspec store setup`) in ~/.claude/groundwork/config.json, a repository without its own openspec/
# keeps its changes in that store, named "<repo key>-<change>" so repositories never clash. A repository
# that has openspec/ keeps the in-repo behaviour.
OPENSPEC_STORE_TIMEOUT = 5
_STORE_ROOTS: dict[str, Path | None] = {}  # per hook process
_TOPLEVELS: dict[str, str] = {}


def repo_key(root: str) -> str:
    """<slug>-<sha256(root)[:10]>: the same scheme as the task ledger and investigation files."""
    root = os.path.abspath(root)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", os.path.basename(root.rstrip("/"))).strip("-").lower() or "repo"
    return f"{slug}-{hashlib.sha256(root.encode('utf-8')).hexdigest()[:10]}"


def openspec_store_id() -> str:
    """The configured store id (scripts/groundwork_config.py owns the key), or "" when unset."""
    for d in (_config_dir() / "groundwork" / "bin", Path(__file__).resolve().parent.parent / "scripts"):
        if (d / "groundwork_config.py").is_file() and str(d) not in sys.path:
            sys.path.append(str(d))
    try:
        import groundwork_config
        return groundwork_config.openspec_store(
            groundwork_config.load_config(_config_dir() / "groundwork" / "config.json"))
    except Exception:
        return ""


def openspec_store_root(store_id: str) -> Path | None:
    """The store's folder, from `openspec store list --json` ({"stores": [{"id", "root"}]}); None if unknown."""
    if store_id not in _STORE_ROOTS:
        root = None
        try:
            r = subprocess.run(["openspec", "store", "list", "--json"], capture_output=True, text=True,
                               timeout=OPENSPEC_STORE_TIMEOUT, stdin=subprocess.DEVNULL)
            for st in json.loads(r.stdout or "{}").get("stores", []):
                if st.get("id") == store_id and st.get("root"):
                    root = Path(st["root"])
        except Exception:
            root = None
        _STORE_ROOTS[store_id] = root
    return _STORE_ROOTS[store_id]


def openspec_location(root: str) -> tuple[Path, str, str]:
    """(base, store id, change-name prefix) for a repository: changes live in base/openspec/changes.
    In-repo (today's behaviour): (root, "", ""). Store mode: (store folder, id, "<repo key>-"); the base
    stays `root` when the store is not registered, so callers find nothing and create nothing there."""
    if (Path(root) / "openspec").is_dir():
        return Path(root), "", ""
    store = openspec_store_id()
    if not store:
        return Path(root), "", ""
    top = _TOPLEVELS.get(str(root))
    if top is None:
        try:
            top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True,
                                 text=True, timeout=5, stdin=subprocess.DEVNULL).stdout.strip()
        except Exception:
            top = ""
        top = _TOPLEVELS[str(root)] = top or str(root)
    if (Path(top) / "openspec").is_dir():
        return Path(root), "", ""  # a subdirectory of a repository that keeps its own openspec/
    return openspec_store_root(store) or Path(root), store, repo_key(top) + "-"


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
