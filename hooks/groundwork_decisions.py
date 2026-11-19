#!/usr/bin/env python3
"""Groundwork decision records — one Markdown file per task key that keeps the decisions, rejected options, waits
and the owner's own words, enforced by hooks rather than model memory.

A record is `<KEY> - <title> - decisions.md` in a configurable folder (`decision_records` in
~/.claude/groundwork/config.json: work_dir, personal_dir, work_roots; GROUNDWORK_DECISIONS_DIR overrides both
folders). Frontmatter: task_id, title, status (open/waiting/closed), waiting_on, waiting_since, jira, repos,
task_note, last_updated. Sections: Current state · Decisions (D-n) · Rejected (R-n, do not re-propose) · Waiting on
· Standing rules (S-n) · Owner messages (raw, auto-captured, unreviewed). D-, R- and S- entries are append-only.

The active task key of a session is a key in the branch name, else the latest key a prompt named as work.

Hook events (registered directly):
  UserPromptSubmit  a prompt that makes a key active loads its record (or says it has none)
  SessionStart      load the active key's record (startup, resume, clear, compact)
  PreCompact        copy every owner prompt in the transcript into Owner messages (secret-shaped text redacted),
                    creating the record when the key has none
  Stop              add the latest owner prompt; block once per stop chain when the key has no record, or when the
                    reply ends waiting on someone and Waiting on is empty
Per tool call (called from groundwork_task_gate.py, which already runs on every PreToolUse/PostToolUse):
  pre_tool          ask the owner before Claude writes a record entry; deny edits that change an existing entry;
                    deny push, PR, Jira, email and chat actions unless the record is newer than the owner's last
                    message
  post_tool         stamp last_updated after Claude's approved edit; close the record on "Good for review"

CLI: groundwork decision create|add|state|waiting|close|show|path|list (see --help).
Fail-open: unreadable input, config or transcript means no gate. GROUNDWORK_DECISIONS=off disables everything.
Not a sandbox: a program such as Python writing a record is not inspected.
"""
import argparse
import calendar
import contextlib
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import groundwork_tasks as gt
except Exception:  # partial install
    gt = None

DEFAULTS = {
    "work_dir": "~/SectigoSRE/CloudOps-Knowledge/Decisions",
    "personal_dir": "~/Documents/Obsidian/Personal/Decisions",
    "work_roots": ["~/SectigoSRE"],
}
SUFFIX = " - decisions.md"
FRONT_KEYS = ("task_id", "title", "status", "waiting_on", "waiting_since", "jira", "repos", "task_note",
              "last_updated")
STATUSES = ("open", "waiting", "closed")
SECTIONS = {  # canonical name -> heading written in new records (matched by prefix, case-insensitive)
    "Current state": "Current state",
    "Decisions": "Decisions",
    "Rejected": "Rejected (do not re-propose)",
    "Waiting on": "Waiting on",
    "Standing rules": "Standing rules",
    "Owner messages": "Owner messages (raw, auto-captured, unreviewed)",
}
ENTRY_KINDS = {"decision": ("Decisions", "D"), "rejected": ("Rejected", "R"), "rule": ("Standing rules", "S")}
ENTRY_LINE = re.compile(r"^- ([DRS])-(\d+)\b.*$", re.MULTILINE)
HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)
CAPTURE_TAIL = 8 * 1024 * 1024
STOP_TAIL = 1024 * 1024
NAV_TAIL = 2 * 1024 * 1024
MESSAGE_CAP = 20_000
CONTEXT_CAP = 3000
REASON_CAP = 1800
CAPTURED_KEEP = 2000
CAPTURE_SLACK_S = 10  # the activating prompt is stamped just before its UserPromptSubmit hook runs
STRIP_CATEGORIES = {"Cc", "Cf", "Zl", "Zp"}

# A key in a branch name: `feat/COR-12850-fix`, `cor-12850`. The suffix must end the key, so `records-6172a6`
# is not one; common branch words are not projects.
BRANCH_KEY = re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9]{1,9}-\d{1,7})(?=$|[-_/.])")
BRANCH_WORDS = {"FIX", "FEAT", "FEATURE", "BUG", "BUGFIX", "HOTFIX", "RELEASE", "CHORE", "DOCS", "TEST", "TESTS",
                "PR", "ISSUE", "WIP", "DEPS", "REFACTOR", "BUILD", "CI", "PERF", "STYLE", "REVERT", "SPIKE",
                "EXPERIMENT", "DRAFT", "TMP", "TEMP", "BACKUP", "OLD", "NEW", "VERSION", "STEP", "PART", "PHASE"}

# A reply that ends waiting on someone other than the owner. Heuristic; the tests pin behaviour, not the lists.
_NOT_OWNER = r"(?!(?:you|your|yours|the owner|owner|me|us)\b)"
WAITING = [re.compile(p, re.IGNORECASE) for p in (
    r"\b(?:waiting|wait)\s+(?:on|for)\s+" + _NOT_OWNER + r"[^.\n]{1,80}?\bto\s+(?:reply|respond|confirm|approve|"
    r"answer|get back|grant|provide|share|decide|sign off|review)\b",
    r"\b(?:waiting|wait)\s+(?:on|for)\s+(?:a\s+|an\s+|the\s+)?(?:reply|response|answer|approval|confirmation|"
    r"sign-?off|decision|input|feedback)\s+from\s+" + _NOT_OWNER,
    r"\b(?:waiting|wait)\s+(?:on|for)\s+(?:the\s+)?(?:[\w-]+\s+){0,2}(?:team|teams|dba|dbas|admins?|vendor|"
    r"customer|support|reviewers?|approvers?|manager|lead|on-?call)\b",
    r"\b(?:pending|awaiting)\s+(?:a\s+|an\s+|the\s+)?(?:reply|response|answer|approval|confirmation|sign-?off|"
    r"decision|input|feedback|review)\s+from\s+" + _NOT_OWNER,
    r"\bblocked\s+(?:on|until)\s+" + _NOT_OWNER + r"[^.\n]{1,60}?\b(?:replies|responds|confirms|approves|answers)\b",
)]

GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
GH_OUTWARD = {("pr", "create"), ("pr", "new"), ("pr", "edit"), ("pr", "merge"), ("pr", "comment"), ("pr", "review"),
              ("pr", "close"), ("pr", "ready"), ("issue", "create"), ("issue", "comment"), ("issue", "edit"),
              ("issue", "close"), ("release", "create")}
JIRA_CLIS = {"jira", "acli", "jira-cli"}
JIRA_READ_WORDS = {"view", "list", "ls", "get", "search", "me", "version", "help", "--help", "-h", "show", "open"}
MAIL_CLIS = {"mail", "mailx", "sendmail", "mutt", "msmtp"}
WRITE_VERBS = {"create", "update", "edit", "add", "transition", "comment", "delete", "assign", "move", "link", "log",
               "send", "post", "reply", "forward", "schedule", "publish", "set"}
BROWSER_MUTATING = {"left_click", "right_click", "double_click", "triple_click", "type", "key", "left_click_drag"}
JIRA_HOST = re.compile(r"(?:^|[/.])[\w-]+\.atlassian\.net\b|\bjira\.", re.IGNORECASE)
READERS = {"cat", "less", "more", "head", "tail", "grep", "rg", "ls", "wc", "stat", "file", "diff", "jq"}


# ---------------------------------------------------------------------------------------------- basics

def enabled() -> bool:
    return os.environ.get("GROUNDWORK_DECISIONS", "").lower() != "off"


def config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))


def state_dir() -> Path:
    return config_dir() / "groundwork" / "state" / "decisions"


def decision_cli() -> str:
    """How Claude should invoke this CLI: the installed file's absolute path (always resolvable, unlike PATH)."""
    return f"python3 {Path(__file__).resolve()}"


def clean(text: str) -> str:
    return "".join(ch for ch in str(text) if ch in "\n\t" or unicodedata.category(ch) not in STRIP_CATEGORIES)


def one_line(text: str, cap: int = 600) -> str:
    return " ".join(clean(text).split())[:cap]


def utc_now() -> str:
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + f".{int((t % 1) * 1000):03d}Z"


def local_stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M %Z", time.localtime())


def parse_ts(value) -> float | None:
    """Epoch seconds for an ISO-8601 UTC stamp (`2026-11-19T16:32:01.123Z`); None when unreadable."""
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?Z$", str(value or "").strip())
    if not m:
        return None
    try:
        return calendar.timegm(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")) + float(m.group(2) or 0)
    except ValueError:
        return None


def settings() -> dict:
    """decision_records from Groundwork's config.json merged over DEFAULTS; unreadable config -> DEFAULTS."""
    out = dict(DEFAULTS)
    try:
        cfg = json.loads((config_dir() / "groundwork" / "config.json").read_text())
        dr = cfg.get("decision_records") if isinstance(cfg, dict) else None
        if isinstance(dr, dict):
            for k in ("work_dir", "personal_dir"):
                if isinstance(dr.get(k), str) and dr[k].strip():
                    out[k] = dr[k]
            if isinstance(dr.get("work_roots"), list) and all(isinstance(r, str) for r in dr["work_roots"]):
                out["work_roots"] = dr["work_roots"]
    except Exception:
        pass
    return out


def _expand(p: str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.path.expandvars(p))))


def folders() -> list[Path]:
    override = os.environ.get("GROUNDWORK_DECISIONS_DIR")
    if override:
        return [_expand(override)]
    s = settings()
    return list(dict.fromkeys([_expand(s["work_dir"]), _expand(s["personal_dir"])]))


def folder_for(cwd: str, personal: bool | None = None) -> Path:
    override = os.environ.get("GROUNDWORK_DECISIONS_DIR")
    if override:
        return _expand(override)
    s = settings()
    if personal is None:
        real = os.path.realpath(cwd or os.getcwd())
        personal = not any(real == os.path.realpath(str(_expand(r))) or
                           real.startswith(os.path.realpath(str(_expand(r))) + os.sep) for r in s["work_roots"])
    return _expand(s["personal_dir"] if personal else s["work_dir"])


def valid_key(key: str) -> bool:
    return bool(re.match(r"^[A-Z][A-Z0-9]{1,9}-\d{1,7}$", key or ""))


def safe_title(title: str) -> str:
    t = re.sub(r"[\\/:*?\"<>|#^\[\]]+", "-", one_line(title, 200))
    t = re.sub(r"\s+-\s+", " – ", t).strip(" .-")  # " - " separates name parts
    return t[:80] or "untitled"


def find_record(key: str) -> Path | None:
    if not valid_key(key):
        return None
    for d in folders():
        try:
            hits = sorted(p for p in d.glob(f"{key} - *{SUFFIX}") if p.is_file())
        except OSError:
            continue
        if hits:
            return hits[0]
    return None


def is_record_path(path: str) -> bool:
    if not path or not str(path).endswith(SUFFIX):
        return False
    real = os.path.realpath(os.path.expanduser(str(path)))
    if not valid_key(os.path.basename(real).split(" - ", 1)[0]):
        return False
    return any(real.startswith(os.path.realpath(str(d)) + os.sep) for d in folders())


# ---------------------------------------------------------------------------------------------- record format

def dump_meta(meta: dict) -> str:
    lines = ["---"]
    for k in FRONT_KEYS:
        v = meta.get(k, [] if k == "repos" else "")
        lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    return "\n".join(lines) + "\n---\n"


def parse(text: str) -> tuple[dict, str]:
    """(frontmatter, body). Values are JSON (as written by dump_meta) or bare strings."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    meta = {}
    for ln in text[4:end].splitlines():
        k, sep, v = ln.partition(":")
        if not sep:
            continue
        v = v.strip()
        try:
            meta[k.strip()] = json.loads(v) if v else ""
        except ValueError:
            meta[k.strip()] = v.strip("'\"")
    return meta, text[end + 5:]


def new_record(key: str, title: str, meta: dict) -> str:
    body = (f"# {key} - {title} - decisions\n\n"
            "<!-- Groundwork decision record. Entries in Decisions, Rejected and Standing rules are append-only: "
            "supersede an entry with a new one, never edit or delete it. Claude writes an entry only after the owner "
            "approves it. Owner messages are copied by a hook, raw and unreviewed. -->\n\n")
    body += "".join(f"## {h}\n\n" for h in SECTIONS.values())
    return dump_meta(meta) + "\n" + body


def _canonical(heading: str) -> str | None:
    low = heading.strip().lower()
    for name in SECTIONS:
        if low.startswith(name.lower()):
            return name
    return None


def section_span(text: str, name: str) -> tuple[int, int] | None:
    """(start, end) of the section's body: from after its heading line to the next `## ` heading."""
    heads = list(HEADING.finditer(text))
    for i, m in enumerate(heads):
        if _canonical(m.group(1)) == name:
            start = m.end() + 1 if m.end() < len(text) else m.end()
            return start, heads[i + 1].start() if i + 1 < len(heads) else len(text)
    return None


def section_text(text: str, name: str) -> str:
    span = section_span(text, name)
    if not span:
        return ""
    body = text[span[0]:span[1]]
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    return "\n".join(ln for ln in body.splitlines() if ln.strip()).strip()


def _ensure_section(text: str, name: str) -> str:
    if section_span(text, name):
        return text
    sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return text + sep + f"## {SECTIONS[name]}\n\n"


def append_to_section(text: str, name: str, block: str) -> str:
    text = _ensure_section(text, name)
    s, e = section_span(text, name)
    body = text[s:e].rstrip("\n")
    lead = body + "\n" if body.strip() else ("\n" if not body else body + "\n")
    return text[:s] + lead + block.rstrip("\n") + "\n\n" + text[e:].lstrip("\n")


def replace_section(text: str, name: str, content: str) -> str:
    text = _ensure_section(text, name)
    s, e = section_span(text, name)
    new = ("\n" + content.strip() + "\n\n") if content.strip() else "\n"
    return text[:s] + new + text[e:].lstrip("\n")


def set_meta(text: str, **updates) -> str:
    meta, body = parse(text)
    meta.update(updates)
    return dump_meta(meta) + body


def entry_lines(text: str) -> set[str]:
    out = set()
    for name in ("Decisions", "Rejected", "Standing rules"):
        span = section_span(text, name)
        if span:
            out.update(m.group(0).rstrip() for m in ENTRY_LINE.finditer(text[span[0]:span[1]]))
    return out


def next_id(text: str, prefix: str) -> str:
    nums = [int(m.group(2)) for m in ENTRY_LINE.finditer(text) if m.group(1) == prefix]
    return f"{prefix}-{max(nums, default=0) + 1}"


# ---------------------------------------------------------------------------------------------- file I/O

@contextlib.contextmanager
def locked(key: str):
    path = state_dir() / "locks" / f"{key}.lock"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        except Exception:
            pass
        yield
    finally:
        os.close(fd)


def write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="replace")


def update(key: str, fn) -> Path | None:
    """Read-modify-write the key's record under its lock; fn(text) returns the new text (or None for no change)."""
    with locked(key):
        path = find_record(key)
        if path is None:
            return None
        text = read(path)
        new = fn(text)
        if new is not None and new != text:
            write_private(path, new)
        return path


def create(key: str, title: str, cwd: str = "", jira: str = "", task_note: str = "",
           personal: bool | None = None) -> tuple[Path, bool]:
    """(path, created). An existing record for the key is returned untouched."""
    with locked(key):
        existing = find_record(key)
        if existing:
            return existing, False
        redact = redactor()
        title = safe_title(redact(clean(title))[0] if redact else key)  # no redactor: never a raw title in the name
        jira = one_line(redact(clean(jira))[0], 300) if redact and jira else ""
        root = (gt.repo_root(cwd) if gt and cwd else None) or ""
        note_link = ""
        if task_note:
            note_link = f"[[{Path(task_note).stem}]]"
        meta = {"task_id": key, "title": title, "status": "open", "waiting_on": "", "waiting_since": "",
                "jira": jira, "repos": [root] if root else [], "task_note": note_link, "last_updated": utc_now()}
        path = folder_for(cwd, personal) / f"{key} - {title}{SUFFIX}"
        write_private(path, new_record(key, title, meta))
    if task_note:
        link_task_note(Path(os.path.expanduser(task_note)), path)
    return path, True


def link_task_note(note: Path, record: Path) -> bool:
    """Add `- Decision record: [[<record>]]` to an existing Markdown task note once."""
    if note.suffix != ".md" or not note.is_file():
        return False
    link = f"[[{record.stem}]]"
    text = read(note)
    if link in text:
        return False
    sep = "" if text.endswith("\n") else "\n"
    with open(note, "a", encoding="utf-8") as f:
        f.write(f"{sep}\n- Decision record: {link}\n")
    return True


# ---------------------------------------------------------------------------------------------- active key

def _state_file(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", session_id)[:80] or "unknown"
    return state_dir() / "sessions" / f"{safe}.json"


def session_state(session_id: str) -> dict:
    try:
        d = json.loads(_state_file(session_id).read_text())
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_session_state(session_id: str, data: dict) -> None:
    if not session_id:
        return
    path = _state_file(session_id)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(data))
    os.replace(tmp, path)
    now = time.time()
    for old in path.parent.glob("*.json"):
        try:
            if now - old.stat().st_mtime > 30 * 86400:
                old.unlink()
        except OSError:
            pass


def branch_key(cwd: str) -> str | None:
    if not gt or not cwd:
        return None
    branch = (gt.git(cwd, "rev-parse", "--abbrev-ref", "HEAD") or "").strip()
    for m in BRANCH_KEY.finditer(branch):
        raw = m.group(1)
        key = raw.upper()
        prefix = key.split("-")[0]
        if prefix in BRANCH_WORDS or prefix in gt.NOT_TICKET_PREFIXES or not valid_key(key):
            continue
        # Upper-case as written (`feat/COR-12850-x`) is a ticket key. Lower-case (`bump-node-18`, `feat/k8s-1`) counts
        # only when the key is already known: it has a decision record or a task in this repository's ledger.
        if raw.split("-")[0].isupper() or find_record(key) or _ledger_has(cwd, key):
            return key
    return None


def _ledger_has(cwd: str, key: str) -> bool:
    try:
        root = gt.repo_root(cwd)
        return bool(root and gt.load_task(root, key))
    except Exception:
        return False


def prompt_key(prompt: str) -> str | None:
    """The key a prompt names as work: it heads the prompt or a clause, or the prompt is engineering work, or it is
    the /decision command. A question that only mentions a key returns None."""
    if not gt or not prompt:
        return None
    text = prompt.strip()
    keys = gt.find_keys(text[:4000])
    if not keys:
        return None
    if text.startswith("/decision"):
        return keys[0]
    work = [k for k in keys if gt.work_key(text, k)]
    if work:
        return work[0]
    cls = gt.classify(text)
    return keys[0] if cls and cls.get("kind") == "task" else None


def active_key(cwd: str, session_id: str) -> str | None:
    return branch_key(cwd) or session_state(session_id).get("active") or None


def capture_since(cwd: str, session_id: str, key: str) -> float | None:
    """When a prompt (not the branch) made `key` active: the time it did, else None (capture everything)."""
    if branch_key(cwd) == key:
        return None
    v = (session_state(session_id).get("since") or {}).get(key)
    return float(v) if isinstance(v, (int, float)) else None


def active_record_path(cwd: str, session_id: str) -> Path | None:
    """Used by groundwork_brief.py to link the record from the branch brief."""
    if not enabled():
        return None
    key = active_key(cwd, session_id)
    return find_record(key) if key else None


# ---------------------------------------------------------------------------------------------- transcript

def _tail_lines(path: str, limit: int) -> list:
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - limit))
            raw = f.read()
    except OSError:
        return []
    lines = raw.split(b"\n")
    if size > limit:
        lines = lines[1:]
    out = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        if isinstance(e, dict):
            out.append(e)
    return out


def _command_text(text: str) -> str:
    """A slash command as the transcript stores it (`<command-name>/x</command-name>…<command-args>a</command-args>`)."""
    name = re.search(r"<command-name>(.*?)</command-name>", text, re.DOTALL)
    args = re.search(r"<command-args>(.*?)</command-args>", text, re.DOTALL)
    return " ".join(x for x in ((name.group(1).strip() if name else ""), (args.group(1).strip() if args else "")) if x)


def owner_text(entry: dict) -> str | None:
    """The text of a prompt the owner typed, or None: tool results, meta entries, compaction summaries, sidechains and
    system envelopes (`<task-notification>` …) are not the owner's words."""
    if entry.get("type") != "user" or entry.get("isSidechain") or entry.get("isMeta") or entry.get("isCompactSummary"):
        return None
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return None
        text = "\n".join(str(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    else:
        return None
    stripped = text.strip()
    if stripped.startswith("<command-"):
        stripped = _command_text(stripped)
    elif stripped.startswith("<"):
        return None
    return stripped or None


def owner_messages(transcript_path: str, limit: int = CAPTURE_TAIL) -> list:
    """[(id, timestamp, text)] of owner prompts in the transcript tail, oldest first."""
    out = []
    for e in _tail_lines(transcript_path, limit) if transcript_path else []:
        text = owner_text(e)
        if text is None:
            continue
        ts = str(e.get("timestamp") or "")
        mid = str(e.get("uuid") or "") or hashlib.sha256((ts + "\0" + text).encode()).hexdigest()[:32]
        out.append((mid, ts, text))
    return out


def owner_last_ts(transcript_path: str, session_id: str) -> float | None:
    msgs = owner_messages(transcript_path, STOP_TAIL) if transcript_path and os.path.isfile(transcript_path) else []
    stamps = [t for t in (parse_ts(ts) for _mid, ts, _t in msgs) if t is not None]
    if stamps:
        return max(stamps)
    try:  # no transcript (unsaved sessions): the reply check's prompt-time marker
        from groundwork_shared import _turn_marker
        return parse_ts(json.loads(_turn_marker(session_id).read_text()).get("ts"))
    except Exception:
        return None


def redactor():
    """The copilot redactor (scripts/groundwork_copilot.py), installed in groundwork/bin; None when unavailable."""
    for d in (config_dir() / "groundwork" / "bin", Path(__file__).resolve().parent.parent / "scripts"):
        if (d / "groundwork_copilot.py").is_file() and str(d) not in sys.path:
            sys.path.append(str(d))
    try:
        from groundwork_copilot import redact
        return redact
    except Exception:
        return None


def scrub(text: str, cap: int) -> str:
    """One line of Claude-supplied record text with secret-shaped values redacted. Refuses (SystemExit) when the
    redactor is unavailable: unredacted text never reaches a notes folder."""
    redact = redactor()
    if redact is None:
        raise SystemExit("refusing to write: the secret redactor (groundwork_copilot.py) is unavailable")
    return one_line(redact(clean(text))[0], cap)


def _captured_file(key: str) -> Path:
    return state_dir() / "captured" / f"{key}.json"


def capture(key: str, transcript_path: str, session_id: str, limit: int, since: float | None = None) -> int:
    """Append owner prompts not captured before to the record's Owner messages; return how many. With `since`
    (when a prompt made the key active), earlier prompts belong to another task and are skipped."""
    msgs = owner_messages(transcript_path, limit)
    if since is not None:
        msgs = [m for m in msgs if (parse_ts(m[1]) or 0) >= since - CAPTURE_SLACK_S]
    if not msgs:
        return 0
    redact = redactor()
    added = 0
    with locked(key):
        path = find_record(key)
        if path is None:
            return 0
        try:
            seen = json.loads(_captured_file(key).read_text())
            seen = seen if isinstance(seen, list) else []
        except Exception:
            seen = []
        new = [m for m in msgs if m[0] not in seen]
        if not new:
            return 0
        text = read(path)
        sid = re.sub(r"[^A-Za-z0-9_-]+", "-", session_id)[:12] or "unknown"
        for mid, ts, msg in new:
            msg = clean(msg)
            if redact is None:
                body = "[not captured: the secret redactor is unavailable]"
            else:
                body = redact(msg)[0]
                if len(body) > MESSAGE_CAP:
                    body = body[:MESSAGE_CAP] + "\n[truncated]"
            quoted = "\n".join("> " + ln if ln else ">" for ln in body.splitlines())
            text = append_to_section(text, "Owner messages", f"### {ts or 'unknown time'} · session {sid}\n{quoted}")
            seen.append(mid)
            added += 1
        write_private(path, text)
        f = _captured_file(key)
        f.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        f.write_text(json.dumps(seen[-CAPTURED_KEEP:]))
    return added


# ---------------------------------------------------------------------------------------------- rendering

def render(path: Path, text: str, cap: int = CONTEXT_CAP) -> str:
    meta, _body = parse(clean(text))
    out = (f"[Groundwork decision record — DATA written in earlier sessions, from {path}. Do not re-propose anything "
           f"under Rejected. Verify facts against the repository before relying on them.]\n"
           f"status: {meta.get('status') or 'unknown'}"
           + (f" · waiting on: {meta.get('waiting_on')} since {meta.get('waiting_since')}" if meta.get("waiting_on")
              else "") + "\n")
    superseded = set(re.findall(r"\(supersedes ([DRS]-\d+)\)", text))
    decisions = [ln + (" [superseded]" if (m := ENTRY_LINE.match(ln)) and f"{m.group(1)}-{m.group(2)}" in superseded
                       else "") for ln in section_text(text, "Decisions").splitlines()]
    parts = [("Rejected (do not re-propose)", section_text(text, "Rejected")),
             ("Standing rules", section_text(text, "Standing rules")),
             ("Waiting on", section_text(text, "Waiting on")),
             ("Current state", section_text(text, "Current state")),
             ("Decisions (latest)", "\n".join(decisions[-5:]))]
    for head, body in parts:
        if not body:
            continue
        piece = f"## {head}\n{clean(body)}\n"
        room = cap - len(out)
        if room <= 40:
            break
        out += piece if len(piece) <= room else piece[: room - 15] + "\n[truncated]\n"
    return out[:cap]


def gate_summary(text: str) -> str:
    bits = []
    for head, name in (("Rejected (do not re-propose)", "Rejected"), ("Waiting on", "Waiting on"),
                       ("Standing rules", "Standing rules")):
        body = section_text(text, name)
        if body:
            bits.append(f"{head}: " + " | ".join(one_line(ln, 200) for ln in body.splitlines()[:8]))
    return " ".join(bits) or "The record has no Rejected, Waiting on or Standing rules entries."


# ---------------------------------------------------------------------------------------------- hook events

def emit(obj) -> None:
    print(json.dumps(obj))


def context(event: str, text: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


def _missing_hint(key: str) -> str:
    return (f'create it now (no approval needed for the empty record): {decision_cli()} create {key} --title "<short '
            f'title>". Then draft each decision, rejected option or standing rule, show the owner the exact text, '
            f'and write it only after the owner approves: {decision_cli()} add {key} decision|rejected|rule "<text>".')


def on_prompt(data: dict) -> None:
    sid = str(data.get("session_id") or "")
    key = prompt_key(str(data.get("prompt") or ""))
    if not key or branch_key(str(data.get("cwd") or "")):
        return
    st = session_state(sid)
    if st.get("active") == key:
        return
    st["active"] = key
    st["since"] = {**(st.get("since") or {}), key: time.time()}
    st["keys"] = list(dict.fromkeys((st.get("keys") or []) + [key]))[-20:]
    save_session_state(sid, st)
    path = find_record(key)
    if path:
        context("UserPromptSubmit", render(path, read(path)))
    else:
        context("UserPromptSubmit", f"[Groundwork] {key} has no decision record yet; {_missing_hint(key)}")


def on_session_start(data: dict) -> None:
    key = active_key(str(data.get("cwd") or ""), str(data.get("session_id") or ""))
    path = find_record(key) if key else None
    if path:
        context("SessionStart", render(path, read(path)))
    elif key:
        context("SessionStart", f"[Groundwork] {key} has no decision record yet; {_missing_hint(key)}")


def _default_title(cwd: str, key: str) -> str:
    try:
        root = gt.repo_root(cwd) if gt else None
        task = gt.load_task(root, key) if root else None
        if task and task.get("title"):
            return str(task["title"])[:80]
    except Exception:
        pass
    branch = (gt.git(cwd, "rev-parse", "--abbrev-ref", "HEAD") or "").strip() if gt and cwd else ""
    return branch.rsplit("/", 1)[-1] or "untitled"


def on_precompact(data: dict) -> None:
    cwd, sid = str(data.get("cwd") or ""), str(data.get("session_id") or "")
    key = active_key(cwd, sid)
    if not key:
        return
    if find_record(key) is None:
        create(key, _default_title(cwd, key), cwd)
    capture(key, str(data.get("transcript_path") or ""), sid, CAPTURE_TAIL, capture_since(cwd, sid, key))


def waiting_phrase(text: str) -> str | None:
    tail = (text or "")[-3000:]
    for rx in WAITING:
        m = rx.search(tail)
        if m:
            return m.group(0)
    return None


def block(reason: str) -> None:
    emit({"decision": "block", "reason": reason})


def on_stop(data: dict) -> None:
    cwd, sid = str(data.get("cwd") or ""), str(data.get("session_id") or "")
    key = active_key(cwd, sid)
    if not key:
        return
    path = find_record(key)
    if path is not None:
        try:
            capture(key, str(data.get("transcript_path") or ""), sid, STOP_TAIL, capture_since(cwd, sid, key))
        except Exception:
            pass  # capture must never break the gate
    if data.get("stop_hook_active"):
        return
    if path is None:
        block(f"Groundwork decision record: this session works on {key}, which has no decision record. "
              f"{_missing_hint(key)[0].upper() + _missing_hint(key)[1:]}")
        return
    text = read(path)
    meta, _ = parse(text)
    if meta.get("status") == "closed":
        return
    said = waiting_phrase(str(data.get("last_assistant_message") or ""))
    if (said or meta.get("status") == "waiting") and not section_text(text, "Waiting on"):
        why = f'your reply says "{one_line(said, 120)}"' if said else "the record's status is waiting"
        block(f"Groundwork decision record: {why}, but Waiting on in {path} is empty. Record who or what {key} is "
              f'waiting on: {decision_cli()} waiting {key} "<who> — <what is needed>". If nothing is pending on '
              f"someone else, say so in one line instead.")


# ---------------------------------------------------------------------------------------------- per tool call

def _git_words(argv: list[str], i: int) -> list[str]:
    words, n, rest = [], i + 1, argv
    while n < len(rest):
        w = rest[n]
        if w in GIT_OPTS_WITH_VALUE:
            n += 2
            continue
        if not w.startswith("-"):
            words.append(w)
        n += 1
    return words


def outward_command(argv: list[str]) -> str | None:
    """A label when a simple command publishes, messages or changes a ticket; None otherwise."""
    names = [os.path.basename(a) for a in argv]
    for i, name in enumerate(names):
        if name == "git":
            words = _git_words(argv, i)
            if words[:1] == ["push"]:
                return "git push"
            return None
        if name == "gh":
            words = [w for w in argv[i + 1:] if not w.startswith("-")]
            if tuple(words[:2]) in GH_OUTWARD:
                return "gh " + " ".join(words[:2])
            return None
        if name in JIRA_CLIS:
            words = [w for w in argv[i + 1:]]
            if words and not (set(w.lower() for w in words) & JIRA_READ_WORDS):
                return f"{name} (Jira)"
            return None
        if name in MAIL_CLIS:
            return f"{name} (email)"
    return None


def outward_mcp(tool: str) -> str | None:
    if not tool.startswith("mcp__"):
        return None
    parts = tool.split("__")
    server, action = ("__".join(parts[1:-1]).lower(), parts[-1]) if len(parts) >= 3 else ("", "")
    words = {w.lower() for w in re.split(r"[_\-]+|(?<=[a-z0-9])(?=[A-Z])", action) if w}
    if not words & WRITE_VERBS:
        return None
    if "atlassian" in server or "jira" in server or "jira" in action.lower():
        return "Jira (" + action + ")"
    low = action.lower()
    if "draft" in low or "label" in low or "spam" in low or "trash" in low:
        return None
    if re.search(r"gmail|mail|outlook", server) and re.search(r"send|reply|forward", low):
        return "email (" + action + ")"
    if re.search(r"slack|teams|chat|discord", server) and re.search(r"send|post|reply|schedule", low):
        return "chat (" + action + ")"
    if re.search(r"^[0-9a-f-]{36}$", server) and re.search(r"(?:^|_)(send_message|reply|forward)$", low):
        return "email (" + action + ")"  # connector servers named by UUID (the Gmail connector's tools)
    return None


def _browser_tool(tool: str) -> bool:
    return bool(re.match(r"^mcp__(?:Claude_Browser|claude-in-chrome|remote-devices__Claude_Browser)__", tool))


def _browser_mutating(tool: str, ti: dict) -> bool:
    action = tool.rsplit("__", 1)[-1]
    if action == "computer":
        return str(ti.get("action") or "") in BROWSER_MUTATING
    if action == "form_input":
        return True
    if action == "browser_batch":
        return any(isinstance(a, dict) and (a.get("name") == "form_input" or (
            a.get("name") == "computer" and str((a.get("input") or {}).get("action") or "") in BROWSER_MUTATING))
            for a in (ti.get("actions") or []))
    return False


def last_navigation(transcript_path: str) -> str:
    """The URL of the session's latest browser navigation (navigate / preview_start / tabs_create input)."""
    url = ""
    for e in _tail_lines(transcript_path, NAV_TAIL) if transcript_path else []:
        if e.get("type") != "assistant":
            continue
        for b in (e.get("message") or {}).get("content") or []:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            name, inp = str(b.get("name") or ""), b.get("input") if isinstance(b.get("input"), dict) else {}
            if _browser_tool(name) and name.rsplit("__", 1)[-1] in ("navigate", "preview_start", "browser_batch"):
                if isinstance(inp.get("url"), str):
                    url = inp["url"]
                for a in inp.get("actions") or []:
                    if isinstance(a, dict) and a.get("name") == "navigate" and isinstance((a.get("input") or {}).get("url"), str):
                        url = a["input"]["url"]
    return url


def jira_browser_action(tool: str, ti: dict, transcript_path: str) -> bool:
    if not (_browser_tool(tool) and _browser_mutating(tool, ti)):
        return False
    url = next((a["input"]["url"] for a in reversed(ti.get("actions") or [])
                if isinstance(a, dict) and a.get("name") == "navigate" and isinstance((a.get("input") or {}).get("url"), str)),
               "") if tool.endswith("__browser_batch") else ""
    return bool(JIRA_HOST.search(url or last_navigation(transcript_path)))


def _record_write_target(ti: dict) -> str:
    return str(ti.get("file_path") or ti.get("notebook_path") or "")


def _apply_edit(current: str, tool: str, ti: dict) -> str | None:
    def one(text, old, new, all_):
        if not old or old not in text:
            return None
        return text.replace(old, new) if all_ else text.replace(old, new, 1)
    if tool == "Write":
        return str(ti.get("content") or "")
    if tool == "Edit":
        return one(current, str(ti.get("old_string") or ""), str(ti.get("new_string") or ""), bool(ti.get("replace_all")))
    if tool == "MultiEdit":
        text = current
        for ed in ti.get("edits") or []:
            if not isinstance(ed, dict):
                return None
            text = one(text, str(ed.get("old_string") or ""), str(ed.get("new_string") or ""), bool(ed.get("replace_all")))
            if text is None:
                return None
        return text
    return None


def _cli_call(argv: list[str]) -> list[str] | None:
    """The arguments after `decision` for `groundwork decision …` or `python3 …/groundwork_decisions.py …`."""
    names = [os.path.basename(a) for a in argv]
    for i, n in enumerate(names):
        if n == "groundwork" and i + 1 < len(argv) and argv[i + 1] == "decision":
            return argv[i + 2:]
        if n == "groundwork_decisions.py":
            return argv[i + 1:]
    return None


def _owner_fresh(key: str, path: Path, transcript_path: str, session_id: str) -> bool:
    meta, _ = parse(read(path))
    updated = parse_ts(meta.get("last_updated"))
    last = owner_last_ts(transcript_path, session_id)
    if last is None:
        return True  # unknown: fail-open
    return updated is not None and updated > last


def pre_tool(data: dict, split_segments=None) -> tuple[str, str] | None:
    """("ask"|"deny", reason) for a tool call the decision records gate, else None."""
    if not enabled():
        return None
    tool = str(data.get("tool_name") or "")
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    cwd, sid = str(data.get("cwd") or os.getcwd()), str(data.get("session_id") or "")
    transcript = str(data.get("transcript_path") or "")

    # 1. Claude's own writes to a record: append-only check, then the owner's approval.
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit") and is_record_path(_record_write_target(ti)):
        target = Path(os.path.expanduser(_record_write_target(ti)))
        if target.is_file():
            current = read(target)
            after = _apply_edit(current, tool, ti)
            if after is not None:
                gone = sorted(entry_lines(current) - entry_lines(after))
                if gone:
                    key = target.name.split(" - ", 1)[0]
                    return ("deny", "Groundwork decision record: Decisions, Rejected and Standing rules entries are "
                            f"append-only; this edit changes or removes {one_line(gone[0], 160)}. Supersede it with "
                            f'a new approved entry instead: {decision_cli()} add {key} decision "<text>" '
                            "--supersedes <id>.")
        return ("ask", "this writes a decision record entry. Approve only the exact text the owner agreed to.")

    outward = asking = None
    if tool in ("Bash", "Monitor") and isinstance(ti.get("command"), str):
        segs = split_segments(ti["command"]) if split_segments else None
        for s in segs or []:
            argv = s.get("argv") or []
            cli = _cli_call(argv)
            if cli is not None and cli[:1] == ["add"]:
                asking = asking or "this adds a decision record entry. Approve only the exact text the owner agreed to."
            elif any(t.endswith(SUFFIX) or is_record_path(t) for t in s.get("targets") or []):
                asking = asking or "this command writes a decision record directly."
            elif cli is None and argv and os.path.basename(argv[0]) not in READERS and any(
                    is_record_path(a) for a in argv):
                asking = asking or "this command may change a decision record."
            outward = outward or outward_command(argv)
    elif tool.startswith("mcp__"):
        outward = outward_mcp(tool) or ("Jira (browser)" if jira_browser_action(tool, ti, transcript) else None)
    verdict = outward_verdict(outward, cwd, sid, transcript) if outward else None
    return verdict or (("ask", asking) if asking else None)


def outward_verdict(outward: str, cwd: str, sid: str, transcript: str) -> tuple[str, str] | None:
    """Outward actions need a record that is newer than the owner's last message."""
    key = active_key(cwd, sid)
    if not key:
        return None
    path = find_record(key)
    if path is None:
        return ("deny", f"Groundwork decision record: {outward} is blocked because {key} has no decision record. "
                + _missing_hint(key)[0].upper() + _missing_hint(key)[1:])
    text = read(path)
    if parse(text)[0].get("status") == "closed":
        return None
    if _owner_fresh(key, path, transcript, sid):
        return None
    reason = (f"Groundwork decision record: {outward} is blocked because the owner wrote after {key}'s record was last "
              f"updated ({path}). Read the owner's latest message against the record, then update it: "
              f'{decision_cli()} state {key} "<current state in one line>", and add any new decision, rejected option '
              f"or wait (entries need the owner's approval). Then retry. {gate_summary(text)}")
    return ("deny", reason[:REASON_CAP])


def post_tool(data: dict) -> str | None:
    """Hook-side bookkeeping after a successful tool call; returns a note for Claude, or None."""
    if not enabled() or str(data.get("hook_event_name") or "PostToolUse") != "PostToolUse":
        return None
    tool = str(data.get("tool_name") or "")
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit") and is_record_path(_record_write_target(ti)):
        key = os.path.basename(_record_write_target(ti)).split(" - ", 1)[0]
        update(key, lambda t: set_meta(t, last_updated=utc_now()) if t.startswith("---\n") else None)
        return None
    blob = json.dumps(ti, ensure_ascii=False).lower()
    if "good for review" not in blob:
        return None
    jira = (tool.startswith("mcp__") and outward_mcp(tool) and outward_mcp(tool).startswith("Jira")) or \
        (_browser_tool(tool) and jira_browser_action(tool, ti, str(data.get("transcript_path") or ""))) or \
        (tool == "Bash" and re.search(r"(?:^|[\s/;|&(])(?:jira|acli|jira-cli)\s", str(ti.get("command") or "")))
    if not jira:
        return None
    keys = gt.find_keys(json.dumps(ti, ensure_ascii=False)) if gt else []
    active = active_key(str(data.get("cwd") or ""), str(data.get("session_id") or ""))
    key = next((k for k in keys if find_record(k)), None) or (active if active and find_record(active) else None)
    if not key:
        return None
    update(key, lambda t: set_meta(t, status="closed", last_updated=utc_now()))
    return f"{key}'s decision record is now closed (the ticket moved to Good for review)."


# ---------------------------------------------------------------------------------------------- CLI

def _need(key: str) -> Path:
    key = key.upper()
    path = find_record(key)
    if path is None:
        raise SystemExit(f"no decision record for {key}; create it: {decision_cli()} create {key} --title \"…\"")
    return path


def cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="groundwork decision", description="Per-task decision records.")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="create the record for a task key (no entries)")
    c.add_argument("key")
    c.add_argument("--title", required=True)
    c.add_argument("--jira", default="")
    c.add_argument("--task-note", default="", help="path of the task note to link to and from")
    g = c.add_mutually_exclusive_group()
    g.add_argument("--work", action="store_true")
    g.add_argument("--personal", action="store_true")
    a = sub.add_parser("add", help="append an owner-approved entry")
    a.add_argument("key")
    a.add_argument("kind", choices=sorted(ENTRY_KINDS))
    a.add_argument("text")
    a.add_argument("--supersedes", default="", help="id of the entry this one replaces, e.g. D-2")
    s = sub.add_parser("state", help="replace Current state (and mark the record reviewed now)")
    s.add_argument("key")
    s.add_argument("text")
    w = sub.add_parser("waiting", help="set what the task is waiting on, or --clear")
    w.add_argument("key")
    w.add_argument("text", nargs="?", default="")
    w.add_argument("--clear", action="store_true")
    cl = sub.add_parser("close", help="set status closed")
    cl.add_argument("key")
    for name in ("show", "path"):
        sub.add_parser(name).add_argument("key")
    sub.add_parser("list", help="every record with its status")
    args = p.parse_args(argv)
    key = getattr(args, "key", "").upper()
    if args.cmd != "list" and not valid_key(key):
        raise SystemExit(f"not a task key: {getattr(args, 'key', '')!r} (expected e.g. COR-12850)")

    if args.cmd == "create":
        personal = True if args.personal else (False if args.work else None)
        path, made = create(key, args.title, os.getcwd(), args.jira, args.task_note, personal)
        print(("created " if made else "exists: ") + str(path))
        return 0
    if args.cmd == "add":
        _need(key)
        section, prefix = ENTRY_KINDS[args.kind]
        sup = args.supersedes.strip().upper()
        if sup and not re.match(r"^[DRS]-\d+$", sup):
            raise SystemExit(f"--supersedes must be an entry id such as D-2, not {args.supersedes!r}")
        made = {}

        def apply(t):
            if sup and not re.search(r"^- " + re.escape(sup) + r"\b", t, re.MULTILINE):
                raise SystemExit(f"{sup} is not an entry in this record")
            eid = next_id(t, prefix)
            made["id"] = eid
            line = f"- {eid} · {local_stamp()} · {scrub(args.text, 1500)}" + (f" (supersedes {sup})" if sup else "")
            return set_meta(append_to_section(t, section, line), last_updated=utc_now())
        path = update(key, apply)
        print(f"{made.get('id')} added to {path}")
        return 0
    if args.cmd == "state":
        _need(key)
        path = update(key, lambda t: set_meta(replace_section(t, "Current state",
                                                               f"{scrub(args.text, 1500)} ({local_stamp()})"),
                                              last_updated=utc_now()))
        print(f"Current state updated in {path}")
        return 0
    if args.cmd == "waiting":
        _need(key)
        if not args.clear and not args.text.strip():
            raise SystemExit("give what the task is waiting on, or --clear")

        def apply(t):
            meta, _ = parse(t)
            if args.clear:
                t = replace_section(t, "Waiting on", "")
                return set_meta(t, status="open" if meta.get("status") != "closed" else "closed", waiting_on="",
                                waiting_since="", last_updated=utc_now())
            since = local_stamp()
            t = replace_section(t, "Waiting on", f"- {scrub(args.text, 600)} (since {since})")
            return set_meta(t, status="waiting", waiting_on=scrub(args.text, 200), waiting_since=since,
                            last_updated=utc_now())
        print(f"Waiting on {'cleared' if args.clear else 'set'} in {update(key, apply)}")
        return 0
    if args.cmd == "close":
        _need(key)
        print(f"closed: {update(key, lambda t: set_meta(t, status='closed', last_updated=utc_now()))}")
        return 0
    if args.cmd == "show":
        path = _need(key)
        print(render(path, read(path), cap=20_000))
        return 0
    if args.cmd == "path":
        print(_need(key))
        return 0
    rows = []
    for d in folders():
        for path in sorted(d.glob(f"*{SUFFIX}")) if d.is_dir() else []:
            meta, _ = parse(read(path))
            rows.append(f"{meta.get('task_id') or path.name.split(' - ')[0]:<14} {meta.get('status') or '?':<8} {path}")
    print("\n".join(rows) if rows else "no decision records in " + ", ".join(str(d) for d in folders()))
    return 0


def main() -> None:
    if len(sys.argv) > 1:
        sys.exit(cli(sys.argv[1:]))
    if not enabled():
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            sys.exit(0)
        event = str(data.get("hook_event_name") or "")
        if event == "UserPromptSubmit":
            on_prompt(data)
        elif event == "SessionStart":
            on_session_start(data)
        elif event == "PreCompact":
            on_precompact(data)
        elif event == "Stop":
            on_stop(data)
    except SystemExit:
        raise
    except Exception:
        pass  # a decision-record problem must never break a session
    sys.exit(0)


if __name__ == "__main__":
    main()
