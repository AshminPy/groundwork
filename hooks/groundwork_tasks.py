#!/usr/bin/env python3
"""Groundwork task tracking around native OpenSpec (openspec/changes/add-task-lifecycle-gate/).

Library for hooks/groundwork_task_gate.py and the `groundwork task` CLI. Not registered as a hook.

Native OpenSpec is the development workflow (explore, propose, apply, sync, archive); its change directory is the
plan and the source of truth. Groundwork adds what OpenSpec does not keep:
  - intake():    deterministic classification of a prompt; records the task, and for MATERIAL work creates the
                 OpenSpec change with `openspec new change` (nothing else in the plan is written here)
  - evidence:    verification runs, review results and sensitive operations, tied to a fingerprint of the code
  - continuity:  one JSON record per task under $CLAUDE_CONFIG_DIR/groundwork/tasks/<repo key>/, outside the
                 repository, shown in every new session with phase, progress, evidence and next action
  - complete():  a MATERIAL task completes on evidence: tasks checked, each declared verification passed on the
                 current code, and a review with zero MUST FIX
There is no approval code and no scope gate: plans and implementation can change at any time. Sensitive actions
ask the user through Claude Code's own permission prompt (groundwork_task_gate.py).

Standard library only. Every git/openspec call has a timeout. CLI: python3 groundwork_tasks.py --help
"""
import argparse
import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl  # POSIX; Groundwork supports macOS and Linux only
except ImportError:  # pragma: no cover
    fcntl = None

SCHEMA = 2
MATERIAL, STANDARD = "MATERIAL", "STANDARD"
OPEN, COMPLETE, CANCELLED = "open", "complete", "cancelled"
CLOSED_STATES = (COMPLETE, CANCELLED)  # any other state (including schema-1 states) is open
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # git's well-known empty tree: base for a repo with no commits
GIT_TIMEOUT = 5
OPENSPEC_TIMEOUT = 30
MAX_MISSION = 2000
MAX_HISTORY = 60
MAX_EVIDENCE = 30

CHECKBOX_ANY = re.compile(r"^\s*-\s*\[[ xX]\]", re.MULTILINE)
CHECKBOX_DONE = re.compile(r"^\s*-\s*\[[xX]\]", re.MULTILINE)
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f​-‏  ‪-‮⁦-⁩﻿]")


def is_open(task: dict) -> bool:
    return task.get("state") not in CLOSED_STATES


# ---------------------------------------------------------------------------------------------- paths


def claude_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))


def tasks_root() -> Path:
    return claude_dir() / "groundwork" / "tasks"


def task_cli() -> str:
    """How Claude should invoke this CLI: the installed file's absolute path (always resolvable, unlike PATH)."""
    return f"python3 {Path(__file__).resolve()}"


def git(cwd, *args, timeout: float = GIT_TIMEOUT):
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, errors="replace",
                           timeout=timeout, stdin=subprocess.DEVNULL, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except Exception:
        return None
    return r.stdout if r.returncode == 0 else None


def repo_root(path) -> str | None:
    """Top level of the git work tree containing `path` (file or directory, existing or not), else None."""
    p = Path(os.path.abspath(str(path)))
    while not p.is_dir():
        if p == p.parent:
            return None
        p = p.parent
    out = git(p, "rev-parse", "--show-toplevel")
    out = (out or "").strip()
    return os.path.abspath(out) if out else None


def repo_key(root: str) -> str:
    """Same scheme as groundwork_session_snapshot.investigation_path(): <slug>-<sha256(root)[:10]>."""
    root = os.path.abspath(root)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", os.path.basename(root.rstrip("/"))).strip("-").lower() or "repo"
    return f"{slug}-{hashlib.sha256(root.encode('utf-8')).hexdigest()[:10]}"


def ledger_dir(root: str) -> Path:
    return tasks_root() / repo_key(root)


KEY_SAFE = re.compile(r"^[A-Z][A-Z0-9]{1,9}-\d{1,7}$")


def task_file(root: str, key: str) -> Path:
    if not KEY_SAFE.match(key or ""):
        raise ValueError(f"not a task key: {key!r}")
    return ledger_dir(root) / f"{key}.json"


def now() -> float:
    return time.time()


def iso(ts) -> str:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return "?"


def clip(text, limit: int) -> str:
    text = " ".join(CONTROL.sub("", str(text)).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------------------------------------------------------------------------------------------- ledger I/O


@contextlib.contextmanager
def locked(root: str):
    """Serialise read-modify-write of one repository's ledger (parallel tool calls fire hooks in parallel)."""
    d = ledger_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    fh = open(d / ".lock", "a")
    try:
        if fcntl:
            fcntl.flock(fh, fcntl.LOCK_EX)
        yield
    finally:
        if fcntl:
            fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(Exception):
            os.unlink(tmp)
        raise


def load_task(root: str, key: str) -> dict | None:
    try:
        path = task_file(root, key)
        if path.is_symlink() or not path.is_file():
            return None
        data = json.loads(path.read_text())
    except Exception:
        return None
    return data if isinstance(data, dict) and data.get("key") == key else None


def load_tasks(root: str) -> list[dict]:
    d = ledger_dir(root)
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        if p.name == "repo.json":
            continue
        t = load_task(root, p.stem)
        if t:
            out.append(t)
    out.sort(key=lambda t: t.get("created_at", 0))
    return out


def open_tasks(root: str) -> list[dict]:
    return [t for t in load_tasks(root) if is_open(t)]


def save_task(root: str, task: dict) -> None:
    task["updated_at"] = now()
    task["history"] = task.get("history", [])[-MAX_HISTORY:]
    repo_meta = ledger_dir(root) / "repo.json"
    if not repo_meta.exists():
        _write_json(repo_meta, {"root": os.path.abspath(root)})
    _write_json(task_file(root, task["key"]), task)


def add_history(task: dict, event: str, detail: str = "") -> None:
    task.setdefault("history", []).append({"ts": now(), "event": event, "detail": clip(detail, 300)})


def update_task(root: str, key: str, fn):
    """Locked load -> fn(task) -> save. Returns True, or None when the task does not exist."""
    with locked(root):
        task = load_task(root, key)
        if task is None:
            return None
        fn(task)
        save_task(root, task)
        return True


# ---------------------------------------------------------------------------------------------- intake

KEY_RE = re.compile(r"(?<![A-Za-z0-9_-])([A-Z][A-Z0-9]{1,9}-\d{1,7})(?![A-Za-z0-9_-])")
NOT_TICKET_PREFIXES = {"UTF", "SHA", "ISO", "RFC", "AES", "HTTP", "TLS", "SSL", "MD", "IPV", "RSA", "ECDSA",
                       "PEP", "CWE", "GPT", "ES", "ECMA", "SMS", "MP", "WCAG"}
QUESTION_RE = re.compile(
    r"^\s*(?:what|what's|whats|why|how|when|where|who|which|explain|describe|tell me|is|are|does|do|did|"
    r"should|compare|summari[sz]e|review|audit|investigate|analy[sz]e|research|find|show|list|look at|check|"
    r"can i|could i|should i|is it|are there)\b", re.IGNORECASE)
ACTION_RE = re.compile(
    r"(?<![a-z])(deploy|provision|create|build|implement|add|change|update|modify|migrate|upgrade|downgrade|"
    r"roll ?back|delete|remove|destroy|configure|refactor|fix|rotate|grant|revoke|scale|install|uninstall|"
    r"set ?up|enable|disable|patch|replace|rename|move|restore|decommission|write|automate|apply|release|"
    r"publish|terminate|drop|truncate|purge|wipe|expose|onboard)(?![a-z])", re.IGNORECASE)

# Risk categories: phrase lists matched on word boundaries in the lower-cased prompt. Tests pin behaviour,
# not these lists (design: "likely to change").
RISK_SIGNALS = {
    "cloud": ("gcp", "gcloud", "google cloud", "aws", "azure", "gke", "eks", "aks", "ec2", "compute engine",
              "cloud run", "cloud sql", "lambda", "s3", "gcs", "oci", "oracle cloud"),
    "infrastructure": ("vm", "vms", "virtual machine", "instance", "instances", "cluster", "node pool", "terraform",
                       "ansible", "helm", "kubernetes", "k8s", "vpc", "subnet", "load balancer", "dns", "bucket",
                       "server", "servers", "infrastructure", "infra", "network"),
    "data": ("database", "databases", "db", "postgres", "postgresql", "mysql", "oracle", "goldengate",
             "replication", "migration", "schema", "backup", "restore", "datastore", "data pipeline"),
    "security": ("iam", "role", "roles", "permission", "permissions", "policy", "secret", "secrets", "credential",
                 "credentials", "password", "token", "service account", "kms", "certificate", "tls", "ssl",
                 "firewall", "public ip", "expose", "ssh key", "api key", "rbac"),
    "production": ("prod", "production", "live", "customer-facing"),
    "deployment": ("deploy", "deployment", "provision", "release", "rollout", "roll out", "upgrade", "migrate",
                   "install"),
    "destructive": ("delete", "destroy", "drop", "remove", "purge", "wipe", "truncate", "decommission",
                    "terminate", "rollback", "roll back"),
    "cost": ("vm", "vms", "gpu", "cluster", "instance", "license", "licence", "licensing", "billing", "goldengate"),
}
MATERIAL_CATEGORIES = {"cloud", "infrastructure", "data", "security", "production", "deployment"}

# What the plan should settle, per category (deterministic intake checklist; the model resolves each in the plan).
CHECKLIST = {
    "ticket": ("Ticket content and acceptance criteria (fetch it if a Jira integration is configured; otherwise ask the owner)",),
    "cloud": ("Target cloud project/account and environment (dev, staging or production)", "Region and zone",
              "Identity used to make the change (short-lived credentials or workload identity; no static keys)",
              "Quota, organisation-policy and budget constraints"),
    "infrastructure": ("Sizing: machine type, CPU/memory, disk type and size, OS image",
                       "Network placement: VPC/subnet, firewall rules, public or private address",
                       "Where the infrastructure code lives and where its state is stored"),
    "data": ("Source and target systems, versions and connectivity", "Data volume and replication/recovery objectives",
             "Backup and data rollback path"),
    "security": ("Least-privilege roles required and who grants them", "Where secrets are stored and how they are read",
                 "Exposure: what becomes reachable, and from where"),
    "production": ("Change window, approver and communication", "Rollback plan and the signal that triggers it",
                   "Monitoring and alerting for the changed component"),
    "deployment": ("Deployment method and rollback method", "How success is verified after deployment"),
    "destructive": ("Exactly what is removed and its blast radius", "Backup or restore path before removal"),
    "cost": ("Expected cost, budget owner and any software licence required",),
}
STOPWORDS = {"a", "an", "the", "in", "on", "for", "to", "of", "and", "with", "into", "at", "by", "from", "please",
             "can", "you", "could", "would", "we", "our", "my", "new"}


def _has(text: str, phrase: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text) is not None


def find_keys(text: str) -> list[str]:
    keys = []
    for k in KEY_RE.findall(text or ""):
        if k.split("-")[0] not in NOT_TICKET_PREFIXES and k not in keys:
            keys.append(k)
    return keys


HOUSEKEEPING_RE = re.compile(r"\b(?:archiv\w*|sync\w*)\b", re.IGNORECASE)
OPENSPEC_WORD_RE = re.compile(r"\b(?:openspec|opsx|change|specs?)\b", re.IGNORECASE)


def housekeeping(text: str) -> bool:
    """Native OpenSpec housekeeping on a task's change (archive it, sync its specs), not new work."""
    return bool(HOUSEKEEPING_RE.search(text or "") and OPENSPEC_WORD_RE.search(text or ""))


def work_key(text: str, key: str) -> bool:
    """True when `key` names the work: it starts the prompt (`COR-1 …`, `[COR-1] …`) or heads a clause (`COR-1:`,
    `COR-1 - …`). A key elsewhere ("after COR-1 is merged", "depends on COR-2") is a reference."""
    k = re.escape(key)
    return bool(re.match(r"^\W*" + k + r"(?![A-Za-z0-9_-])", text or "") or re.search(
        r"(?<![A-Za-z0-9_-])" + k + r"\s*(?:[:–—]|-(?=\s))", text or ""))


def classify(text: str) -> dict | None:
    """Deterministic intake classification. None: not engineering work (or not intake-eligible input)."""
    raw = (text or "").strip()
    if not raw or raw[0] in "/<!":  # slash command, system envelope (<task-notification>, <wake> …), shell escape
        return None
    head = raw[:4000]
    lower = head.lower()
    keys = find_keys(head)
    question = bool(QUESTION_RE.match(head))
    action = ACTION_RE.search(head)
    categories, signals = [], []
    for cat, phrases in RISK_SIGNALS.items():
        hits = [p for p in phrases if _has(lower, p)]
        if hits:
            categories.append(cat)
            signals.extend(h for h in hits if h not in signals)
    if question:
        return {"kind": "question", "keys": keys, "categories": categories}
    if not keys and not action:
        return None
    material = bool(set(categories) & MATERIAL_CATEGORIES)
    tier = MATERIAL if material else STANDARD
    if not material:
        level = "low"
    elif {"production", "security", "destructive"} & set(categories) or len(set(categories) & MATERIAL_CATEGORIES) >= 3:
        level = "high"
    else:
        level = "medium"
    checklist = []
    if keys:
        checklist.extend(CHECKLIST["ticket"])
    for cat in categories:
        if tier == MATERIAL or cat == "destructive":
            checklist.extend(i for i in CHECKLIST.get(cat, ()) if i not in checklist)
    if not action and keys:
        checklist.append("Scope is unknown from the prompt alone: establish what the ticket asks for before planning")
    return {"kind": "task", "keys": keys, "tier": tier, "categories": categories, "signals": signals[:20],
            "level": level, "checklist": checklist, "action": action.group(1).lower() if action else None}


def title_of(text: str, keys: list[str]) -> str:
    first = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    if keys:
        first = re.sub(r"^\s*\[?" + re.escape(keys[0]) + r"\]?\s*[:\-–—]?\s*", "", first)
    return clip(first or (keys[0] if keys else "task"), 120)


def change_name(key: str, title: str) -> str:
    key_parts = key.lower().split("-")
    words = [w for w in re.findall(r"[a-z0-9]+", title.lower()) if w not in STOPWORDS and w not in key_parts][:5]
    return "-".join([key.lower()] + words)[:60].rstrip("-")


def next_gw_key(root: str) -> str:
    n = 0
    for t in load_tasks(root):
        m = re.match(r"^GW-(\d+)$", t.get("key", ""))
        if m:
            n = max(n, int(m.group(1)))
    return f"GW-{n + 1}"


def ensure_openspec_change(root: str, change: str) -> str:
    """Create the task's OpenSpec change with the OpenSpec CLI (never by hand). Returns a short status."""
    target = Path(root) / "openspec" / "changes" / change
    if target.is_dir():
        return "exists"
    exe = shutil.which("openspec")
    if not exe:
        return "not created: the openspec CLI is not on PATH"
    try:
        if not (Path(root) / "openspec").is_dir():
            subprocess.run([exe, "init", "--tools", "none"], cwd=root, capture_output=True, text=True,
                           timeout=OPENSPEC_TIMEOUT, stdin=subprocess.DEVNULL)
        r = subprocess.run([exe, "new", "change", change], cwd=root, capture_output=True, text=True,
                           timeout=OPENSPEC_TIMEOUT, stdin=subprocess.DEVNULL)
    except Exception as exc:
        return f"not created: {clip(exc, 160)}"
    if target.is_dir():
        return "created"
    return "not created: " + clip((r.stderr or r.stdout or "openspec new change failed").strip(), 200)


def intake(cwd: str, text: str, session_id: str = "") -> dict | None:
    """Classify a prompt and record a task when it is engineering work. Never blocks anything.

    Returns {"action": "created"|"existing", "tasks": [...], "root": root, "openspec": status} or None."""
    root = repo_root(cwd)
    if not root:
        return None
    cls = classify(text)
    if cls is None and (text or "").strip()[:1] in ("/", "<", "!"):
        return None
    existing = [t for t in (load_task(root, k) for k in find_keys(text or "")) if t]
    is_task = bool(cls) and cls["kind"] == "task"
    # Which key the work is for (follow-up tickets name the old ticket too, in any order): a new key that starts the
    # prompt or heads a clause; else an open key; else a closed key that starts the prompt or heads a clause (a fresh
    # task when the prompt asks for work); else any new key ("after COR-1 is merged, deploy COR-2"); else the first
    # key. A new key next to an open one ("depends on COR-122") is a reference.
    primary = None
    if is_task and cls["keys"]:
        known = {k: load_task(root, k) for k in cls["keys"]}
        new = [k for k in cls["keys"] if known[k] is None]
        opened = [k for k in cls["keys"] if known[k] and is_open(known[k])]
        closed = [k for k in cls["keys"] if known[k] and k not in opened]
        primary = next((k for k in new if work_key(text, k)), None) or next(iter(opened), None) or \
            next((k for k in closed if work_key(text, k)), None) or next(iter(new), None) or cls["keys"][0]
    current = load_task(root, primary) if primary else None
    if is_task and current and is_open(current) and current.get("tier") == STANDARD and cls["tier"] == MATERIAL \
            and cls.get("action"):
        return _escalate(root, current, cls, text)
    # A closed ticket opens a fresh task only when the prompt names it as the work and asks for work that is not
    # native OpenSpec housekeeping ("archive the COR-1 change" is about the finished task, found in the live run).
    reopen = bool(current) and not is_open(current) and bool(cls and cls.get("action")) and \
        work_key(text, primary) and not housekeeping(text)
    if not is_task or (current and not reopen):
        return {"action": "existing", "tasks": existing, "root": root} if existing else None
    if cls["tier"] == STANDARD and not cls["keys"]:
        return None  # untracked STANDARD work stays lightweight; a ticket key is what asks for tracking
    if not cls["keys"]:
        # A keyless prompt while a MATERIAL task is open is almost always more of that task (an answer, a revision).
        active = [t for t in open_tasks(root) if t.get("tier") == MATERIAL]
        if active:
            return {"action": "existing", "tasks": active, "root": root, "suppressed": True}
    with locked(root):
        key = primary or next_gw_key(root)
        current = load_task(root, key)
        if current and not is_open(current):
            # Follow-up work on a closed ticket is a new task: keep the old record under a name never loaded as a task.
            os.replace(task_file(root, key), ledger_dir(root) / f"{key}.closed-{int(now())}.json")
        elif current:  # created concurrently
            return {"action": "existing", "tasks": [current], "root": root}
        title = (current or {}).get("title") or title_of(text, [key])  # a follow-up keeps the ticket's title
        task = {
            "schema": SCHEMA, "key": key, "title": title, "mission": clip(text, MAX_MISSION),
            "tier": cls["tier"], "risk": {"level": cls["level"], "categories": cls["categories"],
                                          "signals": cls["signals"]},
            "checklist": cls["checklist"], "repo_root": os.path.abspath(root), "session_id": session_id,
            "state": OPEN, "created_at": now(), "blockers": [],
            "evidence": {"verifications": [], "reviews": [], "operations": [], "last_op_ts": 0},
        }
        status = None
        if cls["tier"] == MATERIAL:
            task["change"] = _new_change_name(root, key, title)
            status = ensure_openspec_change(root, task["change"])
            task["openspec_intake"] = status
        head = (git(root, "rev-parse", "HEAD") or "").strip()
        task["base_commit"] = head or EMPTY_TREE
        add_history(task, "intake", f"{task['tier']} task recorded from a prompt")
        save_task(root, task)
    return {"action": "created", "tasks": [task], "root": root, "openspec": status}


def _new_change_name(root: str, key: str, title: str) -> str:
    changes = Path(root) / "openspec" / "changes"

    def taken(candidate: str) -> bool:  # live, or archived by an earlier task (change_dir would resolve to it)
        return (changes / candidate).exists() or any((changes / "archive").glob(f"????-??-??-{candidate}"))
    name, n = change_name(key, title), 1
    while taken(name if n == 1 else f"{name}-{n}"):
        n += 1  # never adopt a directory an earlier (closed) task or another change already owns
    return name if n == 1 else f"{name}-{n}"


def _escalate(root: str, task: dict, cls: dict, text: str) -> dict:
    """An open STANDARD task whose key returns with MATERIAL signals becomes MATERIAL and gets an OpenSpec change."""
    with locked(root):
        t = load_task(root, task["key"])
        if not t or t.get("tier") != STANDARD or not is_open(t):
            return {"action": "existing", "tasks": [t] if t else [], "root": root}
        t.update({"tier": MATERIAL,
                  "risk": {"level": cls["level"], "categories": cls["categories"], "signals": cls["signals"]},
                  "checklist": [i for i in t.get("checklist", []) if i not in cls["checklist"]] + cls["checklist"]})
        t["mission"] = clip(t.get("mission", "") + "\n" + text, MAX_MISSION)
        t["change"] = _new_change_name(root, t["key"], t.get("title", ""))
        status = ensure_openspec_change(root, t["change"])
        t["openspec_intake"] = status
        add_history(t, "escalated", "STANDARD -> MATERIAL: the prompt named infrastructure, data, security, production or deployment work")
        save_task(root, t)
    return {"action": "created", "tasks": [t], "root": root, "openspec": status, "escalated": True}


# ---------------------------------------------------------------------------------------------- plan (native OpenSpec)

# The one Groundwork convention in the plan: a "## Verification" section (in proposal.md, design.md or tasks.md)
# listing the exact commands that prove the change works. Evidence is matched against them.
# Only an un-numbered `## Verification` heading declares commands, and only lines that start with one backticked
# command (optionally bulleted, optionally followed by ": …", "(…)" or " — …"): a native tasks.md group such as
# `## 2. Verification` with prose like "- [x] 2.1 Check `config.yaml`" is not a list of commands (found by review).
VERIFY_HEADING = re.compile(r"^#{2,3}[ \t]+(?:verification|verification commands|verify|how to verify)[ \t]*#*[ \t]*$",
                            re.MULTILINE | re.IGNORECASE)
ANY_HEADING = re.compile(r"^#{1,3}[ \t]", re.MULTILINE)
COMMAND_LINE = re.compile(r"^[ \t]*(?:[-*+][ \t]+(?:\[[ xX]\][ \t]+)?|\d+[.)][ \t]+)?`([^`\n]+)`(?:[ \t]*$|[ \t]*[:(][^\n]*$|"
                          r"[ \t]+[\u2014\u2013-][ \t][^\n]*$)", re.MULTILINE)
# `<name>` / `{zone}` placeholders: a command containing one can never be run as written, so evidence could never
# match it (found in the live acceptance run).
PLACEHOLDER = re.compile(r"<[A-Za-z_][^<>\s]*>|\{[A-Za-z_][^{}\s]*\}")
SHELL_OPERATOR_CHARS = "();<>|&"


def verification_entries(text: str) -> list[str]:
    """The commands listed under `## Verification` headings in one artifact."""
    found = []
    for m in VERIFY_HEADING.finditer(text):
        nxt = ANY_HEADING.search(text, m.end())
        found += COMMAND_LINE.findall(text[m.end():nxt.start() if nxt else len(text)])
    return found


def _simple_command(cmd: str) -> bool:
    """One simple command: no unquoted shell operator (&& || ; | & < > parentheses), no command substitution, no
    comment, balanced quotes. Quoted text such as --format='value(status)' is fine."""
    if "\n" in cmd or "$(" in cmd or "`" in cmd:
        return False
    try:
        lx = shlex.shlex(cmd, posix=True, punctuation_chars=SHELL_OPERATOR_CHARS)
        lx.whitespace_split = True
        lx.commenters = ""
        tokens = list(lx)
    except ValueError:
        return False
    return bool(tokens) and not any(set(t) <= set(SHELL_OPERATOR_CHARS) for t in tokens) and \
        not any(t.startswith("#") for t in tokens)


def change_dir(root: str, task: dict) -> Path:
    """The task's OpenSpec change directory; after a native `openspec archive` it is the archived copy."""
    name = task.get("change", "")
    live = Path(root) / "openspec" / "changes" / name
    if not name or live.is_dir():
        return live
    archived = sorted((Path(root) / "openspec" / "changes" / "archive").glob(f"????-??-??-{name}"))
    return archived[-1] if archived else live


def is_archived(root: str, task: dict) -> bool:
    return bool(task.get("change")) and change_dir(root, task).parent.name == "archive"


def plan_rel(root: str, task: dict) -> str:
    return change_dir(root, task).relative_to(root).as_posix()


def _md(path: Path) -> str:
    return path.read_text(errors="replace") if path.is_file() and not path.is_symlink() else ""


def read_plan(root: str, task: dict) -> dict:
    """What tracking needs from the native OpenSpec change: task progress and the declared verification commands,
    read fresh every time, so the plan can be revised whenever the user wants."""
    d = change_dir(root, task)
    tasks_text = _md(d / "tasks.md")
    verify, problems, sources = [], [], {}
    for name in ("proposal.md", "design.md", "tasks.md"):
        for cmd in verification_entries(tasks_text if name == "tasks.md" else _md(d / name)):
            cmd = " ".join(cmd.split())
            if PLACEHOLDER.search(cmd):
                problems.append(f"verification `{cmd}` ({name}) contains a placeholder; write the exact command "
                                "that will be run")
            elif not _simple_command(cmd):
                problems.append(f"verification `{cmd}` ({name}) must be one simple command (no &&, ||, ;, |, "
                                "redirection or command substitution); list each command on its own line")
            elif len(cmd) >= 3 and cmd not in verify:
                verify.append(cmd)
                sources[cmd] = name
    return {"exists": bool(task.get("change")) and d.is_dir(), "verify": verify, "problems": problems,
            "sources": sources, "tasks_total": len(CHECKBOX_ANY.findall(tasks_text)),
            "tasks_done": len(CHECKBOX_DONE.findall(tasks_text))}


def phase(root: str, task: dict, plan: dict | None = None) -> str:
    """planning -> implementing -> verifying (or archived) -> complete, read from the native OpenSpec artifacts."""
    if not is_open(task):
        return task.get("state", "")
    if task.get("tier") != MATERIAL:
        return "in progress"
    plan = plan or read_plan(root, task)
    if not plan["exists"] or plan["tasks_total"] == 0:
        return "planning"  # as in native OpenSpec, implementation starts from tasks.md
    if plan["tasks_done"] < plan["tasks_total"]:
        return "implementing"
    return "archived" if is_archived(root, task) else "verifying"


# ---------------------------------------------------------------------------------------------- evidence

# Generated caches that running the verification itself creates; never part of the fingerprint.
GENERATED_CACHE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
FINGERPRINT_TIMEOUT = 8  # below the hooks' own timeouts (10 s and more), so a slow tree never stalls a hook
LARGE_UNTRACKED = 5_000_000  # untracked files above this are fingerprinted by size and mtime, not hashed


def _generated(rel: str) -> bool:
    return any(part in GENERATED_CACHE_DIRS for part in rel.split("/")[:-1])


def _git_in(root: str, env: dict, *args) -> str | None:
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, errors="replace",
                           timeout=FINGERPRINT_TIMEOUT, stdin=subprocess.DEVNULL,
                           env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", **env})
    except Exception:
        return None
    return r.stdout if r.returncode == 0 else None


def fingerprint(root: str, task: dict) -> str:
    """Content hash (a git tree id) of every tracked and untracked, non-ignored file, except openspec/ and generated
    caches. Revising the plan, syncing specs, archiving, staging or committing never change it; changing a file does,
    whichever tool made the change (staging made evidence stale in the first build; found by independent review).
    Built in a temporary index and object directory, so the repository itself is never written."""
    def path(name: str) -> str | None:
        rel = (git(root, "rev-parse", "--git-path", name) or "").strip()
        return os.path.join(root, rel) if rel else None
    index, objects = path("index"), path("objects")
    if not objects:
        return "unavailable-" + os.urandom(8).hex()  # never a constant: an unreadable tree must not match old evidence
    with tempfile.TemporaryDirectory(prefix="gw-fp-") as tmp:
        tmp_index = os.path.join(tmp, "index")
        if index and os.path.isfile(index):
            shutil.copyfile(index, tmp_index)  # keeps git's stat cache, so only changed files are hashed
        os.mkdir(os.path.join(tmp, "objects"))
        env = {"GIT_INDEX_FILE": tmp_index, "GIT_OBJECT_DIRECTORY": os.path.join(tmp, "objects"),
               "GIT_ALTERNATE_OBJECT_DIRECTORIES": os.path.abspath(objects)}
        caches = [f":(exclude,glob)**/{d}/**" for d in sorted(GENERATED_CACHE_DIRS)]
        # Large untracked files (provider binaries, downloads) are fingerprinted by size and mtime instead of
        # hashed, so the cost stays bounded (found by independent review: 150 MB untracked took ~9 s).
        big = []
        for rel in (git(root, "ls-files", "-z", "--others", "--exclude-standard") or "").split("\0"):
            if rel and not rel.startswith("openspec/") and not _generated(rel):
                try:
                    st = os.lstat(os.path.join(root, rel))
                except OSError:
                    continue
                if st.st_size > LARGE_UNTRACKED:
                    big.append(f"{rel}\0{st.st_size}\0{st.st_mtime_ns}")
        skip = [":(exclude,literal)" + b.split("\0", 1)[0] for b in big]
        tree = None
        if _git_in(root, env, "add", "-A", "--", ".", ":(exclude)openspec", *caches, *skip) is not None and \
                _git_in(root, env, "rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", "openspec",
                        *[f":(glob)**/{d}/**" for d in sorted(GENERATED_CACHE_DIRS)]) is not None:
            tree = (_git_in(root, env, "write-tree") or "").strip()
    if not tree:
        return "unavailable-" + os.urandom(8).hex()
    return hashlib.sha256("\0".join([tree, *sorted(big)]).encode()).hexdigest()[:16] if big else tree[:16]


def record_verification(root: str, key: str, cmd: str, ok: bool, detail: str = "") -> None:
    def apply(t):
        ev = t.setdefault("evidence", {})
        ev["verifications"] = (ev.get("verifications", []) + [
            {"cmd": cmd, "ok": bool(ok), "ts": now(), "fp": fingerprint(root, t), "detail": clip(detail, 200)}])[-MAX_EVIDENCE:]
        add_history(t, "verification", f"{'passed' if ok else 'FAILED'}: {cmd}")
    update_task(root, key, apply)


def record_review(root: str, key: str, reviewer: str, result: dict) -> None:
    def apply(t):
        ev = t.setdefault("evidence", {})
        must_fix = result.get("must_fix")
        if must_fix is None and result.get("verdict") == "approve":
            must_fix = 0
        ev["reviews"] = (ev.get("reviews", []) + [{"reviewer": clip(reviewer, 80), "must_fix": must_fix,
                                                   "verdict": result.get("verdict"), "ts": now(),
                                                   "fp": fingerprint(root, t)}])[-MAX_EVIDENCE:]
        add_history(t, "review", f"{reviewer}: must_fix={must_fix}")
    update_task(root, key, apply)


def record_operation(root: str, key: str, cmd: str) -> None:
    """A sensitive operation ran after the user authorized it: verification must run again after it."""
    def apply(t):
        ev = t.setdefault("evidence", {})
        ev["last_op_ts"] = now()
        ev["operations"] = (ev.get("operations", []) + [{"cmd": clip(cmd, 200), "ts": now()}])[-MAX_EVIDENCE:]
        add_history(t, "operation", cmd)
    update_task(root, key, apply)


def evidence_state(root: str, task: dict, plan: dict | None = None) -> dict:
    """Each declared verification: passed / failed / stale / not run, on the current code; and the latest review."""
    plan = plan or read_plan(root, task)
    ev = task.get("evidence") or {}
    fp = fingerprint(root, task)
    last_op = float(ev.get("last_op_ts") or 0)
    verify = {}
    for cmd in plan["verify"]:
        runs = [r for r in ev.get("verifications", []) if r.get("cmd") == cmd]
        # The latest run on the current code (after the last sensitive operation) decides.
        current = [r for r in runs if r.get("fp") == fp and float(r.get("ts", 0)) >= last_op]
        if current:
            verify[cmd] = "passed" if current[-1].get("ok") else "failed"
        else:
            verify[cmd] = "stale" if runs else "not run"
    # The latest review with a parseable result decides; one without a REVIEW RESULT block neither approves nor
    # masks an earlier result.
    current = [r for r in ev.get("reviews", []) if r.get("fp") == fp and r.get("must_fix") is not None]
    return {"verify": verify, "review": current[-1]["must_fix"] if current else None}


# ---------------------------------------------------------------------------------------------- transitions


def completion_problems(root: str, task: dict, plan: dict | None = None, state: dict | None = None) -> list[str]:
    """What a MATERIAL task still lacks to complete on evidence. STANDARD tasks complete when the user says so."""
    if task.get("tier") != MATERIAL:
        return []
    plan = plan or read_plan(root, task)
    problems = []
    if not plan["exists"]:
        problems.append(f"no OpenSpec change {plan_rel(root, task)}/ (create it: openspec new change {task.get('change')})")
    elif plan["tasks_total"] == 0 or plan["tasks_done"] < plan["tasks_total"]:
        problems.append(f"tasks.md: {plan['tasks_done']}/{plan['tasks_total']} tasks checked")
    problems += plan["problems"]
    if plan["exists"] and not plan["verify"] and not plan["problems"]:
        problems.append("no verification declared: add a `## Verification` section (design.md, proposal.md or "
                        "tasks.md) listing each command that proves the change on its own line, in backticks")
    state = state or evidence_state(root, task, plan)
    for cmd, seen in state["verify"].items():
        if seen != "passed":
            why = {"not run": "never run", "failed": "last run failed",
                   "stale": "not re-run since the code or an operation changed"}[seen]
            problems.append(f"verification `{cmd}` ({plan['sources'].get(cmd, 'plan')}) has no passing run on the "
                            f"current code ({why})")
    if state["review"] is None:
        problems.append("no independent review of the current code (a foreground review subagent whose response ends "
                        "with a REVIEW RESULT block: Verdict / Must-fix)")
    elif state["review"] > 0:
        problems.append(f"the latest review reported {state['review']} MUST FIX finding(s); fix them and get a fresh review")
    return problems


def complete(root: str, key: str) -> tuple[bool, str]:
    task = load_task(root, key)
    if not task:
        return False, f"no task {key} in this repository's ledger"
    if not is_open(task):
        return False, f"{key} is already {task.get('state')}"
    problems = completion_problems(root, task)
    if problems:
        update_task(root, key, lambda t: add_history(t, "completion-refused", f"{len(problems)} unmet condition(s)"))
        return False, f"{key} is not complete yet:\n" + "\n".join(f"  - {p}" for p in problems)

    def apply(t):
        t["state"] = COMPLETE
        t["completed_at"] = now()
        add_history(t, "complete", "evidence passed" if t.get("tier") == MATERIAL else "marked complete")
    update_task(root, key, apply)
    lines = [f"{key} is complete."]
    if task.get("tier") == MATERIAL:
        lines += [f"  verified: `{cmd}` passed on the final code" for cmd in read_plan(root, task)["verify"]]
        reviews = (task.get("evidence") or {}).get("reviews", [])
        if reviews:
            lines.append(f"  reviewed: {reviews[-1].get('reviewer')}, 0 MUST FIX")
        if not is_archived(root, task):
            lines.append(f"  next: archive the change natively when ready (openspec archive {task.get('change')})")
    return True, "\n".join(lines)


def cancel(root: str, key: str) -> tuple[bool, str]:
    task = load_task(root, key)
    if not task:
        return False, f"no task {key} in this repository's ledger"
    if not is_open(task):
        return False, f"{key} is already {task.get('state')}"

    def apply(t):
        t["state"] = CANCELLED
        add_history(t, "cancelled", "cancelled")
    update_task(root, key, apply)
    return True, f"{key} cancelled."


def set_blocker(root: str, key: str, reason: str | None) -> tuple[bool, str]:
    def apply(t):
        if reason:
            t.setdefault("blockers", []).append({"ts": now(), "reason": clip(reason, 300)})
            add_history(t, "blocked", reason)
        else:
            t["blockers"] = []
            add_history(t, "unblocked", "")
    if update_task(root, key, apply) is None:
        return False, f"no task {key} in this repository's ledger"
    return True, f"{key}: blocker {'recorded' if reason else 'cleared'}"


# ---------------------------------------------------------------------------------------------- status


def next_action(root: str, task: dict, plan: dict | None = None, state: dict | None = None) -> str:
    key = task["key"]
    if not is_open(task):
        return "none"
    if task.get("blockers"):
        return f"blocked: {clip(task['blockers'][-1].get('reason'), 160)}"
    if task.get("tier") != MATERIAL:
        return f"implement and test; then: {task_cli()} complete {key}"
    plan = plan or read_plan(root, task)
    ph = phase(root, task, plan)
    if ph == "planning":
        return (f"plan it with OpenSpec in {plan_rel(root, task)}/ (proposal, design with a ## Verification section, "
                "specs, tasks; /opsx:propose), then implement (/opsx:apply)")
    if ph == "implementing":
        return f"implement the next unchecked task in {plan_rel(root, task)}/tasks.md (/opsx:apply)"
    problems = completion_problems(root, task, plan, state)
    return f"run: {task_cli()} complete {key}" if not problems else problems[0]


def evidence_summary(root: str, task: dict, plan: dict | None = None, state: dict | None = None) -> str:
    ev = task.get("evidence") or {}
    if task.get("tier") != MATERIAL or not task.get("change"):
        return f"{len(ev.get('verifications', []))} check run(s), {len(ev.get('reviews', []))} review(s)"
    state = state or evidence_state(root, task, plan)
    passed = sum(1 for v in state["verify"].values() if v == "passed")
    review = "none" if state["review"] is None else f"{state['review']} must-fix"
    return f"verify {passed}/{len(state['verify'])} passed, review {review}"


def render(root: str, task: dict, detail: bool = False) -> str:
    """Task, phase, progress, evidence, next action."""
    plan = read_plan(root, task) if task.get("change") else None
    # One fingerprint per render: it is the expensive part (git hashes changed files).
    state = evidence_state(root, task, plan) if plan and task.get("tier") == MATERIAL else None
    progress = f" · {plan['tasks_done']}/{plan['tasks_total']} tasks" if plan and plan["exists"] else ""
    lines = [f"{task['key']}  {task.get('title')}",
             f"  {phase(root, task, plan)}{progress} · evidence: {evidence_summary(root, task, plan, state)}",
             f"  next: {next_action(root, task, plan, state)}"]
    if not detail:
        return "\n".join(lines)
    risk = task.get("risk") or {}
    lines.insert(1, f"  {task.get('tier')}, risk {risk.get('level')}" +
                 (f" ({', '.join(risk.get('categories', []))})" if risk.get("categories") else ""))
    if plan:
        lines.append(f"  plan: {plan_rel(root, task)}/")
        lines += [f"  verify: `{cmd}` — {seen}" for cmd, seen in (state or evidence_state(root, task, plan))["verify"].items()]
        lines += [f"  plan problem: {p}" for p in plan["problems"]]
    ev = task.get("evidence") or {}
    if ev.get("reviews"):
        r = ev["reviews"][-1]
        lines.append(f"  review: {r.get('reviewer')} — must-fix {r.get('must_fix')} at {iso(r.get('ts'))}")
    if ev.get("operations"):
        op = ev["operations"][-1]
        lines.append(f"  last sensitive operation: {op.get('cmd')} at {iso(op.get('ts'))}")
    if task.get("checklist") and is_open(task):
        lines.append("  intake checklist (settle each in the plan):")
        lines += [f"    - {c}" for c in task["checklist"]]
    if task.get("history"):
        lines.append("  history:")
        lines += [f"    {iso(h.get('ts'))}  {h.get('event')}  {h.get('detail', '')}" for h in task["history"][-8:]]
    return "\n".join(lines)


def open_task_lines(cwd: str, limit: int = 700) -> list[str]:
    """Compact lines for the SessionStart snapshot: every open task in this repository's ledger."""
    root = repo_root(cwd)
    if not root:
        return []
    tasks = open_tasks(root)
    if not tasks:
        return []
    tasks.sort(key=lambda t: (t.get("tier") != MATERIAL, -float(t.get("created_at", 0))))
    lines = [f"open tasks (Groundwork task ledger; details: {task_cli()} show <KEY>):"]
    used = len(lines[0])
    for i, t in enumerate(tasks):
        plan = read_plan(root, t) if t.get("change") else None
        state = evidence_state(root, t, plan) if plan and t.get("tier") == MATERIAL else None
        progress = f" {plan['tasks_done']}/{plan['tasks_total']}" if plan and plan["exists"] else ""
        row = (f"  {t['key']} [{phase(root, t, plan)}{progress}] {clip(t.get('title'), 60)} · evidence: "
               f"{evidence_summary(root, t, plan, state)} · next: {clip(next_action(root, t, plan, state), 200)}")
        if used + len(row) > limit:
            lines.append(f"  … {len(tasks) - i} more ({task_cli()} list)")
            break
        lines.append(row)
        used += len(row)
    return lines


# ---------------------------------------------------------------------------------------------- CLI


def _all_roots() -> list[str]:
    roots = []
    if tasks_root().is_dir():
        for d in sorted(tasks_root().iterdir()):
            try:
                roots.append(json.loads((d / "repo.json").read_text())["root"])
            except Exception:
                continue
    return roots


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="groundwork task", description="Groundwork task tracking around native "
                                "OpenSpec: intake, status, evidence and evidence-based completion.")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("list", help="open tasks in this repository (--all: every repository, every state)")
    s.add_argument("--all", action="store_true")
    sub.add_parser("status", help="same as list")
    s = sub.add_parser("show", help="one task in full")
    s.add_argument("key")
    s = sub.add_parser("intake", help="record a task from a description (normally done by the prompt hook)")
    s.add_argument("text", nargs="+")
    s = sub.add_parser("complete", help="complete a task (MATERIAL: on evidence)")
    s.add_argument("key")
    s = sub.add_parser("cancel", help="drop a task")
    s.add_argument("key")
    s = sub.add_parser("block", help="record a blocker (or --clear)")
    s.add_argument("key")
    s.add_argument("reason", nargs="*")
    s.add_argument("--clear", action="store_true")
    a = p.parse_args(argv)
    if not a.cmd:
        p.print_help()
        return 0
    if a.cmd == "list" and a.all:
        found = False
        for root in _all_roots():
            tasks = load_tasks(root)
            if tasks:
                found = True
                print(f"# {root}")
                for t in tasks:
                    print(f"  {t['key']}  {t.get('tier')}  {t.get('state')}  {t.get('title')}")
        if not found:
            print("no tasks recorded")
        return 0
    root = repo_root(os.getcwd())
    if not root:
        print("not inside a git repository: tasks are recorded per repository", file=sys.stderr)
        return 2
    if a.cmd in ("list", "status"):
        tasks = open_tasks(root)
        print("\n".join(render(root, t) for t in tasks) if tasks else f"no open tasks in {root}")
        return 0
    if a.cmd == "intake":
        res = intake(os.getcwd(), " ".join(a.text), "cli")
        if not res:
            print("not recognised as an engineering task (no ticket key or action verb, or phrased as a question)")
            return 1
        for t in res["tasks"]:
            print(("recorded " if res["action"] == "created" else "already recorded ") + t["key"])
            print(render(root, t, detail=True))
        return 0
    key = a.key.upper()
    if not KEY_SAFE.match(key):
        print(f"not a task key: {key}", file=sys.stderr)
        return 2
    if a.cmd == "show":
        t = load_task(root, key)
        if not t:
            print(f"no task {key} in {root}", file=sys.stderr)
            return 1
        print(render(root, t, detail=True))
        return 0
    if a.cmd == "complete":
        ok, msg = complete(root, key)
    elif a.cmd == "cancel":
        ok, msg = cancel(root, key)
    else:
        if not a.clear and not a.reason:
            print("give a reason, or --clear", file=sys.stderr)
            return 2
        ok, msg = set_blocker(root, key, None if a.clear else " ".join(a.reason))
    print(msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
