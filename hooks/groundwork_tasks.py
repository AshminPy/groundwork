#!/usr/bin/env python3
"""Groundwork task ledger and lifecycle (openspec/changes/add-task-lifecycle-gate/).

Library for hooks/groundwork_task_gate.py and the `groundwork task` CLI. Not registered as a hook.

One JSON file per task under $CLAUDE_CONFIG_DIR/groundwork/tasks/<repo key>/<KEY>.json, never in the
repository: a cloned repository must not be able to ship its own approval (design D1). The plan itself is
the task's OpenSpec change in the repository (source of truth for WHAT/WHY).

Lifecycle of a MATERIAL task: planning -> awaiting-approval -> approved -> complete (or cancelled).
  - intake():            deterministic classification of a prompt; creates the task and its OpenSpec change
  - request_approval():  plan gate (openspec validate --strict + Groundwork's required sections) -> code
  - approve()/cancel():  called ONLY from the UserPromptExpansion hook for a typed /gw-approve, /gw-cancel
  - complete():          evidence gate (plan unchanged, tasks checked, no out-of-scope change, verification
                         and a zero-MUST-FIX review on the current working-tree fingerprint)
STANDARD tasks are tracked for continuity (state "open") and are never gated.

Standard library only. Every git/openspec call has a timeout. CLI: python3 groundwork_tasks.py --help
"""
import argparse
import contextlib
import fnmatch
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

SCHEMA = 1
MATERIAL, STANDARD = "MATERIAL", "STANDARD"
PLANNING, AWAITING, APPROVED, COMPLETE, CANCELLED, OPEN = (
    "planning", "awaiting-approval", "approved", "complete", "cancelled", "open")
GATED_STATES = (PLANNING, AWAITING, APPROVED)
OPEN_STATES = GATED_STATES + (OPEN,)
OWNER_COMMANDS = ("gw-approve", "gw-cancel")
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # git's well-known empty tree: base for a repo with no commits
GIT_TIMEOUT = 5
OPENSPEC_TIMEOUT = 30
MAX_MISSION = 2000
MAX_HISTORY = 60
MAX_EVIDENCE = 30
MAX_BASELINE = 300
FINGERPRINT_DIFF_CAP = 20_000_000
CODE_LEN = 10

CHECKBOX_ANY = re.compile(r"^\s*-\s*\[[ xX]\]", re.MULTILINE)
CHECKBOX_DONE = re.compile(r"^\s*-\s*\[[xX]\]", re.MULTILINE)
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f​-‏  ‪-‮⁦-⁩﻿]")

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


def git_bytes(cwd, *args, timeout: float = GIT_TIMEOUT):
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, timeout=timeout,
                           stdin=subprocess.DEVNULL, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
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


def gated_tasks(root: str) -> list[dict]:
    return [t for t in load_tasks(root) if t.get("tier") == MATERIAL and t.get("state") in GATED_STATES]


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

# What the plan must establish, per category (deterministic intake checklist; the model resolves each in the plan).
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


def _file_digest(path: Path) -> str:
    try:
        if path.is_symlink():
            return "symlink:" + os.readlink(path)
        if not path.exists():
            return "deleted"
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except Exception:
        return "unreadable"


def _status_paths(root: str) -> list[str]:
    out = git(root, "status", "--porcelain", "-z", "--untracked-files=all", "--no-renames") or ""
    return [rec[3:] for rec in out.split("\0") if len(rec) > 3]


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
    """Classify a prompt and register a task when it is engineering work.

    Returns {"action": "created"|"existing", "tasks": [...], "root": root, "openspec": status} or None."""
    root = repo_root(cwd)
    if not root:
        return None
    cls = classify(text)
    if cls is None and (text or "").strip()[:1] in ("/", "<", "!"):
        return None
    existing = [t for t in (load_task(root, k) for k in find_keys(text or "")) if t]
    is_task = bool(cls) and cls["kind"] == "task"
    # The prompt's LEADING key decides; other keys are context (found by independent review: "COR-124: follow-up to
    # COR-123 …" never registered COR-124). Known and open -> its state (escalated when the prompt is now MATERIAL);
    # known and closed -> a fresh task only when the prompt asks for work (an action verb); unknown -> a new task.
    # Which key the work is for: the first key not yet in the ledger (follow-up tickets name the old ticket too, in
    # any order — found by independent review); else the first open key; else the first closed key.
    primary = None
    if is_task and cls["keys"]:
        known = {k: load_task(root, k) for k in cls["keys"]}
        primary = next((k for k in cls["keys"] if known[k] is None), None) or \
            next((k for k in cls["keys"] if known[k].get("state") not in (COMPLETE, CANCELLED)), None) or cls["keys"][0]
    current = load_task(root, primary) if primary else None
    if is_task and current and current.get("state") == OPEN and cls["tier"] == MATERIAL and cls.get("action"):
        return _escalate(root, current, cls, text)
    if not is_task or (current and (current.get("state") not in (COMPLETE, CANCELLED) or not cls.get("action"))):
        return {"action": "existing", "tasks": existing, "root": root} if existing else None
    if cls["tier"] == STANDARD and not cls["keys"]:
        return None  # untracked STANDARD work stays lightweight; a ticket key is what asks for tracking
    if not cls["keys"]:
        # A keyless engineering prompt while a task waits on the owner is almost always the owner answering that
        # task's questions (found by independent review: the reply opened a duplicate MATERIAL task).
        waiting = [t for t in gated_tasks(root) if t.get("state") in (PLANNING, AWAITING)]
        if waiting:
            return {"action": "existing", "tasks": waiting, "root": root, "suppressed": True}
    with locked(root):
        key = primary or next_gw_key(root)
        current = load_task(root, key)
        if current and current.get("state") in (COMPLETE, CANCELLED):
            # Follow-up work on a closed ticket is a new task: keep the old record, under a name the ledger never
            # loads as a task (found by independent review: a closed key stayed ungated forever).
            os.replace(task_file(root, key), ledger_dir(root) / f"{key}.closed-{int(now())}.json")
        elif current:  # created concurrently
            return {"action": "existing", "tasks": [current], "root": root}
        title = title_of(text, [key])
        task = {
            "schema": SCHEMA, "key": key, "title": title, "mission": clip(text, MAX_MISSION),
            "tier": cls["tier"], "risk": {"level": cls["level"], "categories": cls["categories"],
                                          "signals": cls["signals"]},
            "checklist": cls["checklist"], "repo_root": os.path.abspath(root), "session_id": session_id,
            "state": PLANNING if cls["tier"] == MATERIAL else OPEN, "created_at": now(),
            "approval": {}, "plan": {}, "blockers": [],
            "evidence": {"verifications": [], "reviews": [], "last_op_ts": 0},
        }
        status = None
        if cls["tier"] == MATERIAL:
            task["change"] = _new_change_name(root, key, title)
            status = ensure_openspec_change(root, task["change"])
            task["openspec_intake"] = status
        head = (git(root, "rev-parse", "HEAD") or "").strip()
        task["base_commit"] = head or EMPTY_TREE
        dirty = _status_paths(root)
        # Paths beyond the cap are recorded without a digest: excluded from the audit whatever their content
        # (found by independent review: they became permanent violations).
        task["baseline"] = {rel: (_file_digest(Path(root) / rel) if i < MAX_BASELINE else None)
                            for i, rel in enumerate(dirty)}
        add_history(task, "intake", f"{task['tier']} task registered from a prompt")
        save_task(root, task)
    return {"action": "created", "tasks": [task], "root": root, "openspec": status}


def _new_change_name(root: str, key: str, title: str) -> str:
    name, n = change_name(key, title), 1
    while (Path(root) / "openspec" / "changes" / (name if n == 1 else f"{name}-{n}")).exists():
        n += 1  # never adopt a directory an earlier (closed) task or another change already owns
    return name if n == 1 else f"{name}-{n}"


def _escalate(root: str, task: dict, cls: dict, text: str) -> dict:
    """An open STANDARD task whose key returns with MATERIAL signals becomes a gated MATERIAL task (found by
    independent review: 'COR-55: now deploy this to production' stayed ungated)."""
    with locked(root):
        t = load_task(root, task["key"])
        if not t or t.get("tier") != STANDARD or t.get("state") != OPEN:
            return {"action": "existing", "tasks": [t] if t else [], "root": root}
        t.update({"tier": MATERIAL, "state": PLANNING,
                  "risk": {"level": cls["level"], "categories": cls["categories"], "signals": cls["signals"]},
                  "checklist": [i for i in t.get("checklist", []) if i not in cls["checklist"]] + cls["checklist"]})
        t["mission"] = clip(t.get("mission", "") + "\n" + text, MAX_MISSION)
        t["change"] = _new_change_name(root, t["key"], t.get("title", ""))
        status = ensure_openspec_change(root, t["change"])
        t["openspec_intake"] = status
        add_history(t, "escalated", "STANDARD -> MATERIAL: the prompt named infrastructure, data, security, production or deployment work")
        save_task(root, t)
    return {"action": "created", "tasks": [t], "root": root, "openspec": status, "escalated": True}


# ---------------------------------------------------------------------------------------------- plan

REQUIRED_SECTIONS = ("prerequisites", "risks", "missing information", "estimate", "scope", "verification")
SECTION_ALIASES = {
    "prerequisites": ("prerequisites", "prerequisite", "prerequisites and dependencies", "dependencies and prerequisites"),
    "risks": ("risks", "risk", "risk assessment", "risks and mitigations"),
    "missing information": ("missing information", "open questions", "missing info", "unknowns"),
    "estimate": ("estimate", "effort estimate", "estimation", "effort"),
    "scope": ("scope", "approved scope"),
    "verification": ("verification", "verification commands"),
    "approved operations": ("approved operations",),
}
HEADING = re.compile(r"^(#{2,3})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
BACKTICK = re.compile(r"`([^`\n]+)`")
# `<name>` / `{zone}` placeholders: a command containing one can never be run as written, so evidence could never
# match it (found in the live acceptance run: a plan declared `gcloud compute instances describe <name> --zone <zone>`).
PLACEHOLDER = re.compile(r"<[A-Za-z_][^<>\s]*>|\{[A-Za-z_][^{}\s]*\}")
# A Verification or Approved Operations entry must be ONE simple command: evidence is matched against a single command
# exactly as declared (found by independent review: `make lint && pytest` was approved but could never be recorded).
SHELL_OPERATOR_CHARS = "();<>|&"


def _canonical(heading: str) -> str | None:
    h = re.sub(r"^[\d.\s]+", "", heading.strip().lower())
    h = " ".join(re.sub(r"[^a-z ]+", " ", h).split())
    for canon, names in SECTION_ALIASES.items():
        if h in names:
            return canon
    return None


def plan_sections(text: str) -> dict:
    found = {}
    heads = list(HEADING.finditer(text))
    for i, m in enumerate(heads):
        canon = _canonical(m.group(2))
        if not canon:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        found[canon] = (found.get(canon, "") + "\n" + text[m.end():end].strip()).strip()
    return found


def change_dir(root: str, task: dict) -> Path:
    return Path(root) / "openspec" / "changes" / task.get("change", "")


def plan_rel(task: dict) -> str:
    return f"openspec/changes/{task.get('change', '')}"


def _bad_scope(pattern: str) -> str | None:
    if pattern.startswith(("/", "~")) or ".." in pattern.split("/"):
        return "must be a repository-relative path"
    if set(pattern) <= set("*/.") or pattern == "**/*":
        return "matches the whole repository; name specific paths"
    return None


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


def _md(path: Path) -> str:
    return path.read_text(errors="replace") if path.is_file() and not path.is_symlink() else ""


def read_plan(root: str, task: dict) -> dict:
    """Parse the task's plan. Returns scope, verify, operations, task counts, open questions, problems."""
    d = change_dir(root, task)
    sections = plan_sections(_md(d / "proposal.md") + "\n" + _md(d / "design.md"))
    problems = []
    if not task.get("change") or not d.is_dir():
        problems.append(f"the OpenSpec change {plan_rel(task)}/ does not exist (create it: openspec new change {task.get('change')})")
    for name in REQUIRED_SECTIONS:
        if not sections.get(name, "").strip():
            problems.append(f"plan section '## {name.title()}' is missing or empty (proposal.md or design.md)")
    est = sections.get("estimate", "")
    if est and not (re.search(r"\d", est) and re.search(r"confiden|uncertain", est, re.IGNORECASE)):
        problems.append("'## Estimate' needs a number (or range) and a stated confidence or uncertainty")
    scope, verify, ops = [], [], []
    for pat in BACKTICK.findall(sections.get("scope", "")):
        pat = pat.strip()
        pat = pat[2:] if pat.startswith("./") else pat
        why = _bad_scope(pat)
        if why:
            problems.append(f"scope pattern `{pat}` {why}")
        elif pat not in scope:
            scope.append(pat)
    if sections.get("scope") and not scope and not any("scope pattern" in p for p in problems):
        problems.append("'## Scope' must list at least one path pattern in backticks, e.g. `infra/vm/**`")
    for section, found in (("verification", verify), ("approved operations", ops)):
        for cmd in BACKTICK.findall(sections.get(section, "")):
            cmd = " ".join(cmd.split())
            if PLACEHOLDER.search(cmd):
                problems.append(f"'## {section.title()}' command `{cmd}` contains a placeholder; write the exact "
                                "command that will be run (evidence is matched against it)")
            elif not _simple_command(cmd):
                problems.append(f"'## {section.title()}' entry `{cmd}` must be one simple command (no &&, ||, ;, |, "
                                "&, redirection, command substitution, comment or unbalanced quote); list each "
                                "command as its own entry")
            elif len(cmd) >= 3 and cmd not in found:
                found.append(cmd)
    if sections.get("verification") and not verify and not any("Verification" in p for p in problems):
        problems.append("'## Verification' must list at least one exact command in backticks")
    tasks_text = _md(d / "tasks.md")
    total, done = len(CHECKBOX_ANY.findall(tasks_text)), len(CHECKBOX_DONE.findall(tasks_text))
    if total == 0:
        problems.append("tasks.md has no '- [ ]' task checkboxes")
    open_questions = [ln.strip().lstrip("-* \t") for ln in sections.get("missing information", "").splitlines()
                      if ln.strip().startswith(("-", "*")) and not re.search(r"\b(none|resolved|answered)\b", ln, re.I)]
    return {"scope": scope, "verify": verify, "operations": ops, "tasks_total": total, "tasks_done": done,
            "open_questions": open_questions[:12], "problems": problems}


def plan_digest(root: str, task: dict) -> str | None:
    """sha256 over proposal.md, design.md and specs/**/*.md — where Scope, Verification and Approved Operations live
    (design D3). tasks.md is the progress checklist and is excluded: ticking or annotating it during execution voided
    the approval in the live acceptance run. Removing approved tasks is refused at completion instead."""
    d = change_dir(root, task)
    if not task.get("change") or not d.is_dir():
        return None
    files = [d / n for n in ("proposal.md", "design.md") if (d / n).is_file()]
    if (d / "specs").is_dir():
        files += sorted(p for p in (d / "specs").rglob("*.md") if p.is_file())
    h = hashlib.sha256()
    for p in files:
        try:
            content = p.read_bytes().replace(b"\r\n", b"\n")
        except Exception:
            content = b"<unreadable>"
        h.update(p.relative_to(d).as_posix().encode() + b"\0" + content + b"\0")
    return h.hexdigest()[:CODE_LEN]


def approval_valid(root: str, task: dict) -> bool:
    code = (task.get("approval") or {}).get("approved_code")
    return task.get("state") == APPROVED and bool(code) and plan_digest(root, task) == code


def openspec_validate(root: str, change: str) -> tuple[bool, str]:
    exe = shutil.which("openspec")
    if not exe:
        return False, "the openspec CLI is not on PATH, so the plan cannot be validated"
    try:
        r = subprocess.run([exe, "validate", change, "--strict", "--no-interactive"], cwd=root, capture_output=True,
                           text=True, timeout=OPENSPEC_TIMEOUT, stdin=subprocess.DEVNULL)
    except Exception as exc:
        return False, f"openspec validate failed to run: {clip(exc, 160)}"
    return r.returncode == 0, clip((r.stdout + "\n" + r.stderr).strip(), 600)


# ---------------------------------------------------------------------------------------------- scope audit


def path_matches(rel: str, pattern: str) -> bool:
    """`dir/**` and `dir/` match everything below dir; otherwise fnmatch, where * also crosses '/'."""
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return rel == prefix or rel.startswith(prefix + "/")
    if pattern.endswith("/"):
        return rel.startswith(pattern)
    return rel == pattern or fnmatch.fnmatchcase(rel, pattern)


def rel_path(root: str, path) -> str | None:
    """Repository-relative POSIX path of `path` (symlinks resolved), or None when it is outside the repository."""
    real_root = os.path.realpath(root)
    p = os.path.realpath(path if os.path.isabs(str(path)) else os.path.join(root, str(path)))
    if p == real_root:
        return ""
    if not p.startswith(real_root + os.sep):
        return None
    return Path(os.path.relpath(p, real_root)).as_posix()


def in_plan_dir(rel: str, tasks: list[dict]) -> bool:
    for t in tasks:
        pr = plan_rel(t)
        if t.get("change") and (rel == pr or rel.startswith(pr + "/")):
            return True
    return False


def allowed_rel(root: str, rel: str, tasks: list[dict]) -> bool:
    if in_plan_dir(rel, tasks):
        return True
    return any(approval_valid(root, t) and any(path_matches(rel, pat) for pat in t.get("plan", {}).get("scope", []))
               for t in tasks)


# Generated caches that running the verification itself creates. Never a change anyone reviews, and counting them made
# every Python test run an "unauthorized change" in a repository without a .gitignore (found in the live acceptance
# run). Matched by whole path segment only.
GENERATED_CACHE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def _generated(rel: str) -> bool:
    return any(part in GENERATED_CACHE_DIRS for part in rel.split("/")[:-1])


def changed_paths(root: str, task: dict) -> list[str]:
    """Paths changed since intake (committed, staged, unstaged, untracked), excluding paths that were already
    dirty at intake and are byte-identical now, and generated caches (GENERATED_CACHE_DIRS)."""
    base = task.get("base_commit") or EMPTY_TREE
    out = git(root, "diff", "--name-only", "-z", "--no-renames", base, "--")
    if out is None:
        out = git(root, "diff", "--name-only", "-z", "--no-renames", "HEAD", "--") or ""
    paths = {p for p in out.split("\0") if p}
    paths |= {p for p in (git(root, "ls-files", "-z", "--others", "--exclude-standard") or "").split("\0") if p}
    baseline = task.get("baseline") or {}
    return [rel for rel in sorted(paths) if not _generated(rel)
            and not (rel in baseline and baseline[rel] in (None, _file_digest(Path(root) / rel)))]


def scope_violations(root: str, tasks: list[dict] | None = None) -> list[str]:
    tasks = gated_tasks(root) if tasks is None else tasks
    bad = set()
    for t in tasks:
        bad.update(rel for rel in changed_paths(root, t) if not allowed_rel(root, rel, tasks))
    return sorted(bad)


def fingerprint(root: str, task: dict) -> str:
    """Hash of the working tree's changes since intake, excluding the task's own plan directory (design D5)."""
    base = task.get("base_commit") or EMPTY_TREE
    excl = f":(exclude){plan_rel(task)}"
    diff = git_bytes(root, "diff", "--binary", "--no-renames", base, "--", ".", excl, timeout=15)
    if diff is None:
        diff = git_bytes(root, "diff", "--binary", "--no-renames", "HEAD", "--", ".", excl, timeout=15)
    if diff is None:
        # Never a constant: an unreadable tree must not let earlier evidence match (found by independent review).
        return "unavailable-" + os.urandom(8).hex()
    elif len(diff) > FINGERPRINT_DIFF_CAP:
        diff = (git_bytes(root, "diff", "--stat", base, "--", ".", excl) or b"") + b"<large>"
    h = hashlib.sha256(diff + b"\0")
    pr = plan_rel(task)
    untracked = (git(root, "ls-files", "-z", "--others", "--exclude-standard") or "").split("\0")
    for rel in sorted(p for p in untracked if p and not _generated(p) and not (p == pr or p.startswith(pr + "/"))):
        try:
            st = os.lstat(os.path.join(root, rel))
            h.update(f"{rel}\0{st.st_size}\0{st.st_mtime_ns}\0".encode())
        except OSError:
            h.update(f"{rel}\0gone\0".encode())
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------------------------- transitions


def request_approval(root: str, key: str) -> tuple[bool, str]:
    task = load_task(root, key)
    if not task:
        return False, f"no task {key} in this repository's ledger"
    if task.get("tier") != MATERIAL:
        return False, f"{key} is {task.get('tier')}: no owner approval is needed"
    if task.get("state") not in GATED_STATES:
        return False, f"{key} is {task.get('state')}"
    if task.get("state") == APPROVED and approval_valid(root, task):
        return False, f"{key} is already approved and its plan is unchanged; nothing to request"
    plan = read_plan(root, task)
    problems = list(plan["problems"])
    if task.get("change") and change_dir(root, task).is_dir():
        ok, out = openspec_validate(root, task["change"])
        if not ok:
            problems.append("openspec validate --strict failed: " + out)
    if problems:
        update_task(root, key, lambda t: add_history(t, "approval-refused", f"{len(problems)} plan problem(s)"))
        return False, f"Approval not requested for {key}; fix the plan first:\n" + "\n".join(f"  - {p}" for p in problems)
    code = plan_digest(root, task)

    def apply(t):
        t["plan"] = {k: plan[k] for k in ("scope", "verify", "operations", "tasks_total", "open_questions")}
        t["approval"] = {"code": code, "requested_at": now()}
        t["state"] = AWAITING
        add_history(t, "approval-requested", f"plan code {code}")
    update_task(root, key, apply)
    task = load_task(root, key)
    lines = [f"Approval requested for {key} ({task['tier']}, risk {task['risk']['level']}): {task['title']}",
             f"  plan:      {plan_rel(task)}/ ({plan['tasks_total']} tasks)",
             f"  scope:     {', '.join(plan['scope'])}",
             f"  verify:    {'; '.join(plan['verify'])}"]
    if plan["operations"]:
        lines.append(f"  approved operations: {'; '.join(plan['operations'])}")
    if plan["open_questions"]:
        lines.append(f"  open questions ({len(plan['open_questions'])}; approving accepts the plan's stated assumptions):")
        lines += [f"    - {clip(q, 160)}" for q in plan["open_questions"][:8]]
    lines += ["", f"OWNER ACTION: review the plan, then type   /gw-approve {key} {code}",
              f"              or cancel the task with     /gw-cancel {key}",
              "Claude cannot approve. Until the owner approves, Groundwork allows only read-only work and plan edits;"
              " an edit to proposal.md, design.md or specs changes the code and needs a new request."]
    return True, "\n".join(lines)


def approve(root: str, key: str, code: str, session_id: str = "") -> tuple[bool, str]:
    """Record the owner's approval. Call ONLY from the UserPromptExpansion hook (design D2)."""
    task = load_task(root, key)
    if not task:
        return False, f"Groundwork: no task {key} in this repository's ledger ({root})."
    if task.get("state") != AWAITING:
        return False, f"Groundwork: {key} is '{task.get('state')}', not awaiting approval; nothing was approved."
    requested = (task.get("approval") or {}).get("code")
    if plan_digest(root, task) != requested:
        return False, (f"Groundwork: {key}'s plan changed after approval was requested (code {requested} is stale). "
                       "Ask Claude to run request-approval again and approve the new code.")
    if (code or "").strip().lower() != requested:
        return False, f"Groundwork: approval code does not match {key}'s current plan code; nothing was approved."
    plan = read_plan(root, task)
    problems = plan["problems"]  # the plan rules may be stricter than when approval was requested
    if problems:
        return False, (f"Groundwork: {key}'s plan no longer passes the plan check, so nothing was approved: "
                       + "; ".join(problems[:3]) + ". Ask Claude to fix the plan and request approval again.")

    def apply(t):
        t["state"] = APPROVED
        # tasks.md is outside the digest, so the task count the owner saw is taken now (completion_problems).
        t.setdefault("plan", {})["tasks_total"] = plan["tasks_total"]
        t["approval"].update({"approved_code": requested, "approved_at": now(), "approved_session": session_id,
                              "via": "/gw-approve (UserPromptExpansion)"})
        add_history(t, "approved", f"owner approved plan code {requested}")
    update_task(root, key, apply)
    return True, f"Groundwork: owner approved {key} (plan code {requested})."


def cancel(root: str, key: str) -> tuple[bool, str]:
    task = load_task(root, key)
    if not task:
        return False, f"Groundwork: no task {key} in this repository's ledger."
    if task.get("state") in (COMPLETE, CANCELLED):
        return False, f"Groundwork: {key} is already {task.get('state')}."

    def apply(t):
        t["state"] = CANCELLED
        add_history(t, "cancelled", "owner cancelled the task")
    update_task(root, key, apply)
    return True, f"Groundwork: owner cancelled {key}; it no longer gates this repository."


def completion_problems(root: str, task: dict) -> list[str]:
    if task.get("tier") != MATERIAL:
        return []
    if task.get("state") != APPROVED:
        return [f"{task['key']} is '{task.get('state')}'; only an approved task can complete"]
    if not approval_valid(root, task):
        # Everything else follows from this (the approved Scope no longer applies), so it is the only problem shown.
        return ["the plan (proposal, design or specs) changed after approval, so the approval and its Scope no longer "
                f"apply: run {task_cli()} request-approval {task['key']} and get the owner's new approval"]
    problems = []
    plan = read_plan(root, task)
    if plan["tasks_total"] == 0 or plan["tasks_done"] < plan["tasks_total"]:
        problems.append(f"tasks.md: {plan['tasks_done']}/{plan['tasks_total']} tasks checked")
    approved_total = int((task.get("plan") or {}).get("tasks_total") or 0)
    if plan["tasks_total"] < approved_total:
        problems.append(f"tasks.md has {plan['tasks_total']} tasks but the approved plan had {approved_total}; "
                        "approved tasks cannot be removed")
    bad = scope_violations(root)
    if bad:
        problems.append("changes outside the approved scope: " + ", ".join(bad[:10]))
    fp = fingerprint(root, task)
    ev = task.get("evidence") or {}
    last_op = float(ev.get("last_op_ts") or 0)
    for cmd in task.get("plan", {}).get("verify", []):
        runs = [r for r in ev.get("verifications", []) if r.get("cmd") == cmd]
        good = [r for r in runs if r.get("ok") and r.get("fp") == fp and float(r.get("ts", 0)) >= last_op]
        if not good:
            why = "never run" if not runs else ("last run failed" if not runs[-1].get("ok") else
                                                "not re-run since the working tree or an operation changed")
            problems.append(f"verification `{cmd}` has no successful run on the current working tree ({why})")
    current = [r for r in ev.get("reviews", []) if r.get("fp") == fp]
    # The latest review that reported a result decides; one without a REVIEW RESULT block neither approves nor masks
    # an earlier result (found by independent review).
    reported = [r for r in current if r.get("must_fix") is not None]
    if not current:
        problems.append("no independent review of the current working tree (dispatch a foreground review subagent "
                        "whose response ends with a REVIEW RESULT block: Verdict / Must-fix)")
    elif not reported:
        problems.append("no review of the current working tree has a parseable REVIEW RESULT block (Verdict / Must-fix)")
    elif reported[-1]["must_fix"] > 0:
        problems.append(f"the latest review reported {reported[-1]['must_fix']} MUST FIX finding(s); fix them and get a fresh review")
    return problems


def complete(root: str, key: str) -> tuple[bool, str]:
    task = load_task(root, key)
    if not task:
        return False, f"no task {key} in this repository's ledger"
    if task.get("state") in (COMPLETE, CANCELLED):
        return False, f"{key} is already {task.get('state')}"
    problems = completion_problems(root, task)
    if problems:
        update_task(root, key, lambda t: add_history(t, "completion-refused", f"{len(problems)} unmet condition(s)"))
        return False, f"{key} is NOT complete:\n" + "\n".join(f"  - {p}" for p in problems)

    def apply(t):
        t["state"] = COMPLETE
        t["completed_at"] = now()
        add_history(t, "complete", "evidence gate passed" if t.get("tier") == MATERIAL else "marked complete")
    update_task(root, key, apply)
    lines = [f"{key} is COMPLETE ({task.get('tier')})."]
    if task.get("tier") == MATERIAL:
        lines += [f"  verified: `{cmd}` passed on the final working tree" for cmd in task.get("plan", {}).get("verify", [])]
        reviews = (task.get("evidence") or {}).get("reviews", [])
        if reviews:
            lines.append(f"  reviewed: {reviews[-1].get('reviewer')} — {reviews[-1].get('verdict') or 'approve'}, 0 MUST FIX")
        lines.append("  scope:    no change outside the approved scope")
    return True, "\n".join(lines)


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


# ---------------------------------------------------------------------------------------------- evidence


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
    def apply(t):
        ev = t.setdefault("evidence", {})
        ev["last_op_ts"] = now()
        ev["operations"] = (ev.get("operations", []) + [{"cmd": clip(cmd, 200), "ts": now()}])[-MAX_EVIDENCE:]
        add_history(t, "operation", cmd)
    update_task(root, key, apply)


# ---------------------------------------------------------------------------------------------- rendering


def next_action(root: str, task: dict) -> str:
    key, state = task["key"], task.get("state")
    if task.get("tier") != MATERIAL:
        return f"plan inline, implement, test; then: {task_cli()} complete {key}" if state == OPEN else "none"
    if state == PLANNING:
        return (f"write the plan in {plan_rel(task)}/ (proposal.md or design.md with ## Prerequisites, ## Risks, "
                f"## Missing Information, ## Estimate, ## Scope, ## Verification; tasks.md), then run: "
                f"{task_cli()} request-approval {key}")
    if state == AWAITING:
        return f"owner: review the plan, then type /gw-approve {key} {task['approval'].get('code')} (or /gw-cancel {key})"
    if state == APPROVED:
        if not approval_valid(root, task):
            return f"the plan changed after approval: run {task_cli()} request-approval {key} and get a new approval"
        problems = completion_problems(root, task)
        return f"run: {task_cli()} complete {key}" if not problems else "implement within scope; next gap: " + problems[0]
    return "none"


def render(root: str, task: dict, detail: bool = False) -> str:
    risk = task.get("risk") or {}
    head = f"{task['key']}  {task.get('tier')}  {task.get('state')}"
    if task.get("tier") == MATERIAL:
        head += f"  risk {risk.get('level')} ({', '.join(risk.get('categories', []))})"
    lines = [head, f"  {task.get('title')}"]
    if task.get("change"):
        plan = read_plan(root, task)
        lines.append(f"  plan:      {plan_rel(task)}/  tasks {plan['tasks_done']}/{plan['tasks_total']}")
        appr = task.get("approval") or {}
        if appr.get("approved_at"):
            valid = ("task " + task.get("state", "")) if task.get("state") != APPROVED else (
                "valid" if approval_valid(root, task) else "VOID: plan changed since")
            lines.append(f"  approval:  owner approved code {appr.get('approved_code')} at {iso(appr['approved_at'])} ({valid})")
        elif appr.get("code"):
            lines.append(f"  approval:  requested {iso(appr.get('requested_at'))}, code {appr.get('code')}")
        if task.get("plan", {}).get("scope"):
            lines.append(f"  scope:     {', '.join(task['plan']['scope'])}")
        ev = task.get("evidence") or {}
        for cmd in task.get("plan", {}).get("verify", []):
            runs = [r for r in ev.get("verifications", []) if r.get("cmd") == cmd]
            seen = "not run" if not runs else ("passed" if runs[-1]["ok"] else "FAILED") + f" {iso(runs[-1]['ts'])}"
            lines.append(f"  verify:    `{cmd}` — {seen}")
        if ev.get("reviews"):
            r = ev["reviews"][-1]
            lines.append(f"  review:    {r.get('reviewer')} — must-fix {r.get('must_fix')} at {iso(r.get('ts'))}")
    for b in task.get("blockers", [])[-3:]:
        lines.append(f"  blocker:   {b.get('reason')}")
    if detail and task.get("checklist") and task.get("state") in (PLANNING, AWAITING, OPEN):
        lines.append("  intake checklist (resolve in the plan):")
        lines += [f"    - {c}" for c in task["checklist"]]
    if detail and task.get("history"):
        lines.append("  history:")
        lines += [f"    {iso(h.get('ts'))}  {h.get('event')}  {h.get('detail', '')}" for h in task["history"][-8:]]
    lines.append(f"  next:      {next_action(root, task)}")
    return "\n".join(lines)


def open_task_lines(cwd: str, limit: int = 700) -> list[str]:
    """Compact lines for the SessionStart snapshot: every open task in this repository's ledger."""
    root = repo_root(cwd)
    if not root:
        return []
    tasks = [t for t in load_tasks(root) if t.get("state") in OPEN_STATES]
    if not tasks:
        return []
    # Gated tasks first, newest first within each group: the task waiting on the owner must never be crowded out by
    # older STANDARD tasks (found by independent review).
    tasks.sort(key=lambda t: (t.get("state") not in GATED_STATES or t.get("tier") != MATERIAL, -float(t.get("created_at", 0))))
    lines = [f"open tasks (Groundwork task ledger, enforced by the task gate; details: {task_cli()} show <KEY>):"]
    used = len(lines[0])
    for i, t in enumerate(tasks):
        row = f"  {t['key']} {t.get('tier')} {t.get('state')} — {clip(t.get('title'), 70)}"
        if t.get("change"):
            row += f" | plan {plan_rel(t)}/"
        row += f" | next: {clip(next_action(root, t), 220)}"
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
    p = argparse.ArgumentParser(prog="groundwork task", description="Groundwork task ledger: intake, plan gate, "
                                "approval state and evidence-gated completion. Approval is not available here: "
                                "the owner types /gw-approve <KEY> <code> in Claude Code.")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("list", help="open tasks in this repository (--all: every repository, every state)")
    s.add_argument("--all", action="store_true")
    sub.add_parser("status", help="same as list")
    s = sub.add_parser("show", help="one task in full")
    s.add_argument("key")
    s = sub.add_parser("intake", help="register a task from a description (normally done by the prompt hook)")
    s.add_argument("text", nargs="+")
    s = sub.add_parser("request-approval", help="check the plan and record the code the owner approves")
    s.add_argument("key")
    s = sub.add_parser("complete", help="evidence-gated completion")
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
        tasks = [t for t in load_tasks(root) if t.get("state") in OPEN_STATES]
        print("\n".join(render(root, t) for t in tasks) if tasks else f"no open tasks in {root}")
        return 0
    if a.cmd == "intake":
        res = intake(os.getcwd(), " ".join(a.text), "cli")
        if not res:
            print("not recognised as an engineering task (no ticket key or action verb, or phrased as a question)")
            return 1
        for t in res["tasks"]:
            print(("registered " if res["action"] == "created" else "already recorded ") + t["key"])
            print(render(root, t, detail=True))
        return 0
    key = a.key.upper()
    if a.cmd == "show":
        t = load_task(root, key) if KEY_SAFE.match(key) else None
        if not t:
            print(f"no task {key} in {root}", file=sys.stderr)
            return 1
        print(render(root, t, detail=True))
        return 0
    if not KEY_SAFE.match(key):
        print(f"not a task key: {key}", file=sys.stderr)
        return 2
    if a.cmd == "request-approval":
        ok, msg = request_approval(root, key)
    elif a.cmd == "complete":
        ok, msg = complete(root, key)
    else:
        if not a.clear and not a.reason:
            print("give a reason, or --clear", file=sys.stderr)
            return 2
        ok, msg = set_blocker(root, key, None if a.clear else " ".join(a.reason))
    print(msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
