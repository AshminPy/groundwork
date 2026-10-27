#!/usr/bin/env python3
"""SessionStart / PreCompact / Stop hook — per-task brief that survives compaction and new sessions.

Why a hook: the investigation-continuity file (engineering-workflow.md §7) only works when Claude
remembers to write it and to read the "READ FIRST" pointer. Feature 3 of
openspec/changes/core-evidence-continuity moves the remembering into hooks.

One brief per repository branch, at
  <config>/groundwork/briefs/<repo-key>/<branch>-<sha256(branch)[:8]>.md
where <repo-key> is the same <slug>-<sha256(repo root)[:10]> the snapshot hook uses for
investigations, so a branch's brief can never load in another repository or on another branch.

The brief has two kinds of content:
  - judgment sections Claude writes (Goal, Decisions, Verified facts, Rejected, Next step);
  - a `## Snapshot (hook-written ...)` section that this hook rewrites. Nothing outside it is
    ever changed.

Decision log: beside each brief, `<brief>.decisions.md` is an append-only history of the
Decisions and Rejected sections. On every save the hook compares those sections with what it saw
last time (sidecar `<brief>.decisions-state.json`): a new or changed line is appended as ADDED, with
the links or file:line references it cites (or "no evidence cited"); a line that disappeared is
appended as REMOVED. Existing log bytes are never rewritten, so a decision is never lost even when
the brief is edited, and the log can be shown to others to explain why each choice was made.

Events:
  PreCompact   refresh the snapshot (creating the brief from the template when missing). Never blocks.
  Stop         after a turn that used a real tool: refresh the snapshot. If the session is
               substantive (3+ tool-using turns in Groundwork telemetry), the judgment sections are
               still empty, and this session was not asked before, ask once (`decision: "block"`) for
               Goal and Next step; separately, if a Decisions or Rejected line cites no link or
               file:line, ask once per session to add one. Never when `stop_hook_active`.
  SessionStart load the current branch's brief as context (startup, resume, clear and compact),
               Next step first, then the latest decision-log entries, capped, labelled as data to verify.

Fail-open: any error means no output and exit 0. GROUNDWORK_BRIEF=off disables it.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from groundwork_telemetry import current_turn, turn_facts  # shared transcript parsing
except Exception:
    current_turn = turn_facts = None

GIT_TIMEOUT = 3
MAX_CONTEXT = 2400
SUBSTANTIVE_TURNS = 3
TELEMETRY_TAIL = 2 * 1024 * 1024
MARKER_KEEP_S = 8 * 86400
JUDGMENT_ORDER = ("Next step", "Goal", "Decisions", "Verified facts", "Rejected")
LOG_SECTIONS = ("decisions", "rejected")
LOG_LINE_CAP = 500
LOG_TAIL = 5
LOG_RESERVE = 700  # room kept for the decision-log tail when the brief itself is long
# Concurrent sessions on one branch can both append the same entry (or header): duplicates, never loss.
# Same reference shapes the reply check accepts (hooks/groundwork_reply_check.py), every repeat bounded.
REFERENCE = re.compile(
    r"https?://[^\s)>\]]+"
    r"|(?<![\w./-])[\w./-]{1,200}\.\w{1,10}:\d+(?:-\d+)?"
    r"|`[^`\s]{0,200}/[^`\s]{0,200}\.\w{1,10}`"
)
BOOKKEEPING = {"ToolSearch", "TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet"}
TEMPLATE = (
    "<!-- Claude writes the sections above the Snapshot. The Snapshot section is rewritten by a "
    "Groundwork hook; nothing else in this file is changed by it. -->\n\n"
    "## Goal\n\n## Decisions\n<!-- One decision per line, each with its evidence: a link or file:line. -->\n\n"
    "## Verified facts\n\n## Rejected\n<!-- One rejected option per line, with the evidence that rejected it. -->\n\n"
    "## Next step\n\n"
)
HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)
# Only the exact heading this hook writes; "## Snapshot hook decisions" written by Claude must never match (review finding).
SNAPSHOT_HEAD = re.compile(r"^##[ \t]+Snapshot[ \t]+\(hook-written\b.*$", re.MULTILINE)
SNAPSHOT_TITLE = re.compile(r"^Snapshot[ \t]+\(hook-written\b")
# Unicode categories removed before brief text reaches the model: controls (Cc, except newline and tab), format
# characters (Cf: zero-width, bidi marks, soft hyphen, invisible tag characters U+E0000-E007F) and line/paragraph
# separators. A category rule rather than a hand-picked list, which missed several (review finding).
STRIP_CATEGORIES = {"Cc", "Cf", "Zl", "Zp"}


def clean(text: str) -> str:
    return "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch) not in STRIP_CATEGORIES)


def config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))


def git(cwd: str, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=GIT_TIMEOUT)
    except Exception:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def repo_key(root: str) -> str:
    """Must stay identical to groundwork_session_snapshot.investigation_path()'s file stem (tested)."""
    root = os.path.abspath(root)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", os.path.basename(root.rstrip("/"))).strip("-").lower() or "repo"
    return f"{slug}-{hashlib.sha256(root.encode('utf-8')).hexdigest()[:10]}"


def brief_path(cwd: str) -> Path | None:
    root = git(cwd, "rev-parse", "--show-toplevel") if cwd else None
    if not root:
        return None
    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD") or "HEAD"
    if branch == "HEAD":
        branch = "detached-" + (git(cwd, "rev-parse", "--short", "HEAD") or "unknown")
    # Readable part plus a hash of the exact branch name: cleaning alone is lossy (feat/x and feat-x, or two
    # long names with one prefix, would share a file and load each other's brief — review finding).
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", branch).strip("-.")[:80] or "branch"
    digest = hashlib.sha256(branch.encode("utf-8")).hexdigest()[:8]
    return config_dir() / "groundwork" / "briefs" / repo_key(root) / f"{name}-{digest}.md"


def sections(text: str) -> list:
    """[(heading, body)] for every '## ' section."""
    heads = list(HEADING.finditer(text))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out.append((m.group(1).strip(), text[m.end():end].strip("\n")))
    return out


def _body_text(body: str) -> str:
    return "\n".join(ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("<!--")).strip()


def judgment_filled(text: str) -> bool:
    return any(_body_text(body) for head, body in sections(text) if not SNAPSHOT_TITLE.match(head))


def refresh_snapshot(text: str, facts: list) -> str:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    block = f"## Snapshot (hook-written {stamp})\n" + "".join(f"- {f}\n" for f in facts)
    if not text.strip():
        return "# Task brief\n\n" + TEMPLATE + block
    m = SNAPSHOT_HEAD.search(text)
    if not m:
        sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
        return text + sep + block
    nxt = HEADING.search(text, m.end())
    tail = text[nxt.start():] if nxt else ""
    return text[:m.start()] + block + ("\n" + tail if tail else "")


def git_facts(cwd: str, session_id: str, event: str, tools: list) -> list:
    facts = [f"updated by: {event} · session {session_id[:12] or 'unknown'}"]
    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    head = git(cwd, "log", "-1", "--format=%h %s")
    if branch:
        facts.append(f"branch: {branch}")
    if head:
        facts.append(f"HEAD: {clean(head)[:120]}")
    status = git(cwd, "status", "--porcelain")
    if status is not None:
        facts.append(f"uncommitted files: {len([ln for ln in status.splitlines() if ln.strip()])}")
    if tools:
        facts.append("tools in the last turn: " + ", ".join(tools[:12]))
    return facts


def _signature(path: Path):
    try:
        st = path.stat()
        return (st.st_mtime_ns, st.st_size, st.st_ino)
    except FileNotFoundError:
        return None


def _private_dirs(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    for d in (path.parent, path.parent.parent):  # <repo-key>/ and briefs/; mkdir's mode covers only the leaf
        os.chmod(d, 0o700)


def write_private(path: Path, data: bytes, expected="any") -> bool:
    """Owner-only atomic write. With `expected`, the write is dropped when the file changed since it was read."""
    _private_dirs(path)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    if expected != "any" and _signature(path) != expected:
        tmp.unlink()  # someone (e.g. Claude) edited the brief meanwhile; their edit wins
        return False
    # Residual window: microseconds between this check and the replace. Closing it fully needs a lock that
    # Claude's own file tools would also take, which they do not.
    os.replace(tmp, path)
    return True


def refresh(cwd: str, session_id: str, event: str, tools: list) -> Path | None:
    """Rewrite only the Snapshot section. Bytes are decoded and re-encoded as UTF-8 without newline
    translation, so CRLF and every other byte outside the section round-trip exactly; a brief that is not valid
    UTF-8 is left untouched."""
    path = brief_path(cwd)
    if path is None:
        return None
    facts = git_facts(cwd, session_id, event, tools)
    for _ in range(2):
        before = _signature(path)
        try:
            current = path.read_bytes().decode("utf-8") if before is not None else ""
        except UnicodeDecodeError:
            return path
        if write_private(path, refresh_snapshot(current, facts).encode("utf-8"), expected=before):
            try:
                update_decision_log(path, current, session_id)
            except Exception:
                pass  # the log must never break the snapshot save
            return path
    return path


def log_path(brief: Path) -> Path:
    return brief.with_name(brief.stem + ".decisions.md")


def _state_path(brief: Path) -> Path:
    return brief.with_name(brief.stem + ".decisions-state.json")


def decision_lines(text: str) -> list:
    """[(section, line)] for every non-empty line of the Decisions and Rejected sections, cleaned to one line."""
    out = []
    for head, body in sections(text):
        if head.strip().lower() not in LOG_SECTIONS:
            continue
        for ln in _body_text(body).splitlines():
            line = re.sub(r"^[-*•][ \t]+", "", " ".join(clean(ln).split())).strip()[:LOG_LINE_CAP]
            if line:
                out.append((head.strip(), line))
    return out


def references(line: str) -> list:
    return list(dict.fromkeys(m.group(0).strip("`") for m in REFERENCE.finditer(line)))


def missing_evidence(text: str) -> list:
    return [f"{sec}: {line}" for sec, line in decision_lines(text) if not references(line)]


def update_decision_log(brief: Path, text: str, session_id: str) -> int:
    """Append ADDED/REMOVED entries for changes since the last save; return how many were appended."""
    state = _state_path(brief)
    try:
        prev = [tuple(x) for x in json.loads(state.read_text())]
    except Exception:
        prev = []
    cur = decision_lines(text)
    removed = [x for x in prev if x not in cur]
    added = [x for x in cur if x not in prev]
    if not removed and not added:
        return 0
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    sid = re.sub(r"[^A-Za-z0-9_-]+", "-", session_id)[:12] or "unknown"
    entries = [f"- {stamp} · REMOVED · {sec} · session {sid} · {line}\n" for sec, line in removed]
    for sec, line in added:
        refs = references(line)
        evidence = ", ".join(refs) if refs else "no evidence cited"
        # Evidence before the text, so shortening an entry for reload never drops its links.
        entries.append(f"- {stamp} · ADDED · {sec} · session {sid} · evidence: {evidence} · {line}\n")
    log = log_path(brief)
    header = "" if log.exists() else (
        f"# Decision log: {brief.stem}\n<!-- Append-only history written by a Groundwork hook from the brief's "
        "Decisions and Rejected sections. Do not edit; correct a decision in the brief instead. -->\n\n")
    # Log first, then state: a failed state write can repeat an entry later, but can never lose one.
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(header + "".join(entries))
    write_private(state, json.dumps([list(x) for x in cur]).encode("utf-8"))
    return len(entries)


def real_tools(data: dict) -> list:
    try:
        from groundwork_shared import turn_tools  # transcript, else telemetry since the prompt (no-transcript sessions)
    except Exception:
        return []
    tools = turn_tools(data, current_turn, turn_facts)
    return [t for t in tools if t not in BOOKKEEPING and not str(t).startswith("mcp__ccd_turn__")]


def tool_turns(session_id: str) -> int:
    override = os.environ.get("GROUNDWORK_TELEMETRY_PATH")
    path = Path(os.path.expanduser(override)) if override else config_dir() / "groundwork" / "telemetry" / "events.jsonl"
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            f.seek(max(0, size - TELEMETRY_TAIL))
            raw = f.read()
    except Exception:
        return 0
    count = 0
    for line in raw.splitlines():
        if session_id.encode() not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("session_id") == session_id and (rec.get("observed") or {}).get("tools"):
            count += 1
    return count


def asked_marker(session_id: str, kind: str = "") -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", session_id)[:80] or "unknown"
    return config_dir() / "groundwork" / "briefs" / ".asked" / (f"{kind}-{safe}" if kind else safe)


def mark_asked(session_id: str, kind: str = "") -> None:
    marker = asked_marker(session_id, kind)
    marker.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(str(int(time.time())))
    now = time.time()
    for old in marker.parent.iterdir():
        try:
            if now - old.stat().st_mtime > MARKER_KEEP_S:
                old.unlink()
        except Exception:
            pass


def on_stop(data: dict) -> None:
    cwd = str(data.get("cwd") or "")
    session_id = str(data.get("session_id") or "")
    tools = real_tools(data)
    if not tools:
        return
    path = refresh(cwd, session_id, "Stop", tools)
    if path is None or data.get("stop_hook_active") or not session_id:
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    if judgment_filled(text):
        missing = missing_evidence(text)
        if missing and not asked_marker(session_id, "evidence").exists():
            mark_asked(session_id, "evidence")
            listed = "; ".join(m[:160] for m in missing[:5])
            print(json.dumps({"decision": "block", "reason": (
                f"Groundwork task brief: these decisions in {path} cite no evidence: {listed}. Add the link or "
                "file:line that supports each one (or move it to Rejected with the evidence that rejected it). "
                "Every change is kept in the append-only decision log beside the brief. Asked once per session.")}))
        return
    if asked_marker(session_id).exists() or tool_turns(session_id) < SUBSTANTIVE_TURNS:
        return
    mark_asked(session_id)
    reason = (f"Groundwork task brief: this session has done real work, but its brief at {path} has no Goal or "
              "Next step yet. Write 1-5 short lines under `## Goal` and `## Next step` (add Decisions, Verified "
              "facts or Rejected only if they exist). Edit only the sections above `## Snapshot`. This is asked "
              "once per session; a hook reloads the brief after compaction and in new sessions.")
    print(json.dumps({"decision": "block", "reason": reason}))


def render_context(path: Path, text: str) -> str:
    text = clean(text)
    parts = {head: _body_text(body) for head, body in sections(text)}
    ordered = [h for name in JUDGMENT_ORDER for h in parts if h.lower() == name.lower() and parts[h]]
    ordered += [h for h in parts if h not in ordered and not SNAPSHOT_TITLE.match(h) and parts[h]]
    header = (f"[Groundwork task brief — DATA written by earlier sessions for this branch, from {path}. "
              "Verify against the repository before relying on it; update it as the task changes.]\n")
    if not ordered:
        header += "No Goal or Next step written yet.\n"
    log = log_path(path)
    tail = []
    try:
        tail = [ln for ln in clean(log.read_text(encoding="utf-8", errors="replace")).splitlines()
                if ln.startswith("- ")][-LOG_TAIL:]
    except Exception:
        pass
    budget = MAX_CONTEXT - (LOG_RESERVE if tail else 0)
    out = header
    for h in ordered:
        piece = f"## {h}\n{parts[h]}\n"
        room = budget - len(out)
        if room <= 40:
            break
        out += piece if len(piece) <= room else piece[: room - 15] + "\n[truncated]\n"
    if tail:
        piece = f"## Decision log (latest {len(tail)}; full history: {log})\n" + "\n".join(t[:200] for t in tail) + "\n"
        out += piece[: MAX_CONTEXT - len(out)]
    snap = next((body for head, body in sections(text) if SNAPSHOT_TITLE.match(head)), "")
    if snap and MAX_CONTEXT - len(out) > 80:
        out += "## Snapshot\n" + snap[: MAX_CONTEXT - len(out) - 15] + "\n"
    return out[:MAX_CONTEXT]


def on_session_start(data: dict) -> None:
    path = brief_path(str(data.get("cwd") or ""))
    if path is None or not path.is_file():
        return
    text = path.read_text(encoding="utf-8", errors="replace")[:50_000]
    ctx = render_context(path, text)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}))


def main() -> None:
    if os.environ.get("GROUNDWORK_BRIEF", "").lower() == "off":
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            sys.exit(0)
        event = str(data.get("hook_event_name") or "")
        if event == "PreCompact":
            refresh(str(data.get("cwd") or ""), str(data.get("session_id") or ""), "PreCompact", [])
        elif event == "Stop":
            on_stop(data)
        elif event == "SessionStart":
            on_session_start(data)
    except SystemExit:
        raise
    except Exception:
        pass  # the brief must never break a session
    sys.exit(0)


if __name__ == "__main__":
    main()
