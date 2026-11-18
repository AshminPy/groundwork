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
  - when the turn changed files (Edit / Write / MultiEdit / NotebookEdit), an `Evidence & references`
    section (or `Evidence`) with at least one URL, file:line or file path inside it: a reference
    anywhere else is not enough (34 of 40 saved benchmark answers cited file:line only inline). Other
    turns follow the contract's "only when the conclusion depends on sources" (owner, 2026-10-31,
    openspec/changes/compact-reply-format: the section on every reply was noise);
  - harness metadata: the one-line form or the older four-line block;
  - every repository citation outside code fences resolves: a `dir/file.ext` path whose top-level
    directory exists in the repository must exist on disk or in HEAD, and a `:line` or `:a-b` must be
    inside the file. A bare `file.ext:line` is range-checked when exactly one repository file has
    that name. Absolute, `~/` and URL paths, and paths whose top directory is not in the repository,
    are not checked, so citations of other checkouts or illustrative paths never block
    (openspec/changes/harden-autonomy-evidence-review, evidence-validation).
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
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from groundwork_telemetry import META_HEADING, current_turn, has_metadata, turn_facts  # shared transcript parsing
except Exception:  # a missing sibling must not break the session
    META_HEADING = current_turn = has_metadata = turn_facts = None
try:
    from groundwork_shared import mark_turn_start, turn_tools  # tool use without a transcript (telemetry fallback)
except Exception:
    mark_turn_start = turn_tools = None

BOOKKEEPING = {"ToolSearch", "TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet"}
BOOKKEEPING_PREFIXES = ("mcp__ccd_turn__",)
FILE_CHANGING = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

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
    "plain-language result first; a `Technical details` section (evidence only, no restated result) "
    "when commands ran; an `Evidence & references` section with at least one link or file:line when "
    "files changed or the conclusion depends on sources; and one last line "
    "`Harness metadata · Groundwork <version> · <PLAYBOOK> · <execution> · evidence: <types> · validation: <state>`. "
    "State each fact once and do not repeat a recap the app already shows. A Stop hook checks this and asks once if a part is missing."
)
MISSING_TEXT = {
    "explanation": "a plain-language result first (the reply opens with a section heading instead)",
    "technical_details": "a `Technical details` section (commands ran this turn)",
    "evidence": "an `Evidence & references` section listing at least one link or file:line for what changed (files changed this turn)",
    "metadata": "the one-line `Harness metadata · Groundwork <version> · <PLAYBOOK> · …` at the end",
}

# A repository citation: `path/to/file.ext`, `file.ext:12` or `path/file.ext:12-30`, starting at a token start.
CITATION = re.compile(r"(?<![\w./~:@-])((?:[\w.-]{1,100}/){0,20}[\w-][\w.-]{0,100}\.[A-Za-z]\w{0,9})(?::(\d{1,7})(?:-(\d{1,7}))?)?")
URL = re.compile(r"[A-Za-z][\w+.-]{0,20}://\S+")
FENCE = re.compile(r"^[ \t]*```.*?^[ \t]*```[ \t]*$", re.MULTILINE | re.DOTALL)
MAX_CITATIONS = 60
MAX_LINES_FILE = 20_000_000  # bytes; larger files are not line-counted


def _git(root: str, *args) -> str | None:
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, errors="replace", timeout=5,
                           stdin=subprocess.DEVNULL, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except Exception:
        return None
    return r.stdout if r.returncode == 0 else None


def _line_count(path: Path) -> int | None:
    try:
        if path.stat().st_size > MAX_LINES_FILE:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    return data.count(b"\n") + (0 if not data or data.endswith(b"\n") else 1)


def citation_problems(text: str, cwd: str) -> list:
    """Cited repository files that do not exist, and cited lines outside the file (evidence-validation)."""
    if not cwd or not os.path.isdir(cwd):
        return []
    root = (_git(cwd, "rev-parse", "--show-toplevel") or "").strip()
    if not root:
        return []
    body = URL.sub(" ", FENCE.sub(" ", text or ""))
    problems, seen, names = [], set(), None
    for m in CITATION.finditer(body):
        rel, start, end = m.group(1), m.group(2), m.group(3)
        cite = m.group(0)
        if cite in seen:
            continue
        seen.add(cite)
        if len(seen) > MAX_CITATIONS:
            break
        rel = rel[2:] if rel.startswith("./") else rel
        if "/" in rel:
            top = rel.split("/", 1)[0]
            if top in (".", "..") or not os.path.isdir(os.path.join(root, top)):
                continue  # another checkout, an absolute-looking fragment or an illustrative path
            path = Path(root, rel)
            if not path.is_file():
                if _git(root, "cat-file", "-e", f"HEAD:{rel}") is None:
                    problems.append(f"`{cite}` (no such file in {os.path.basename(root)})")
                continue
        else:
            if not start:
                continue  # a bare name without a line is too ambiguous to check
            if names is None:
                names = {}
                listed = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard") or ""
                for f in listed.split("\0"):
                    if f:
                        names.setdefault(f.rsplit("/", 1)[-1], []).append(f)
            matches = names.get(rel, [])
            if len(matches) != 1:
                continue
            path = Path(root, matches[0])
        if not start:
            continue
        lines = _line_count(path)
        if lines is None:
            continue
        a, b = int(start), int(end) if end else int(start)
        if a < 1 or b < a:
            problems.append(f"`{cite}` (not a valid line range)")
        elif b > lines:
            problems.append(f"`{cite}` (the file has {lines} line{'' if lines == 1 else 's'})")
    return problems


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
            or (META_HEADING is not None and META_HEADING.match(first)) or "HARNESS METADATA" in first.upper()
            or (has_metadata is not None and has_metadata(first))):
        missing.append("explanation")
    if "Bash" in used and not TECH_HEAD.search(text):
        missing.append("technical_details")
    if FILE_CHANGING.intersection(used) and not evidence_ok(text):
        missing.append("evidence")
    if has_metadata is None or not has_metadata(text):
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
    try:
        cited = citation_problems(text, str(data.get("cwd") or "")) if real_tools(tools) else []
    except Exception:
        cited = []  # the citation check must never break the format check
    if not missing and not cited:
        return
    reason = "Groundwork reply check: "
    if missing:
        parts = "; ".join(MISSING_TEXT[m] for m in missing)
        reason += (f"this turn used tools, but the final reply is missing: {parts}. Add only the missing parts in "
                   "a short follow-up message. Do not repeat the rest of the reply and do not re-run tools.")
    if cited:
        reason += ((" " if missing else "") + "These cited repository references do not resolve: " +
                   "; ".join(cited) + ". Correct or remove each one in a short follow-up message (check the file "
                   "and line first). For a file in another checkout, cite its absolute path.")
    print(json.dumps({"decision": "block", "reason": reason}))


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
