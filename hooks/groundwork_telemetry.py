#!/usr/bin/env python3
"""Stop hook — append one structured telemetry record per substantive Groundwork task.

Groundwork has no other audit log, so this is its audit/telemetry mechanism: the same
Stop-hook pattern as require_material_review.py, append-only JSONL, fail-open. It never
blocks, never prints, never raises past main(); the user's task is primary, reporting is
secondary.

Trigger: the turn was substantive — the response carries a "Harness metadata" block (the block
output-contract.md asks for) OR the current turn used at least one tool. A conversational reply
with no tool use produces no record. When the block is missing, observed facts are still
recorded and `declared.block_present` is false (declared fields stay "unknown").

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

Record layout (schema 2): `observed` holds what the hook determined itself (transcript facts,
environment, version); `declared` holds what the model stated (block fields, status sentence).
Reports must not present declared fields as verified.

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
# Accepts the code-block layout ("Playbook:       IMPLEMENT") and, for tolerance, a bullet or bold key.
META_FIELD = re.compile(r"^\s*(?:[-*]\s*)?\**\s*([A-Za-z ]+?)\s*\**\s*:\s*\**\s*(.+?)\s*$")
# Free text copied from the model's block is stored only if it looks like a short label:
# letters/digits/space/_/- and at most 32 chars. Anything else (a path, an @, a token-shaped
# string, a sentence) is dropped — identifiers and labels only, never raw content.
LABEL = re.compile(r"^[a-z][a-z0-9 _:-]{0,31}$")  # ":" allowed for agent ids like ecc:code-reviewer
TOKEN_SHAPED = re.compile(r"[a-z0-9_-]*\d[a-z0-9_-]*")  # a "word" containing a digit; long ones look like keys
PLAYBOOKS = {"RESEARCH", "EXPLAIN", "DESIGN", "PLAN", "IMPLEMENT", "TROUBLESHOOT", "VALIDATE", "AUDIT", "DEPLOY", "DOCUMENT"}
TAIL_CHUNK = 256 * 1024          # first backward read; doubles each step
TAIL_CAP = 32 * 1024 * 1024      # never read more than this from the end of the transcript
HEADLINE = re.compile(r"^\s*Groundwork\s+\S+\s*[·\-–—|]\s*([A-Za-z]+)\s*$", re.IGNORECASE)  # "Groundwork 1.3.2 · IMPLEMENT"
# Outcome — model-declared, read from the response's own status language (output-contract.md Layer 1
# and the playbooks' Status / Result vocabularies). Precedence inside a sentence: failed > blocked >
# partial > complete; "not done"-style negations count as partial; nothing recognisable -> unknown.
OVERALL = re.compile(r"Overall:\s*\**\s*(COMPLETE|PARTIAL|BLOCKED|PLANNED|FAILED)", re.IGNORECASE)
STATUS_HEAD = re.compile(r"(?:^|\n)[ \t]*(?:#+[ \t]*)?\**[ \t]*(?:Status|Result)[ \t]*\**[ \t]*:?[ \t]*\**[ \t]*(.*)", re.IGNORECASE)
NOTHING_LEFT = re.compile(r"\b(?:next(?: action| step)?|your move|remaining|open items?)\s*\**\s*:\s*\**\s*(?:none|nothing)\b", re.IGNORECASE)
LEAD_HEAD = re.compile(r"(?:^|\n)[ \t]*(?:#+[ \t]*)?\**[ \t]*(?:Answer|Recommendation|Deliverable|Plan|Goal)[ \t]*\**[ \t]*:?", re.IGNORECASE)
BOLD_LEAD = re.compile(r"^\s*\*\*(?:(?:my )?(?:call|finding|verdict|answer|result|status)\s*:\s*)?(.+?)\*\*", re.IGNORECASE)
# A plain opening line that starts with a state word is explicit status language too ("Complete. subtract() added…").
STATE_LEAD = re.compile(r"^\s*(?:complete[d]?|partial(?:ly)?|blocked|failed|fixed|done|deployed|resolved|root cause found|not verified|pass|fail|verified)\b[.:—-]", re.IGNORECASE)
NO_FAIL = re.compile(r"\b(?:no|zero|without|not a single)\s+(?:test\s+)?(?:failures?|failed tests?|failing tests?)\b|\bno longer\s+(?:fails?|failing|failed|blocked)\b|\b(?:0|zero) (?:failed|failures|failing|errors?)\b", re.IGNORECASE)
FAILED_RE = re.compile(r"\b(?:failed|failure|failures|fails)\b|\bfail\b(?!-)", re.IGNORECASE)
BLOCKED_RE = re.compile(r"\bblocked\b|\bcannot proceed\b|\bcan't proceed\b|\bwaiting (?:on|for)\b|\bneeds? (?:your|an?|the) (?:decision|approval|input|answer|credentials|authori[sz]ation)\b", re.IGNORECASE)
NOT_DONE_RE = re.compile(r"\b(?:not|isn't|is not|wasn't|was not|never|cannot be|can't be)\s+(?:yet\s+|fully\s+)?(?:completed?|done|fixed|verified|tested|deployed|merged|finished|resolved|validated|working|live|ready|attempted|run|executed)\b|\bincomplete\b|\bunverified\b", re.IGNORECASE)
PARTIAL_RE = re.compile(r"\bpartial(?:ly)?\b|\broot cause found\b|\bnot yet\b|\bin progress\b|\bstill (?:open|pending|missing)\b", re.IGNORECASE)
COMPLETE_RE = re.compile(r"\b(?:completed?|done|fixed|resolved|implemented|deployed|merged|verified|validated|tested|ready|pass|passed|passes|succeeded|successful|live)\b", re.IGNORECASE)
TEST_CMD = re.compile(r"\b(pytest|npm test|npm run test|yarn test|go test|cargo test|make test|tox|nox|unittest|terraform validate|terraform plan|kubectl .* --dry-run)\b|python3?\s+\S*(?:tests?/|test_)\S*\.py\b")
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
        hl = HEADLINE.match(line)  # concise form: "Groundwork <version> · <PLAYBOOK>"
        if hl:
            fields["playbook"] = hl.group(1)
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
    for part in re.split(r"[+,;]|\s/\s", value):  # "a / b" separates; a bare slash means a path, dropped
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


def classify_state(sentence: str):
    """State word of one status sentence, or None when nothing recognisable is present."""
    t = NO_FAIL.sub(" ", sentence or "")
    if FAILED_RE.search(t):
        return "failed"
    if BLOCKED_RE.search(t):
        return "blocked"
    if NOT_DONE_RE.search(t) or PARTIAL_RE.search(t):
        return "partial"
    if COMPLETE_RE.search(t):
        return "complete"
    return None


def status_paragraph(text: str):
    """The paragraph under a Status / Result heading (or the rest of a 'Status: …' line)."""
    m = STATUS_HEAD.search(text)
    if not m:
        return None
    rest = m.group(1).strip().strip("*").strip()
    if rest:
        return rest
    lines = []
    for ln in text[m.end():].splitlines():
        if not ln.strip():
            if lines:
                break
            continue
        lines.append(ln.strip())
        if len(lines) >= 3:
            break
    return " ".join(lines) if lines else None


def outcome_from_text(text: str) -> str:
    """Model-declared outcome, from the response's own status language (never 'complete' merely
    because a response exists)."""
    m = OVERALL.search(text)
    if m:
        return m.group(1).lower()
    para = status_paragraph(text)
    if para:
        # whole paragraph first: a failure or block stated after a leading "Complete." must win
        state = classify_state(para)
        if state:
            return state
    first_line = next((ln for ln in text.splitlines() if ln.strip()), "")
    b = BOLD_LEAD.match(first_line)
    if b:
        state = classify_state(b.group(1))
        if state:
            return state
    if STATE_LEAD.match(first_line):
        state = classify_state(first_line)
        if state:
            return state
    if NOTHING_LEFT.search(text) and not asks_question(text):  # explicit "Next action: none" = the model declares nothing remains
        head = NO_FAIL.sub(" ", text[:800])
        if FAILED_RE.search(head) or BLOCKED_RE.search(head):
            return classify_state(head) or "unknown"
        return "complete"
    if LEAD_HEAD.search(text):  # Answer / Recommendation / Deliverable / Plan: the playbook's result heading is present
        if asks_question(text):
            return "blocked"
        head = text[:600]
        if FAILED_RE.search(NO_FAIL.sub(" ", head)) or BLOCKED_RE.search(head):
            return classify_state(head) or "unknown"
        return "complete"
    return "unknown"


def asks_question(text: str) -> bool:
    tail = [ln.strip() for ln in text.strip().splitlines() if ln.strip()][-4:]
    return any(ln.endswith("?") for ln in tail)


def parse_execution(value: str):
    """'single agent' -> (single_agent, 0); '3 subagents' -> (subagents, 3); 'agent team' -> (agent_team, None)."""
    v = (value or "").lower()
    mode = next((m for k, m in EXEC_MODES.items() if k in v), "unknown")
    if mode == "single_agent":
        return mode, 0
    n = re.search(r"(\d+)", v)
    return mode, (int(n.group(1)) if n else None)


def build_record(data: dict, text: str) -> dict:
    """One record: `observed` = facts the hook determined itself (transcript, environment, files);
    `declared` = what the model stated in its block and status sentence — recorded, not verified,
    except that agent count / mode / roles are reconciled against observed Agent calls (authoritative)."""
    meta = parse_metadata(text)
    facts = turn_facts(current_turn(data.get("transcript_path", "")))
    if not meta and not facts["tools"]:
        return {}  # conversational reply, no tool use: nothing to record
    execution, exec_count = parse_execution(meta.get("execution", ""))
    count, roles = parse_agents(meta.get("agents", ""))
    if count is None:
        count = exec_count
    # Reconcile with what the hook observed: Agent calls in the transcript are authoritative for the
    # count and the mode; declared roles are kept only when they match that count.
    observed_calls = len(facts["agents"])
    observed_types = labels(", ".join(a["name"] or a["type"] for a in facts["agents"]), 12)
    if observed_calls:
        if count != observed_calls or not roles:
            count = observed_calls
            roles = observed_types
        if execution in ("single_agent", "unknown"):
            execution = "subagents"
    elif execution == "single_agent":
        count, roles = 0, []
    validation_raw = meta.get("validation", "").lower()
    validation = next((v for k, v in VALIDATION_STATES.items() if k in validation_raw), "unknown")
    playbook_raw = (meta.get("playbook") or "").strip("* ").upper().split()
    playbook = playbook_raw[0] if playbook_raw and playbook_raw[0] in PLAYBOOKS else "unknown"
    cwd = data.get("cwd") or os.getcwd()
    return {
        "schema": 2,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": data.get("session_id") or "unknown",
        "prompt_id": data.get("prompt_id") or "unknown",
        "harness": "Groundwork",
        "harness_version": harness_version(),
        "cwd_hash": hashlib.sha256(cwd.encode()).hexdigest()[:12],
        "observed": {
            "profile": label(os.environ.get("GROUNDWORK_PROFILE") or ""),
            "tools": facts["tools"],
            "mcp_servers": facts["mcp_servers"],
            "agent_calls": len(facts["agents"]),
            "agent_types": observed_types,
            "files_changed": facts["files_changed"],
            "tests_run": facts["tests_run"],
            "implementation_performed": facts["implementation_performed"],
            "deployment_performed": facts["deployment_performed"],
        },
        "declared": {
            "block_present": bool(meta),
            "playbook": playbook,
            "execution_mode": execution,
            "agent_count": count,
            "agent_roles": roles[:12],
            "evidence_sources": labels(meta.get("evidence", ""), 8),
            "validation": validation,
            "environment": label(meta.get("environment") or ""),
            "outcome": outcome_from_text(text),
            "clarification_required": asks_question(text),
        },
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
