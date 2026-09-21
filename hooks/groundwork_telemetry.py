#!/usr/bin/env python3
"""Stop hook — append one structured telemetry record per substantive Groundwork task.

Groundwork has no other audit log, so this is its audit/telemetry mechanism: the same
Stop-hook pattern as require_material_review.py, append-only JSONL, fail-open. It never
blocks, never prints, never raises past main(); the user's task is primary, reporting is
secondary.

Trigger: the response Claude just finished contains a "Harness metadata" block (the block
output-contract.md asks for on substantive Groundwork tasks). No block → no record, which is
exactly the "omit for trivial conversational responses" rule.

What is recorded (identifiers and aggregates only — never prompt text, command text, file
paths, secrets, or reasoning):
  - from the metadata block (as the model stated it): playbook, execution mode, agent count and
    roles, evidence source types, validation state, profile, environment;
  - from the current turn of the transcript (deterministic): tool names used, MCP servers used,
    Agent calls (count, subagent_type/name), whether Edit/Write happened and on how many
    distinct files (count only), whether a test-shaped or deploy-shaped Bash command ran
    (matched by a small pattern list; the command itself is not stored);
  - from the response text: outcome (Overall: … / Status line keywords), and a heuristic
    clarification flag (the response ends by asking the user a question);
  - context: session_id, prompt_id, harness version (from ~/.claude/groundwork/VERSION), a
    short hash of cwd (so runs can be grouped by project without storing the path).

Disable with GROUNDWORK_TELEMETRY=off. Path override: GROUNDWORK_TELEMETRY_PATH.
"""
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

META_HEADING = re.compile(r"^\s*(?:#+\s*|\*\*)?Harness metadata(?:\*\*)?\s*$", re.MULTILINE | re.IGNORECASE)
META_FIELD = re.compile(r"^\s*[-*]\s*\**\s*([A-Za-z ]+?)\s*\**\s*:\s*\**\s*(.+?)\s*$")
# Free text copied from the model's block is stored only if it looks like a short label:
# letters/digits/space/_/- and at most 32 chars. Anything else (a path, an @, a token-shaped
# string, a sentence) is dropped — identifiers and labels only, never raw content.
LABEL = re.compile(r"^[a-z][a-z0-9 _-]{0,31}$")
TOKEN_SHAPED = re.compile(r"[a-z0-9_-]*\d[a-z0-9_-]*")  # a "word" containing a digit; long ones look like keys
PLAYBOOKS = {"RESEARCH", "EXPLAIN", "DESIGN", "PLAN", "IMPLEMENT", "TROUBLESHOOT", "VALIDATE", "AUDIT", "DEPLOY", "DOCUMENT"}
TAIL_CHUNK = 256 * 1024          # first backward read; doubles each step
TAIL_CAP = 32 * 1024 * 1024      # never read more than this from the end of the transcript
OVERALL = re.compile(r"Overall:\s*\**\s*(COMPLETE|PARTIAL|BLOCKED|PLANNED|FAILED)", re.IGNORECASE)
STATUS_LINE = re.compile(r"(?:^|\n)\s*(?:#+\s*|\*\*)?Status\**:?\s*\n?\s*\**\s*([A-Za-z][A-Za-z -]{0,40})", re.IGNORECASE)
TEST_CMD = re.compile(r"\b(pytest|npm test|npm run test|yarn test|go test|cargo test|make test|tox|nox|terraform validate|terraform plan|kubectl .* --dry-run)\b")
DEPLOY_CMD = re.compile(r"\b(terraform apply|tofu apply|kubectl apply|kubectl rollout|helm (install|upgrade)|gcloud run deploy|gcloud .* deploy|aws deploy|flux reconcile|argocd app sync|docker compose up|docker push)\b")
EXEC_MODES = {"single agent": "single_agent", "single_agent": "single_agent", "subagents": "subagents",
              "subagent": "subagents", "agent team": "agent_team", "agent_team": "agent_team", "team": "agent_team"}
VALIDATION_STATES = {"not verified": "not_verified", "unverified": "not_verified", "not_verified": "not_verified",
                     "partially verified": "partial", "partial": "partial", "verified": "verified"}


def default_path() -> Path:
    override = os.environ.get("GROUNDWORK_TELEMETRY_PATH")
    if override:
        return Path(os.path.expanduser(override))
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))
    return base / "groundwork" / "telemetry" / "events.jsonl"


def harness_version() -> str:
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))
    try:
        return (base / "groundwork" / "VERSION").read_text().strip() or "unknown"
    except Exception:
        return "unknown"


def parse_metadata(text: str) -> dict:
    """Fields of the 'Harness metadata' block as the model stated them (lower-cased keys)."""
    m = META_HEADING.search(text)
    if not m:
        return {}
    fields = {}
    for line in text[m.end():].splitlines():
        if not line.strip():
            if fields:
                break
            continue
        f = META_FIELD.match(line)
        if not f:
            if fields:
                break
            continue
        fields[f.group(1).strip().lower()] = f.group(2).strip().strip("*")
    return fields


def label(value: str, default: str = "unknown") -> str:
    """A short label or the default — never a path, token or sentence."""
    v = (value or "").strip().strip("*").lower()
    if not LABEL.match(v):
        return default
    if any(len(w) >= 12 for w in TOKEN_SHAPED.findall(v)):  # akia…123, ghp_…, sk-live-… shapes
        return default
    return v


def labels(value: str, limit: int) -> list:
    """Split a 'a + b, c / d (note)' list into labels; parentheticals and non-labels are dropped."""
    value = re.sub(r"\([^)]*\)", " ", value or "")
    out = []
    for part in re.split(r"[+,;]", value):  # '/' is not a separator: a slash means a path, dropped
        v = label(part, "")
        if v and v not in out:
            out.append(v)
    return out[:limit]


def parse_agents(value: str):
    """'3 — investigator, reviewer, validator' → (3, [...]); '1' → (1, []); 'none' → (0, [])."""
    if not value:
        return None, []
    count = None
    num = re.match(r"\s*(\d+)", value)
    if num:
        count = int(num.group(1))
    elif value.strip().lower() in ("none", "no", "0", "-"):
        count = 0
    roles = []
    tail = re.split(r"—|:|\s-\s", value, maxsplit=1)
    if len(tail) > 1:
        roles = labels(tail[1], 12)
    return count, roles


def is_human_prompt(e: dict) -> bool:
    if e.get("type") != "user" or e.get("isSidechain"):
        return False
    content = (e.get("message") or {}).get("content")
    return not (isinstance(content, list) and any(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content))


def current_turn(transcript_path: str) -> list:
    """Entries after the last human prompt (a 'user' entry that carries no tool_result).

    Reads the transcript backwards in growing chunks and stops at the first human prompt it
    meets, so cost follows the size of the current turn, not of the whole session. At most
    TAIL_CAP bytes are read; a turn longer than that contributes only its tail (facts are then
    a lower bound, which is acceptable for aggregate reporting)."""
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as f:
            pos, buf, step = size, b"", TAIL_CHUNK
            while True:
                take = min(step, pos)
                pos -= take
                f.seek(pos)
                buf = f.read(take) + buf
                step = min(step * 2, TAIL_CAP)
                lines = buf.split(b"\n")
                if pos > 0:
                    lines = lines[1:]  # first piece may be a partial line; it completes next round
                entries = []
                for raw in lines:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        e = json.loads(raw)
                    except Exception:
                        continue
                    if isinstance(e, dict):
                        entries.append(e)
                start = None
                for i in range(len(entries) - 1, -1, -1):
                    if is_human_prompt(entries[i]):
                        start = i
                        break
                if start is not None:
                    return entries[start:]
                if pos == 0 or size - pos >= TAIL_CAP:
                    return entries
    except Exception:
        return []


def turn_facts(entries: list) -> dict:
    tools, mcp, agents, files = [], [], [], set()
    tests_run = deploy = False
    for e in entries:
        if e.get("type") != "assistant":
            continue
        content = (e.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            name = str(b.get("name", ""))
            inp = b.get("input") if isinstance(b.get("input"), dict) else {}
            if name and name not in tools:
                tools.append(name)
            if name.startswith("mcp__"):
                server = name[5:].split("__")[0]
                if server and server not in mcp:
                    mcp.append(server)
            if name in ("Agent", "Task"):
                agents.append({"type": str(inp.get("subagent_type") or ""), "name": str(inp.get("name") or "")})
            if name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                fp = str(inp.get("file_path") or inp.get("notebook_path") or "")
                if fp:
                    files.add(fp)
            if name == "Bash":
                cmd = str(inp.get("command") or "")
                if TEST_CMD.search(cmd):
                    tests_run = True
                if DEPLOY_CMD.search(cmd):
                    deploy = True
    return {"tools": tools[:40], "mcp_servers": mcp[:20], "agents": agents[:20],
            "files_changed": len(files), "tests_run": tests_run, "deployment_performed": deploy,
            "implementation_performed": bool(files)}


def outcome_from_text(text: str):
    m = OVERALL.search(text)
    if m:
        return m.group(1).lower()
    m = STATUS_LINE.search(text)
    if m:
        head = m.group(1).lower()
        for key, value in (("validation failed", "failed"), ("blocked", "blocked"), ("failed", "failed"),
                           ("partial", "partial"), ("root cause found", "partial"), ("not verified", "partial"),
                           ("complete", "complete"), ("fixed", "complete"), ("passed", "complete"),
                           ("pass", "complete"), ("fail", "failed")):
            if key in head:
                return value
    return "unknown"


def asks_question(text: str) -> bool:
    tail = [ln.strip() for ln in text.strip().splitlines() if ln.strip()][-4:]
    return any(ln.endswith("?") for ln in tail)


def build_record(data: dict, text: str) -> dict:
    meta = parse_metadata(text)
    if not meta:
        return {}
    facts = turn_facts(current_turn(data.get("transcript_path", "")))
    exec_raw = meta.get("execution", "").lower()
    execution = next((v for k, v in EXEC_MODES.items() if k in exec_raw), "unknown")
    if execution == "unknown":
        execution = "single_agent" if not facts["agents"] else "subagents"
    count, roles = parse_agents(meta.get("agents", ""))
    if count is None:
        count = len(facts["agents"])
    if not roles:
        roles = labels(", ".join(a["name"] or a["type"] for a in facts["agents"]), 12)
    validation_raw = meta.get("validation", "").lower()
    validation = next((v for k, v in VALIDATION_STATES.items() if k in validation_raw), "unknown")
    evidence = labels(meta.get("evidence", ""), 8)
    playbook_raw = (meta.get("playbook") or "").strip("* ").upper().split()
    playbook = playbook_raw[0] if playbook_raw and playbook_raw[0] in PLAYBOOKS else "unknown"
    cwd = data.get("cwd") or os.getcwd()
    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": data.get("session_id") or "unknown",
        "prompt_id": data.get("prompt_id") or "unknown",
        "harness": "Groundwork",
        "harness_version": harness_version(),
        "profile": label(meta.get("profile") or os.environ.get("GROUNDWORK_PROFILE") or ""),
        "playbook": playbook,
        "execution_mode": execution,
        "agent_count": count,
        "agent_roles": roles[:12],
        "tools": facts["tools"],
        "mcp_servers": facts["mcp_servers"],
        "evidence_sources": evidence,
        "clarification_required": asks_question(text),
        "environment": label(meta.get("environment") or ""),
        "outcome": outcome_from_text(text),
        "validation": validation,
        "tests_run": facts["tests_run"],
        "implementation_performed": facts["implementation_performed"],
        "deployment_performed": facts["deployment_performed"],
        "files_changed": facts["files_changed"],
        "cwd_hash": hashlib.sha256(cwd.encode()).hexdigest()[:12],
    }


def main() -> None:
    if os.environ.get("GROUNDWORK_TELEMETRY", "").lower() == "off":
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            sys.exit(0)
        text = str(data.get("last_assistant_message") or "")
        record = build_record(data, text)
        if not record:
            sys.exit(0)
        path = default_path()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)  # owner-only records
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except SystemExit:
        raise
    except Exception:
        pass  # telemetry must never affect the task
    sys.exit(0)


if __name__ == "__main__":
    main()
