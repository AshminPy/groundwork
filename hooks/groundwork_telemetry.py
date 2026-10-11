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

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from groundwork_shared import TEST_CMD  # shared with require_material_review.py (Groundwork 2.0)
except Exception:
    # Fail-open: an incomplete/partial install must never crash this hook. A pattern that
    # matches nothing just means test-shaped commands stop being detected — degraded, not broken.
    TEST_CMD = re.compile(r"(?!x)x")
try:
    from groundwork_evidence import telemetry_summary, declared_exceeds, declared_label  # evidence receipt (observed estimate)
except Exception:
    telemetry_summary = declared_exceeds = declared_label = None  # fail-open: the evidence fields are simply omitted

# [ \t]* and not \s*: with MULTILINE, \s* spans newlines and a model answer of tens of thousands of blank lines made the search quadratic
META_HEADING = re.compile(r"^[ \t]*(?:#+[ \t]*|\*\*)?Harness metadata(?:\*\*)?[ \t\r]*$", re.MULTILINE | re.IGNORECASE)
MAX_FIELD_LINE = 300  # no metadata line is this long; longer lines are not run through the field patterns at all
_META_KEY = re.compile(r"[A-Za-z][A-Za-z ]*")


def _meta_field(line: str):
    """(key, value) of a `Key: value` line, tolerating a bullet or bold markers, or None. A scan, not one regex: the regex form
    was cubic on a letter followed by thousands of spaces."""
    s = line.strip()
    i, n = 0, len(s)
    if i < n and s[i] in "-*":
        i += 1
    while i < n and s[i] in "* \t":
        i += 1
    j = s.find(":", i)
    if j < 0:
        return None
    key = s[i:j].rstrip(" \t*")
    if not _META_KEY.fullmatch(key):
        return None
    value = s[j + 1:].lstrip(" \t*").rstrip()
    return (key, value) if value else None
# Free text copied from the model's block is stored only if it looks like a short label:
# letters/digits/space/_/- and at most 32 chars. Anything else (a path, an @, a token-shaped
# string, a sentence) is dropped — identifiers and labels only, never raw content.
LABEL = re.compile(r"^[a-z][a-z0-9 _:-]{0,31}$")  # ":" allowed for agent ids like ecc:code-reviewer
TOKEN_SHAPED = re.compile(r"[a-z0-9_-]*\d[a-z0-9_-]*")  # a "word" containing a digit; long ones look like keys
PLAYBOOKS = {"RESEARCH", "EXPLAIN", "DESIGN", "PLAN", "IMPLEMENT", "TROUBLESHOOT", "VALIDATE", "AUDIT", "DEPLOY", "DOCUMENT"}
TAIL_CHUNK = 256 * 1024          # first backward read; doubles each step
TAIL_CAP = 32 * 1024 * 1024      # never read more than this from the end of the transcript
TAIL_STEP_CAP = 2 * 1024 * 1024  # no chunk is larger than this, so the deadline is looked at often enough
HOOK_START = time.monotonic()    # the Stop hook has a 10 s timeout (scripts/merge_settings.py)
HOOK_BUDGET_S = 7.0              # evidence is derived only with time left under this, so it can never cost the existing record
EVIDENCE_BUDGET_S = 3.0          # the most derive_evidence may use
MIN_EVIDENCE_S = 0.5             # with less than this left, evidence is not even started (its set-up pass over the turn is not free)
HEADLINE = re.compile(r"^\s*Groundwork\s+\S+\s*[·\-–—|]\s*([A-Za-z]+)\s*$", re.IGNORECASE)  # "Groundwork 1.3.2 · IMPLEMENT"
# Outcome — model-declared, read from the response's own status language (output-contract.md Layer 1
# and the playbooks' Status / Result vocabularies). Precedence inside a sentence: failed > blocked >
# partial > complete; "not done"-style negations count as partial; nothing recognisable -> unknown.
OVERALL = re.compile(r"Overall:\s{0,20}\**\s{0,20}(COMPLETE|PARTIAL|BLOCKED|PLANNED|FAILED)", re.IGNORECASE)  # runs of blanks are bounded: adjacent \s* were quadratic on a model answer that starts with 20,000 spaces
STATUS_HEAD = re.compile(r"(?:^|\n)[ \t]{0,20}(?:#+[ \t]{0,20})?\**[ \t]{0,20}(?:Status|Result)[ \t]{0,20}\**[ \t]{0,20}:?[ \t]{0,20}\**[ \t]{0,20}(.*)", re.IGNORECASE)
NOTHING_LEFT = re.compile(r"\b(?:next(?: action| step)?|your move|remaining|open items?)\s*\**\s*:\s*\**\s*(?:none|nothing)\b", re.IGNORECASE)
LEAD_HEAD = re.compile(r"(?:^|\n)[ \t]{0,20}(?:#+[ \t]{0,20})?\**[ \t]{0,20}(?:Answer|Recommendation|Deliverable|Plan|Goal)[ \t]{0,20}\**[ \t]{0,20}:?", re.IGNORECASE)
BOLD_LEAD = re.compile(r"^\s*\*\*(?:(?:my )?(?:call|finding|verdict|answer|result|status)\s*:\s*)?(.+?)\*\*", re.IGNORECASE)
# A plain opening line that starts with a state word is explicit status language too ("Complete. subtract() added…").
STATE_LEAD = re.compile(r"^\s*(?:complete[d]?|partial(?:ly)?|blocked|failed|fixed|done|deployed|resolved|root cause found|not verified|pass|fail|verified)\b[.:—-]", re.IGNORECASE)
NO_FAIL = re.compile(r"\b(?:no|zero|without|not a single)\s+(?:test\s+)?(?:failures?|failed tests?|failing tests?)\b|\bno longer\s+(?:fails?|failing|failed|blocked)\b|\b(?:0|zero) (?:failed|failures|failing|errors?)\b", re.IGNORECASE)
FAILED_RE = re.compile(r"\b(?:failed|failure|failures|fails)\b|\bfail\b(?!-)", re.IGNORECASE)
BLOCKED_RE = re.compile(r"\bblocked\b|\bcannot proceed\b|\bcan't proceed\b|\bwaiting (?:on|for)\b|\bneeds? (?:your|an?|the) (?:decision|approval|input|answer|credentials|authori[sz]ation)\b", re.IGNORECASE)
NOT_DONE_RE = re.compile(r"\b(?:not|isn't|is not|wasn't|was not|never|cannot be|can't be)\s+(?:yet\s+|fully\s+)?(?:completed?|done|fixed|verified|tested|deployed|merged|finished|resolved|validated|working|live|ready|attempted|run|executed)\b|\bincomplete\b|\bunverified\b", re.IGNORECASE)
PARTIAL_RE = re.compile(r"\bpartial(?:ly)?\b|\broot cause found\b|\bnot yet\b|\bin progress\b|\bstill (?:open|pending|missing)\b", re.IGNORECASE)
COMPLETE_RE = re.compile(r"\b(?:completed?|done|fixed|resolved|implemented|deployed|merged|verified|validated|tested|ready|pass|passed|passes|succeeded|successful|live)\b", re.IGNORECASE)
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
        if len(line) > MAX_FIELD_LINE:
            if fields:
                break
            continue
        hl = HEADLINE.match(line)  # concise form: "Groundwork <version> · <PLAYBOOK>"
        if hl:
            fields["playbook"] = hl.group(1)
            continue
        f = _meta_field(line)
        if not f:
            if fields:
                break
            continue
        fields[f[0].strip().lower()] = f[1].strip().strip("*")
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
    if e.get("type") != "user" or e.get("isSidechain") or e.get("isMeta") or e.get("isCompactSummary"):
        return False  # hook feedback, a context-compaction summary (it can fall mid-turn) and other synthetic entries do not start a turn
    origin = e.get("origin")
    if isinstance(origin, dict) and origin.get("kind") != "human":
        return False  # task notifications and sub-agent hand-backs do not start a turn either
    content = (e.get("message") or {}).get("content")
    return not (isinstance(content, list) and any(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content))


# The summariser request that Claude Code sends as a user entry when it compacts the context (read from real transcripts of 2.1.285 to 2.1.296,
# entrypoint remote_mobile; UNVERIFIED for other versions and entrypoints). It is not what the person typed and the turn goes on after the compaction.
_COMPACTION_PROMPT = "Below is a conversation log from a Claude Code coding session"


def _entry_text(e: dict) -> str:
    content = (e.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(b.get("text", "")) for b in content[:3] if isinstance(b, dict))
    return ""


def is_compaction_request(entries: list, i: int) -> bool:
    """Is entries[i] the summariser request of a context compaction? By its opening words, or because it is SDK-originated and a compaction
    boundary follows within 200 entries before the model uses any tool or another prompt arrives (an `sdk` entry alone is not enough: `claude -p` prompts are `sdk` too)."""
    e = entries[i]
    if e.get("turnOrigin") != "sdk":
        return False  # a typed prompt may quote the summariser's words; only an SDK-originated entry is a request
    if _entry_text(e).lstrip().startswith(_COMPACTION_PROMPT):
        return True
    for later in entries[i + 1:i + 201]:  # bookkeeping entries (attachment, last-prompt, …) sit between the request and the boundary: 34 to 37 entries in the real ones
        if later.get("subtype") == "compact_boundary" or later.get("isCompactSummary"):
            return True
        content = (later.get("message") or {}).get("content")
        if later.get("type") == "assistant" and isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_use" for b in content):
            return False
        if is_human_prompt(later):
            return False  # another prompt ends the look-ahead
    return False


def current_turn(transcript_path: str, deadline: float | None = None) -> list:
    """Entries after the last human prompt (a 'user' entry that carries no tool_result).

    Reads the transcript backwards in growing chunks (each chunk is parsed once, never again) and stops at the first
    human prompt it meets, so cost follows the size of the current turn, not of the whole session. At most TAIL_CAP
    bytes are read; a turn longer than that contributes only its tail (facts are then a lower bound, which is acceptable
    for aggregate reporting). With a `deadline` (time.monotonic()), reading stops there and nothing is returned: the
    record is then written without observed facts, exactly as for an unreadable transcript."""
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as f:
            pos, step, carry, entries = size, TAIL_CHUNK, b"", []
            while True:
                if deadline is not None and time.monotonic() > deadline:
                    return []
                take = min(step, pos, TAIL_CAP - (size - pos))  # never more than TAIL_CAP in total
                pos -= take
                f.seek(pos)
                lines = (f.read(take) + carry).split(b"\n")
                if pos > 0:
                    carry, lines = lines[0], lines[1:]  # the first piece may be a partial line; it completes with the next, older chunk
                else:
                    carry = b""
                parsed = []
                for raw in lines:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        e = json.loads(raw)
                    except Exception:
                        continue
                    if isinstance(e, dict):
                        parsed.append(e)
                entries = parsed + entries
                for i in range(len(parsed) - 1, -1, -1):
                    if is_human_prompt(parsed[i]) and not is_compaction_request(entries, i):
                        return entries[i:]
                if pos == 0 or size - pos >= TAIL_CAP:
                    return entries
                step = min(step * 2, TAIL_STEP_CAP)
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
    entries = current_turn(data.get("transcript_path", ""), deadline=HOOK_START + HOOK_BUDGET_S)
    facts = turn_facts(entries)
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
    # Evidence confidence is a best-effort estimate derived from the transcript (hooks/groundwork_evidence.py; its
    # docstring lists the known gaps), recorded as a label plus counts/booleans only — never a path, URL or command.
    # The model's own stated label is recorded separately under `declared`; the comparison is a derived fact, not
    # proof of an over-claim. Additive and fail-open.
    estimate, ev_obs = None, {}
    time_left = HOOK_BUDGET_S - (time.monotonic() - HOOK_START)
    if telemetry_summary is not None and entries and time_left >= MIN_EVIDENCE_S:  # an unreadable (or too slow to read) transcript is UNKNOWN: record no observed fact at all
        try:
            ev = telemetry_summary(entries, budget_s=min(EVIDENCE_BUDGET_S, time_left))
            estimate = ev["confidence"]
            ev_obs = {"evidence_confidence": estimate, "evidence_signals": ev["signals"]}
        except Exception:
            estimate, ev_obs = None, {}
    stated_raw = meta.get("confidence") or meta.get("evidence confidence") or ""
    if declared_label is not None:
        declared_conf = declared_label(stated_raw) or "unknown"  # tolerant: "High.", "**HIGH**", "MEDIUM/HIGH"
    else:
        stated = stated_raw.strip().strip("*").split()
        declared_conf = stated[0].upper() if stated and stated[0].upper() in ("NONE", "LOW", "MEDIUM", "HIGH") else "unknown"
    if estimate is not None and declared_exceeds is not None:
        ev_obs["declared_confidence_exceeds_observed"] = declared_exceeds(declared_conf, estimate)
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
            **ev_obs,
        },
        "declared": {
            "block_present": bool(meta),
            "playbook": playbook,
            "execution_mode": execution,
            "agent_count": count,
            "agent_roles": roles[:12],
            "evidence_sources": labels(meta.get("evidence", ""), 8),
            "evidence_confidence": declared_conf.lower(),
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
