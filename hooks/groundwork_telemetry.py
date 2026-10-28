#!/usr/bin/env python3
"""Stop / PostToolUse / PostToolUseFailure hook — Groundwork's only audit/telemetry mechanism.

Groundwork has no other audit log. This one script now covers two independent records, kept in
two separate files because their shapes and volumes differ (one per turn vs. one per tool call):

1. Per-turn aggregate (Stop event, unchanged since 1.3.x) -> events.jsonl, schema 2.
   See "Per-turn record" below.
2. Per-tool-call record (PostToolUse / PostToolUseFailure, added in this change) ->
   tool_events.jsonl, its own schema (see "Per-tool-call record" below). Added because Claude
   Code's PostToolUse/PostToolUseFailure hooks (code.claude.com/docs/en/hooks-guide, confirmed
   2026-10-01) give per-call success/failure that the per-turn record cannot: it only ever saw
   tool *names used somewhere in the turn*, never whether an individual call succeeded. This was
   recorded as a known gap in CHANGELOG 2.2.0 ("Investigated Integration Usage Telemetry... not
   reliably supported... no PostToolUse hook exists anywhere in Groundwork") and is what this
   change closes — nothing else about that investigation's wider scope (read/write classification,
   CLI-domain attribution) is implemented here; see docs/ARCHITECTURE.md for the limitation this
   still leaves.

Same append-only JSONL, fail-open pattern as require_material_review.py for both: never blocks,
never prints, never raises past main(). The user's task is primary, telemetry is secondary.

## Per-turn record (Stop)

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

## Per-tool-call record (PostToolUse / PostToolUseFailure)

Trigger: every PostToolUse and PostToolUseFailure event that carries a `tool_name`. Fires once
per tool call — far higher volume than the per-turn record, which is exactly why it is a
separate file: mixing a few-per-turn aggregate with many-per-call rows into one schema/file
would force every reader (scripts/groundwork_report.py, any future one) to branch on shape, and
the day-bucket/profile/playbook dimensions the per-turn schema aggregates by do not exist for a
single tool call.

What is recorded per call: the event's own `tool_name`, `session_id`, `prompt_id`, `tool_use_id`,
which event fired, and the boolean `is_interrupt`. Accuracy signals change (D5): for Bash only, the
command and the first line of `error` are read in memory to set `kind`, `result` and `git_commit`;
neither is stored. For a completed reviewer Agent/Task call, the result text is parsed for its
REVIEW RESULT block and a `review` signal is written (D9). Nothing else from `tool_input` or
`tool_response` is read:
  - `tool`: the tool name Claude Code reports (e.g. "Bash", "Edit", "mcp__github__list_prs"),
    capped to a short length as a defensive bound — the same strings the per-turn record already
    stores in `observed.tools`, so this adds no new exposure;
  - `category`: "builtin" or "mcp", from the same `mcp__<server>__...` prefix test the per-turn
    record already uses to build `observed.mcp_servers`; `mcp_server` carries that server slug
    when `category` is "mcp" (never the full qualified tool name beyond what `tool` already has);
  - `success`: True for PostToolUse, False for PostToolUseFailure;
  - `interrupted`: present, as True, only when a PostToolUseFailure carries `is_interrupt: true`
    (Claude Code's documented flag for a call that ended as an abort rather than as an error the
    tool reported). Such a row still has `success: False`, but it is not a tool failure:
    scripts/groundwork_report.py counts it separately and keeps it out of the success rate;
  - `ts`, `session_id`: same meaning as the per-turn record.
Not recorded, by Claude Code's own design (code.claude.com/docs/en/hooks): a call that is denied
by permissions or rejected before execution (unknown tool, invalid input) fires neither event,
and cancelling a running tool fires no failure event, so such calls leave no failure row. Rows are therefore calls that actually
finished or failed — never a count of everything Claude attempted.
Known limitation: a Bash-invoked CLI integration (gh, kubectl, terraform, …) is not attributable
by name; only MCP-mechanism and built-in-tool usage is classified, as documented in
docs/ARCHITECTURE.md.

Event-shaped signals (openspec/changes/add-accuracy-signals D2): SubagentStop (review result of a
review-shaped agent type), UserPromptSubmit (correction flag; slash commands and harness envelopes
marked skipped) and PostCompact (trigger) append to signals.jsonl through
groundwork_shared.append_signal. No prompt, reply or command text is stored. Any other event
writes nothing.

Both files share the owner-only (0600 file / 0700 dir) permission model and the same off-switch.
Disable with GROUNDWORK_TELEMETRY=off. Path overrides: GROUNDWORK_TELEMETRY_PATH (per-turn file),
GROUNDWORK_TOOL_TELEMETRY_PATH (per-tool-call file), GROUNDWORK_SIGNALS_PATH (signals file).
"""
import calendar
import hashlib
import json
import os
import re
import subprocess
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
    from groundwork_shared import append_signal  # signals.jsonl writer (openspec/changes/add-accuracy-signals)
except Exception:
    def append_signal(_rec):
        pass
try:
    from require_material_review import REVIEW_PATTERN, is_review_call, parse_review_result  # the gate's definitions
except Exception:
    REVIEW_PATTERN, is_review_call, parse_review_result = re.compile(r"(?!x)x"), (lambda *_a: False), (lambda _t: {})

META_HEADING = re.compile(r"^[ \t]*(?:#+[ \t]*|\*\*)?Harness metadata(?:\*\*)?[ \t]*$", re.MULTILINE | re.IGNORECASE)
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
DEPLOY_CMD = re.compile(r"\b(terraform apply|tofu apply|kubectl apply|kubectl rollout|helm (install|upgrade)|gcloud run deploy|gcloud .* deploy|aws deploy|flux reconcile|argocd app sync|docker compose up|docker push)\b")
EXEC_MODES = {"single agent": "single_agent", "single_agent": "single_agent", "subagents": "subagents",
              "subagent": "subagents", "agent team": "agent_team", "agent_team": "agent_team", "team": "agent_team"}
VALIDATION_STATES = {"not verified": "not_verified", "unverified": "not_verified", "not_verified": "not_verified",
                     "partially verified": "partial", "partial": "partial", "verified": "verified"}


TOOL_EVENTS = ("PostToolUse", "PostToolUseFailure")
TOOL_NAME_CAP = 80          # defensive bound only — these strings are already stored unbounded
MCP_SERVER_CAP = 40         # in the per-turn record's `observed.tools` / `mcp_servers` lists


def default_path() -> Path:
    override = os.environ.get("GROUNDWORK_TELEMETRY_PATH")
    if override:
        return Path(os.path.expanduser(override))
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))
    return base / "groundwork" / "telemetry" / "events.jsonl"


def default_tool_path() -> Path:
    override = os.environ.get("GROUNDWORK_TOOL_TELEMETRY_PATH")
    if override:
        return Path(os.path.expanduser(override))
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))
    return base / "groundwork" / "telemetry" / "tool_events.jsonl"


USAGE_TAIL = 256 * 1024        # only the end of usage.jsonl: the newest renders are the ones that matter
CTX_MAX_AGE_S = 15 * 60        # an older reading no longer describes this turn's context


def default_usage_path() -> Path:
    """Same file scripts/groundwork_statusline.py appends to (at most once a minute per session)."""
    override = os.environ.get("GROUNDWORK_USAGE_PATH")
    if override:
        return Path(os.path.expanduser(override))
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))
    return base / "groundwork" / "telemetry" / "usage.jsonl"


COST_MAX_AGE_S = 60            # the statusLine writes at most once a minute; older is another turn's spend


def latest_usage(session_id: str, now: float = None) -> dict:
    """This session's newest statusLine row: ctx_pct if at most 15 min old, cost_usd + its age if at most 60 s old.
    {} without a statusLine row (headless runs, another statusLine)."""
    if not session_id or session_id == "unknown":
        return {}
    now = time.time() if now is None else now
    try:
        path = default_usage_path()
        size = path.stat().st_size
        with open(path, "rb") as f:
            if size > USAGE_TAIL:
                f.seek(size - USAGE_TAIL)
                f.readline()  # drop the partial first line
            lines = f.read().splitlines()
    except Exception:
        return {}
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    for raw in reversed(lines):
        try:
            r = json.loads(raw)
        except Exception:
            continue
        if not isinstance(r, dict) or r.get("session_id") != session_id:
            continue
        try:
            age = now - calendar.timegm(time.strptime(str(r.get("ts")), "%Y-%m-%dT%H:%M:%SZ"))
        except Exception:
            return {}
        out = {}
        if num(r.get("ctx_pct")) and 0 <= r["ctx_pct"] <= 100 and 0 <= age <= CTX_MAX_AGE_S:
            out["ctx_pct"] = round(float(r["ctx_pct"]), 1)
        if num(r.get("cost_usd")) and r["cost_usd"] >= 0 and 0 <= age <= COST_MAX_AGE_S:
            out["cost_usd"] = round(float(r["cost_usd"]), 4)
            out["cost_age_s"] = int(age)
        return out
    return {}


def latest_ctx_pct(session_id: str, now: float = None):
    return latest_usage(session_id, now).get("ctx_pct")


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


def classify_tool(tool_name: str):
    """(category, mcp_server) — the same mcp__<server>__... prefix test turn_facts() already uses
    to build observed.mcp_servers. "builtin" for everything else (Bash, Edit, Read, Agent, …)."""
    if tool_name.startswith("mcp__"):
        server = tool_name[5:].split("__")[0]
        return "mcp", (server[:MCP_SERVER_CAP] if server else "unknown")
    return "builtin", None


def build_tool_record(data: dict, event: str) -> dict:
    """One record per PostToolUse/PostToolUseFailure call: tool name, category, success, ids. Never tool_response
    content. For Bash only, classify_bash() reads the command and the first line of `error` to classify the call and
    its result; neither is stored. {} when there is nothing usable to record (no tool_name)."""
    tool_name = str(data.get("tool_name") or "").strip()
    if not tool_name:
        return {}
    category, server = classify_tool(tool_name)
    record = {
        "schema": 1,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": str(data.get("session_id") or "unknown")[:64],
        "tool": tool_name[:TOOL_NAME_CAP],
        "category": category,
        "success": event != "PostToolUseFailure",
    }
    for key in ("prompt_id", "tool_use_id"):
        if safe_id(data.get(key)):
            record[key] = data[key]
    if server:
        record["mcp_server"] = server
    if event == "PostToolUseFailure" and data.get("is_interrupt") is True:
        record["interrupted"] = True   # an abort, not an error the tool reported (hooks docs)
    if tool_name == "Bash":
        record.update(classify_bash(data, event))
    return record


SAFE_ID = re.compile(r"[\w.:-]{1,100}")


def safe_id(v) -> bool:
    """Ids are stored only when they look like ids, so a malformed payload cannot smuggle text into a record."""
    return isinstance(v, str) and bool(SAFE_ID.fullmatch(v))


# ---------------------------------------------------------------- Bash classification (design D5)
EXIT_LINE = re.compile(r"\AExit code (\d+)\b")  # hooks docs: a Bash command that exited -> first line "Exit code N"
WRAPPERS = {"env", "time", "sudo", "nice", "nohup", "command", "builtin"}
BENIGN = {"cd", "export", "set", "source", ".", "pushd", "popd", "true", "unset", "ulimit"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
PY_TEST_PATH = re.compile(r"(?:^|/)(?:tests?/|test_)[^ ]*\.py$")
KIND_ORDER = ("test", "check", "deploy", "runtime_read")
NOT_A_RUN = {"--help", "-h", "--version", "-V", "--collect-only", "--co"}
NOT_FOUND_CODES = (126, 127)  # the shell could not run the command: not a test failure


def _leading(argv: list) -> list:
    """argv without assignments and wrappers: `env X=1 timeout 60 uv run pytest -q` -> ['pytest', '-q']."""
    a = list(argv)
    while a:
        head = os.path.basename(a[0])
        if ASSIGNMENT.match(a[0]) or head in WRAPPERS:
            a = a[1:]
        elif head == "timeout":
            a = a[1:]
            while a and a[0].startswith("-"):
                a = a[1:]
            a = a[1:]  # the duration
        elif head in ("uv", "poetry", "pdm", "hatch") and len(a) > 1 and a[1] == "run":
            a = a[2:]
        elif head in ("npx", "bunx"):
            a = a[1:]
        else:
            break
    return a


def segment_kind(argv: list):
    a = _leading(argv)
    if not a:
        return None
    exe, rest = os.path.basename(a[0]), a[1:]
    if any(x in NOT_A_RUN for x in rest):
        return None  # pytest --collect-only, --help, --version: nothing was tested or checked
    sub = rest[0] if rest else ""
    if exe in ("pytest", "py.test", "tox", "nox", "bats", "jest", "vitest", "mocha"):
        return "test"
    if re.fullmatch(r"python3?(?:\.\d+)?", exe):
        if rest[:2] in (["-m", "pytest"], ["-m", "unittest"]):
            return "test"
        if rest[:2] in (["-m", "mypy"], ["-m", "ruff"]):
            return "check"
        if sub and not sub.startswith("-") and PY_TEST_PATH.search(sub):
            return "test"
        return None
    if exe in ("go", "cargo") and sub == "test":
        return "test"
    if exe in ("npm", "pnpm", "yarn", "bun") and (sub == "test" or (sub == "run" and len(rest) > 1 and rest[1].startswith("test"))):
        return "test"
    if exe == "make" and sub in ("test", "check"):
        return "test"
    if exe in ("terraform", "tofu") and sub in ("validate", "plan"):
        return "check"
    if exe in ("ruff", "mypy"):
        return "check"
    if exe == "openspec" and sub == "validate":
        return "check"
    if exe == "kubectl":
        if any(x.startswith("--dry-run") for x in rest):
            return "check"
        if sub in ("get", "describe", "logs") or rest[:2] == ["rollout", "status"]:
            return "runtime_read"
    if exe in ("curl", "wget"):
        return "runtime_read"
    if exe == "gh" and (rest[:2] in (["run", "view"], ["run", "watch"], ["pr", "checks"])):
        return "runtime_read"
    if exe == "claude" and ("-p" in rest or "--print" in rest):
        return "runtime_read"
    if DEPLOY_CMD.match(" ".join(a)):
        return "deploy"
    return None


def _is_git_commit(argv: list) -> bool:
    a = _leading(argv)
    if not a or os.path.basename(a[0]) != "git":
        return False
    i = 1
    while i < len(a) and a[i].startswith("-"):
        i += 2 if a[i] in ("-C", "-c", "--git-dir", "--work-tree") else 1
    return i < len(a) and a[i] == "commit"


def _segments(cmd: str):
    """The task gate's own parser, imported lazily: the gate's dependencies stay unchanged (design D5)."""
    try:
        from groundwork_task_gate import split_segments
        return split_segments(cmd)
    except Exception:
        return None


def _status_visible(segs: list, k: int) -> bool:
    """The call's exit status is segment k's own: nothing after it can mask or replace it (verification_match)."""
    s = segs[k]
    later_ok = all(t["prev"] == "&&" for t in segs[k + 1:])
    return s["prev"] in (None, ";", "&&", "\n") and later_ok and s["next"] in (None, "&&", "\n")


def classify_bash(data: dict, event: str) -> dict:
    inp = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    cmd = str(inp.get("command") or "")
    segs = _segments(cmd)
    if segs is None:
        a = cmd.split()
        kind = segment_kind(a) if a else None
        out = {"kind": kind} if kind else {}
        if kind in ("test", "check"):
            out["result"] = "unknown"  # not parsed: no result can be trusted
        return out
    out = {}
    kinds = [segment_kind(s["argv"]) for s in segs]
    if any(_is_git_commit(s["argv"]) and _status_visible(segs, i) for i, s in enumerate(segs)):
        out["git_commit"] = True  # only when the call's own status shows the commit's result (no ||, ;, pipe after it)
    present = [k for k in KIND_ORDER if k in kinds]
    if not present:
        return out
    kind = present[0]
    out["kind"] = kind
    if kind not in ("test", "check"):
        return out
    k = max(i for i, x in enumerate(kinds) if x == kind)  # the last test/check segment decides
    s = segs[k]
    status_visible = _status_visible(segs, k)
    resp = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    if not status_visible or inp.get("run_in_background") is True or data.get("is_interrupt") is True \
            or resp.get("interrupted") is True:
        out["result"] = "unknown"
    elif event == "PostToolUse":
        out["result"] = "pass"
    else:
        m = EXIT_LINE.match(str(data.get("error") or ""))
        code = int(m.group(1)) if m else None
        exe = _leading(s["argv"])
        is_pytest = bool(exe) and (os.path.basename(exe[0]) in ("pytest", "py.test") or exe[1:3] == ["-m", "pytest"])
        special = (exe[:2] in (["terraform", "plan"], ["tofu", "plan"]) and code == 2) or (is_pytest and code == 5)
        earlier_benign = all(not _leading(t["argv"]) or os.path.basename(_leading(t["argv"])[0]) in BENIGN
                             for t in segs[:k])
        if code is None or code == 0 or code in NOT_FOUND_CODES or special or k != len(segs) - 1 or not earlier_benign:
            out["result"] = "unknown"  # another segment may have failed, or the code is not a test failure
        else:
            out["result"] = "fail"
    return out


# ---------------------------------------------------------------- event-shaped signals (design D2, D9, D10)
SIGNAL_EVENTS = ("SubagentStop", "UserPromptSubmit", "PostCompact")
AP = "['\u2019]?"  # straight or curly apostrophe, or none
CORRECTION = re.compile(
    r"(?:^|[.!?]\s+|\b(?:it|this|that|still)\s+)(?:still\s+)?(?:did" + AP + "n" + AP + "t|does" + AP + "n" + AP
    + r"t|did not|does not)\s+work\b"
    r"|\bstill\s+(?:failing|fails|broken)\b"
    r"|\bthat" + AP + r"s\s+(?:wrong|incorrect|not right)\b|\bthat is (?:wrong|incorrect|not right)\b"
    r"|\bnot what i asked\b|\byou broke\b", re.IGNORECASE)
ENVELOPES = ("<task-notification", "<system-reminder", "<agent-message")
CONDITIONAL = re.compile(r"\b(?:if|when|whenever|unless|in case)\b", re.IGNORECASE)  # "if it doesn't work, tell me"


def is_skipped_prompt(prompt: str) -> bool:
    """A slash command or a harness envelope (also how turns Claude Code starts itself arrive): not a user's words."""
    p = prompt or ""
    return p.lstrip().startswith("/") or any(e in p for e in ENVELOPES)


def is_correction(prompt: str) -> bool:
    """Design D10: skip slash commands and harness envelopes; match only the first 5 lines outside ``` fences,
    each at most 300 characters, so pasted logs and code are not read."""
    p = prompt or ""
    if is_skipped_prompt(p):
        return False
    lines, fenced = [], False
    for ln in p.splitlines():
        if ln.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced or not ln.strip():
            continue
        if len(ln) <= 300:
            lines.append(ln)
        if len(lines) >= 5:
            break
    for ln in lines:
        m = CORRECTION.search(ln)
        if m and not CONDITIONAL.search(re.split(r"[.!?;]", ln[:m.start() + 1])[-1]):  # same sentence only
            return True
    return False


def _response_text(resp) -> str:
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        c = resp.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            return "\n".join(str(b.get("text") or "") for b in c if isinstance(b, dict))
    return ""


def signal_record(data: dict, kind: str, **fields) -> dict:
    rec = {"schema": 1, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "session_id": str(data.get("session_id") or "unknown")[:64], "kind": kind}
    if safe_id(data.get("prompt_id")):
        rec["prompt_id"] = data["prompt_id"]
    rec.update(fields)
    return rec


REVIEW_TEXT_CAP = 64 * 1024  # the REVIEW RESULT block ends a reply; a bounded tail keeps parsing fast


def review_fields(text: str) -> dict:
    res = parse_review_result((text or "")[-REVIEW_TEXT_CAP:])
    must_fix = res.get("must_fix")
    if must_fix is None and res.get("verdict") == "approve":
        must_fix = 0  # same rule as the ledger (groundwork_tasks.record_review)
    if must_fix is None and "verdict" not in res:
        return {"parsed": False}
    out = {"parsed": True}
    if "verdict" in res:
        out["verdict"] = res["verdict"]
    if must_fix is not None:
        out["must_fix"] = min(int(must_fix), 1000)
    return out


def tool_review_signal(data: dict, event: str) -> dict:
    """A completed foreground Agent/Task review, by the gate's own definition (design D9)."""
    tool = str(data.get("tool_name") or "")
    inp = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    if event != "PostToolUse" or tool not in ("Agent", "Task") or not is_review_call(tool, inp):
        return {}
    resp = data.get("tool_response")
    if isinstance(resp, dict) and resp.get("status") not in (None, "completed"):
        return {}  # a background launch: its result arrives at SubagentStop
    rec = signal_record(data, "review", source="tool", **review_fields(_response_text(resp)))
    agent_id = resp.get("agentId") if isinstance(resp, dict) else None
    if safe_id(agent_id):
        rec["agent_id"] = agent_id
    return rec


def build_signal(data: dict, event: str) -> dict:
    if event == "SubagentStop":
        agent = str(data.get("agent_type") or "")
        if not REVIEW_PATTERN.search(agent):
            return {}
        rec = signal_record(data, "review", source="subagent_stop",
                            **review_fields(str(data.get("last_assistant_message") or "")))
        if safe_id(data.get("agent_id")):
            rec["agent_id"] = data["agent_id"]
        return rec
    if event == "UserPromptSubmit":
        prompt = str(data.get("prompt") or "")
        if is_skipped_prompt(prompt):  # kept, so Q4 can step over it to the user's next own prompt
            return signal_record(data, "prompt", correction=False, skipped=True)
        return signal_record(data, "prompt", correction=is_correction(prompt))
    if event == "PostCompact":
        trig = str(data.get("trigger") or "")
        return signal_record(data, "compact", trigger=trig if trig in ("manual", "auto") else "unknown")
    return {}


# ---------------------------------------------------------------- per-turn accuracy facts (design D7, D8, D11)
URL_SPAN = re.compile(r"https?://\S+")
CITATION = re.compile(r"(?<![\w/.~:@-])((?:~|/)?[\w.-]+(?:/[\w.-]+)*):(\d{1,7})(?:-(\d{1,7}))?(?![\w:/])")
CITATION_CAP = 50
CITED_FILE_MAX = 5 * 1024 * 1024


def _git_root(cwd: str) -> str:
    try:
        p = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=1)
        return os.path.realpath(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else ""
    except Exception:
        return ""


def check_citations(text: str, cwd: str) -> dict:
    """Counts only: checked (inside cwd or its git top level), resolved (file and both line ends exist), unchecked."""
    checked = resolved = unchecked = 0
    roots = []
    body = URL_SPAN.sub(" ", text or "")
    if not CITATION.search(body):
        return {"checked": 0, "resolved": 0, "unchecked": 0}
    if cwd:
        roots = [os.path.realpath(cwd)]
        top = _git_root(cwd)
        if top and top not in roots:
            roots.append(top)
    seen, line_counts = set(), {}
    for m in CITATION.finditer(body):
        if len(seen) >= CITATION_CAP:
            break
        raw, a, b = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
        if not re.search(r"[A-Za-z]", raw) or (raw, a, b) in seen:
            continue  # "10:30", "3.11:5": not paths
        seen.add((raw, a, b))
        path = os.path.expanduser(raw)
        cands = [os.path.realpath(c) for c in ([path] if os.path.isabs(path) else [os.path.join(r, path) for r in roots])]
        is_inside = lambda c: any(c == r or c.startswith(r + os.sep) for r in roots)
        existing = [c for c in cands if os.path.isfile(c)]
        if existing:
            # a file that exists decides by where it really is: a symlink or ../ out of the project is not checkable
            if not is_inside(existing[0]):
                unchecked += 1
                continue
        elif "/" not in raw or not any(is_inside(c) for c in cands):
            unchecked += 1  # outside the project, or a bare word that is not a file (host:port, node.js:18)
            continue
        if not existing:
            checked += 1  # a project path that does not exist: a wrong citation
            continue
        f = existing[0]
        try:
            if a < 1 or b < a or os.path.getsize(f) > CITED_FILE_MAX:
                raise ValueError("not checkable")  # malformed range, or too large to count
            if f not in line_counts:
                with open(f, "rb") as fh:
                    line_counts[f] = sum(1 for _ in fh)
        except Exception:
            unchecked += 1  # never a false "unresolved"
            continue
        checked += 1
        resolved += 1 if b <= line_counts[f] else 0
    return {"checked": checked, "resolved": resolved, "unchecked": unchecked}


GITHUB_REMOTE = re.compile(r"github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


def committed_this_turn(prompt_id: str) -> bool:
    """A successful Bash `git commit` in this prompt's tool rows (design D8)."""
    if not prompt_id:
        return False
    try:
        path = default_tool_path()
        size = path.stat().st_size
        with open(path, "rb") as f:
            if size > USAGE_TAIL:
                f.seek(size - USAGE_TAIL)
                f.readline()
            for raw in f:
                if b'"git_commit"' not in raw:
                    continue
                try:
                    r = json.loads(raw)
                except Exception:
                    continue
                if r.get("prompt_id") == prompt_id and r.get("git_commit") is True and r.get("success") is True:
                    return True
    except Exception:
        pass
    return False


def commit_facts(cwd: str) -> dict:
    out = {}
    try:
        head = subprocess.run(["git", "-C", cwd, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=1)
        if head.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", head.stdout.strip()):
            out["head"] = head.stdout.strip()
            url = subprocess.run(["git", "-C", cwd, "remote", "get-url", "origin"], capture_output=True, text=True, timeout=1)
            m = GITHUB_REMOTE.search(url.stdout.strip()) if url.returncode == 0 else None
            if m and m.group(1) not in (".", "..") and m.group(2) not in (".", ".."):
                out["repo"] = f"{m.group(1)}/{m.group(2)}"  # owner/repo only; any user:token@ sits before github.com
    except Exception:
        pass
    return out


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
    observed_extra = latest_usage(str(data.get("session_id") or ""))  # absent (not 0) when unknown
    observed_extra["citations"] = check_citations(text, str(data.get("cwd") or ""))
    if committed_this_turn(str(data.get("prompt_id") or "")):
        observed_extra.update(commit_facts(cwd))
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
            **observed_extra,
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


def _append_record(path: Path, record: dict) -> None:
    """Shared owner-only append used by both the per-turn and per-tool-call records — one
    permission model, one place that can get it wrong."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)  # owner-only records
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    if os.environ.get("GROUNDWORK_TELEMETRY", "").lower() == "off":
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            sys.exit(0)
        event = str(data.get("hook_event_name") or "")
        if event in TOOL_EVENTS:
            record = build_tool_record(data, event)
            if record:
                _append_record(default_tool_path(), record)
            review = tool_review_signal(data, event)
            if review:
                append_signal(review)
            sys.exit(0)
        if event in SIGNAL_EVENTS:
            record = build_signal(data, event)
            if record:
                append_signal(record)
            sys.exit(0)
        if event not in ("Stop", ""):  # design D2: any other event writes nothing ("" = older payloads in tests)
            sys.exit(0)
        text = str(data.get("last_assistant_message") or "")
        record = build_record(data, text)
        if not record:
            sys.exit(0)
        _append_record(default_path(), record)
    except SystemExit:
        raise
    except Exception:
        pass  # telemetry must never affect the task
    sys.exit(0)


if __name__ == "__main__":
    main()
