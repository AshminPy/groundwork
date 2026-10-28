#!/usr/bin/env python3
"""UserPromptSubmit / Stop hook — enforces the reply format of output-contract.md.

Why a hook: the format lives in rules and playbooks, and nothing loads a playbook by itself, so
replies drift (feature 6 of openspec/changes/core-evidence-continuity). Rules suggest; this checks.

UserPromptSubmit: adds a short format reminder as context. When a deliberately conservative
keyword route picks exactly one task category, it also adds that playbook's "Output Format"
section (read from <config>/groundwork/playbooks/). An ambiguous or unmatched prompt gets the
reminder only, and a slash command gets nothing.

Stop: when the turn used a real tool (bookkeeping tools such as ToolSearch do not count), the
final reply (`last_assistant_message`) must have:
  - a plain-language result first (not a Technical details / Evidence / metadata heading);
  - a `Technical details` section when Bash ran;
  - an `Evidence & references` section (or `Evidence`) with at least one URL, file:line or
    file path inside it, so every reply carries the sources a reader can check and reuse. The owner
    asked for this after first measuring that 34 of 40 saved benchmark answers cited file:line only
    inline: a reference anywhere is not enough, it must be in the section;
  - the `HARNESS METADATA` block.
If anything is missing it returns `decision: "block"` once, naming the missing parts; Claude
then adds them. It never asks twice: when `stop_hook_active` is true (Claude is already
continuing because of a Stop hook) it does nothing, so it cannot loop
(code.claude.com/docs/en/hooks, Stop input). Chat turns with no tool use are never touched.

Fail-open like every Groundwork hook: bad input, an unreadable transcript or any error means
no output and exit 0. GROUNDWORK_REPLY_CHECK=off disables both events. Stores nothing.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
_SESSION = ""
_TOOL_USE_ID = ""
_PROMPT_ID = ""


def _record(decision: str, cause: str = "policy") -> None:
    """Telemetry of this hook's own decision. Imported here, inside try, so a missing or broken module can never
    stop the decision being printed (openspec/changes/add-accuracy-signals D6)."""
    try:
        from groundwork_shared import record_guardrail
        record_guardrail(_SESSION, _PROMPT_ID, "reply_check", decision, cause, _TOOL_USE_ID)
    except BaseException:  # nothing raised while recording may change the decision
        pass


try:
    from groundwork_telemetry import META_HEADING, current_turn, turn_facts  # shared transcript parsing
except Exception:  # a missing sibling must not break the session
    META_HEADING = current_turn = turn_facts = None
try:
    from groundwork_shared import mark_turn_start, turn_tools  # tool use without a transcript (telemetry fallback)
except Exception:
    mark_turn_start = turn_tools = None

BOOKKEEPING = {"ToolSearch", "TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet"}
BOOKKEEPING_PREFIXES = ("mcp__ccd_turn__",)

HEADING = r"^[ \t]*(?:#{{1,6}}[ \t]*)?\**[ \t]*(?:{name})[ \t]*\**[ \t]*:?[ \t]*\**[ \t]*$"
TECH_HEAD = re.compile(HEADING.format(name=r"Technical details"), re.MULTILINE | re.IGNORECASE)
EVID_HEAD = re.compile(HEADING.format(name=r"Evidence(?:[ \t]*(?:&|and)[ \t]*references)?"), re.MULTILINE | re.IGNORECASE)
# Every repeat is bounded and the file:line form starts only at a token start: an unbounded form
# backtracked cubically on one long token (a pasted hash took >80 s at 4,000 characters, review finding).
# The Evidence section ends at the next heading line or code fence (so the metadata block never counts).
SECTION_END = re.compile(r"^[ \t]*(?:#{1,6}[ \t]+\S|\*\*[^*\n]{1,80}\*\*[ \t]*:?[ \t]*$|```)", re.MULTILINE)
REFERENCE = re.compile(
    r"https?://\S+"                                         # a link
    r"|(?<![\w./-])[\w./-]{1,200}\.\w{1,10}:\d+"             # file:line (file:line-range too)
    r"|`[^`\s]{0,200}/[^`\s]{0,200}\.\w{1,10}`"               # a `path/with/slash.ext`
)

REMINDER = (
    "[Groundwork reply format] If this turn uses tools, the final reply has, in order: the "
    "plain-language result first; a `Technical details` section when commands ran; an "
    "`Evidence & references` section with at least one link or file:line; and the fenced "
    "`HARNESS METADATA` block at the end. A Stop hook checks this and asks once if a part is missing."
)
MISSING_TEXT = {
    "explanation": "a plain-language result first (the reply opens with a section heading instead)",
    "technical_details": "a `Technical details` section (commands ran this turn)",
    "evidence": "an `Evidence & references` section listing at least one link or file:line that supports the result",
    "metadata": "the fenced `HARNESS METADATA` block at the end",
}

ROUTES = {  # one category must match alone; any overlap means "not confident" and routes nothing
    "TROUBLESHOOT": r"\b(?:debug\w*|crash\w*|errors?|exceptions?|traceback|stack trace|fail(?:s|ed|ing|ure)?|broken|not working|root cause|rca|incident|outage)\b",
    "DEPLOY": r"\b(?:deploy\w*|roll ?out|roll ?back|rollback)\b",
    "IMPLEMENT": r"\b(?:implement\w*|refactor\w*|add (?:a|an|the) (?:feature|function|flag|option|test|endpoint|script)|write (?:a|the) (?:script|function|test))\b",
    "VALIDATE": r"\b(?:validate|verify|prove (?:it|that)|confirm (?:it|that) works|smoke test|acceptance test|regression test)\b",
    "AUDIT": r"\b(?:review|audit)\b",
    "DOCUMENT": r"\b(?:readme|runbook|write ?up|document (?:this|it|the)|changelog|executive summary)\b",
    "RESEARCH": r"\b(?:research|compare (?:tools|libraries|options|vendors)|what(?:'s| is) the latest)\b",
    "EXPLAIN": r"\b(?:explain\w*|what (?:is|are|does)|how (?:does|do)|why (?:does|is))\b",
    "DESIGN": r"\b(?:design|architecture|architect)\b",
    "PLAN": r"\b(?:plan|roadmap)\b",
}
ROUTE_RES = {cat: re.compile(rx, re.IGNORECASE) for cat, rx in ROUTES.items()}
FORMAT_CAP = 800


def real_tools(tools) -> list:
    return [t for t in tools or [] if t not in BOOKKEEPING and not str(t).startswith(BOOKKEEPING_PREFIXES)]


def evidence_ok(text: str) -> bool:
    """An Evidence heading followed, before the next section or code fence, by at least one reference."""
    for m in EVID_HEAD.finditer(text):
        end = SECTION_END.search(text, m.end() + 1)
        if REFERENCE.search(text[m.end():end.start() if end else len(text)][:20_000]):
            return True
    return False


def check_reply(text: str, tools) -> list:
    """Missing parts of a final reply, in reading order. Empty when the turn used no real tool."""
    used = real_tools(tools)
    if not used:
        return []
    text = text or ""
    missing = []
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    if (not first or first.strip().startswith("```") or TECH_HEAD.match(first) or EVID_HEAD.match(first)
            or (META_HEADING is not None and META_HEADING.match(first)) or "HARNESS METADATA" in first.upper()):
        missing.append("explanation")
    if "Bash" in used and not TECH_HEAD.search(text):
        missing.append("technical_details")
    if not evidence_ok(text):
        missing.append("evidence")
    if META_HEADING is None or not META_HEADING.search(text):
        missing.append("metadata")
    return missing


def classify_prompt(prompt: str):
    """The one task category a prompt clearly asks for, or None when unclear."""
    p = (prompt or "").strip()
    if not p or p.startswith("/"):
        return None
    hits = [cat for cat, rx in ROUTE_RES.items() if rx.search(p)]
    return hits[0] if len(hits) == 1 else None


def config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))


def output_format(category: str) -> str:
    try:
        text = (config_dir() / "groundwork" / "playbooks" / f"{category.lower()}.md").read_text()
    except Exception:
        return ""
    m = re.search(r"^## Output Format[ \t]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip()[:FORMAT_CAP] if m else ""


def on_prompt(data: dict) -> None:
    if mark_turn_start is not None:
        try:
            mark_turn_start(str(data.get("session_id") or ""))
        except Exception:
            pass  # only the no-transcript fallback depends on it
    prompt = str(data.get("prompt") or "")
    if prompt.strip().startswith("/"):
        return
    ctx = REMINDER
    category = classify_prompt(prompt)
    fmt = output_format(category) if category else ""
    if fmt:
        ctx += f"\n[Groundwork playbook {category} — Output Format]\n{fmt}"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}}))


def on_stop(data: dict) -> None:
    if data.get("stop_hook_active") or turn_tools is None:
        return
    tools = turn_tools(data, current_turn, turn_facts)
    text = data.get("last_assistant_message")
    if not isinstance(text, str) or not text.strip():
        return  # no reply text to check (e.g. an older Claude Code without the field): fail open
    missing = check_reply(text, tools)
    if not missing:
        return
    parts = "; ".join(MISSING_TEXT[m] for m in missing)
    reason = (f"Groundwork reply check: this turn used tools, but the final reply is missing: {parts}. "
              "Add only the missing parts in a short follow-up message. Do not repeat the rest of the "
              "reply and do not re-run tools.")
    global _SESSION, _PROMPT_ID
    _SESSION = data.get("session_id")
    _PROMPT_ID = data.get("prompt_id")
    print(json.dumps({"decision": "block", "reason": reason}), flush=True)
    _record("block")  # after the decision is out (design D6)


def main() -> None:
    if os.environ.get("GROUNDWORK_REPLY_CHECK", "").lower() == "off":
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            sys.exit(0)
        event = str(data.get("hook_event_name") or "")
        if event == "UserPromptSubmit":
            on_prompt(data)
        elif event == "Stop":
            on_stop(data)
    except SystemExit:
        raise
    except Exception:
        pass  # the reply check must never break a session
    sys.exit(0)


if __name__ == "__main__":
    main()
