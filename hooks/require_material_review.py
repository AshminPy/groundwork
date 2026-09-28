#!/usr/bin/env python3
"""Stop hook — deterministically require an independent fresh-context review before
a MATERIAL (spec-driven) change is allowed to finish, and (Groundwork 2.0, Decision D3)
require that a review's own MUST FIX findings are followed by a FRESH independent
re-review of the resulting change — not merely by an edit and a re-run of validation —
before the change counts as reviewed.

Groundwork extension (not part of ECC or OpenSpec). Neither enforces review: ECC's
reviewer agents are invocable but nothing dispatches them, and OpenSpec tracks task
checkboxes only. Rather than trust a self-declared "MATERIAL" tier (gameable) or a
self-declared "I reviewed it" claim, this hook uses facts it can check directly:

  1. Was an OpenSpec change fully implemented this session? (every checkbox in its
     tasks.md is "[x]", and the change directory is uncommitted/untracked per git —
     i.e. it is this session's own work, not old already-reviewed work.)
  2. Did a reviewer-shaped tool call happen anywhere in this session's transcript?
     - an `Agent` (or legacy `Task`) call whose `subagent_type` or `name` contains
       "review" — this covers ECC/project/user reviewer subagents AND Agent Team
       reviewer teammates, which current Claude Code (>= 2.1.178) spawns through the
       same Agent tool with a `name` and no reviewer-specific `subagent_type`
       (docs/en/agent-teams, docs/en/sub-agents). The free-text `description` is
       deliberately NOT matched: "Review existing tests before implementing" on an
       Explore call is not a review, and matching it would let the gate be satisfied
       by coincidence (caught by independent review of 1.1.0);
     - or a `Skill` call whose skill name contains "review".
     This deliberately does not pin one specific reviewer name, so reviewer
     selection stays contextual per engineering-workflow.md.
  3. (2.0) Did that reviewer's OWN output contain a structured "REVIEW RESULT" block
     (`output-contract.md`, mirroring the already-proven "Harness metadata" block
     format) stating a MUST-FIX count? If the MOST RECENT review-shaped call's own
     result reports MUST-FIX > 0, the gate blocks — an edit and a re-run of the
     affected validation afterward are NOT, by themselves, sufficient evidence the
     finding was resolved (this was the first-pass design's known weakness, fixed
     here per explicit owner instruction): only a FRESH review-shaped call whose own
     result reports zero remaining findings (or approves) clears the gate, because the
     decision always looks at the transcript's *most recent* review result, so a
     second review is structurally required whenever the most recent one found a
     problem. When a reviewer does not emit the block (most reviewers do not know
     this format yet — RUNTIME VALIDATION REQUIRED, see docs/VALIDATION.md), this
     degrades gracefully to the original presence-only check, never stricter than
     before. What this hook genuinely CANNOT establish, and does not pretend to:
     that the fix was semantically correct, or that a second reviewer's approval
     without the block was independent — it only proves the review-shaped calls and
     their own self-reported verdicts that actually appear in the transcript.

If (1) is true and no reviewer-shaped call exists, or the most recent one's own result
reports unresolved MUST FIX findings, the Stop is blocked with the concrete change name
and exactly what has/hasn't been observed. It re-checks on every Stop, so once a
qualifying review is dispatched the block clears itself — no state file, no
self-declaration, no findings database. Claude Code itself caps a Stop hook at 8
consecutive blocks (docs/en/hooks §Stop), so a session can never be trapped; the
transcript may also lag the in-memory turn, in which case the next Stop sees the call.

Fail-open on any error (missing git, unreadable transcript, no repo): never block a
session over a broken guard.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Imported separately (not one combined try/except): a stale or partially-installed
# groundwork_shared.py that is missing just one of these two names must not also take down
# the other — each degrades independently to its own safe fail-open default.
try:
    from groundwork_shared import dirty_change_names  # shared with groundwork_session_snapshot.py
except Exception:
    # Fail-open: an incomplete/partial install must never crash this hook — no dirty
    # changes found means no review candidates, the same safe outcome as every other
    # fail-open path below.
    def dirty_change_names(cwd: str) -> set[str]:
        return set()
try:
    from groundwork_shared import TEST_CMD  # shared with groundwork_telemetry.py
except Exception:
    # A TEST_CMD that matches nothing just means "validation re-run" evidence is not
    # detected (degraded, not broken) — never a crash.
    TEST_CMD = re.compile(r"(?!x)x")

# (?<![a-z]) so "preview"/"previewer" never count; "reviewer", "code-review", "orch-review" still do.
REVIEW_PATTERN = re.compile(r"(?<![a-zA-Z])review", re.IGNORECASE)
CHECKBOX_UNDONE = re.compile(r"^\s*-\s*\[\s\]", re.MULTILINE)
CHECKBOX_ANY = re.compile(r"^\s*-\s*\[[ xX]\]", re.MULTILINE)
AGENT_TOOLS = ("Task", "Agent")
AGENT_REVIEW_FIELDS = ("subagent_type", "name")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")

# A reviewer may optionally emit this short structured block (same shape/tolerance as the
# existing "Harness metadata" block groundwork_telemetry.py already parses) naming its
# verdict and MUST-FIX count. Absence is handled gracefully — see module docstring point 3.
REVIEW_RESULT_HEADING = re.compile(r"^\s*(?:#+\s*|\*\*)?REVIEW RESULT(?:\*\*)?\s*$", re.MULTILINE | re.IGNORECASE)
# Field names may contain a hyphen ("Must-fix") unlike the Harness metadata block's fields,
# which never do — the char class is widened from that block's parser accordingly.
REVIEW_RESULT_FIELD = re.compile(r"^\s*(?:[-*]\s*)?\**\s*([A-Za-z][A-Za-z -]*?)\s*\**\s*:\s*\**\s*(.+?)\s*$")


def find_complete_unreviewed_changes(cwd: str) -> list[str]:
    """Return names of openspec changes that are fully task-complete AND look like
    this session's own uncommitted work (not old, already-reviewed, committed work)."""
    changes_dir = Path(cwd) / "openspec" / "changes"
    if not changes_dir.is_dir():
        return []

    dirty = dirty_change_names(cwd)
    if not dirty:
        return []  # nothing uncommitted under openspec/changes, or not a git repo — nothing to gate

    candidates = []
    for entry in sorted(changes_dir.iterdir()):
        if not entry.is_dir() or entry.name == "archive":
            continue
        tasks_file = entry / "tasks.md"
        if not tasks_file.is_file():
            continue
        # Only a change that git shows as modified/untracked is "this session's work";
        # an old, already-committed, already-reviewed change is not re-flagged.
        if entry.name not in dirty:
            continue
        try:
            text = tasks_file.read_text()
        except Exception:
            continue
        if not CHECKBOX_ANY.search(text):
            continue  # no checkboxes at all — not a task list we understand
        if CHECKBOX_UNDONE.search(text):
            continue  # still has unchecked tasks — not complete yet, nothing to gate
        candidates.append(entry.name)
    return candidates


def is_review_call(name: str, tool_input) -> bool:
    """True when a single tool_use block is reviewer-shaped (see module docstring)."""
    if not isinstance(tool_input, dict):
        tool_input = {}
    if name in AGENT_TOOLS:
        target = " ".join(str(tool_input.get(field, "") or "") for field in AGENT_REVIEW_FIELDS)
    elif name == "Skill":
        target = str(tool_input.get("skill", "") or "")
    else:
        return False
    return bool(REVIEW_PATTERN.search(target))


def parse_review_result(text: str) -> dict:
    """Fields of a reviewer's own 'REVIEW RESULT' block, if it emitted one.

    Returns {} when no such block is found or nothing in it parses — callers must treat
    that as "unknown", never as "must_fix: 0". Mirrors groundwork_telemetry.py's proven
    'Harness metadata' block parser (same heading/field tolerance) rather than a new format.
    """
    if not text:
        return {}
    m = REVIEW_RESULT_HEADING.search(text)
    if not m:
        return {}
    fields = {}
    for line in text[m.end():].splitlines():
        if not line.strip():
            if fields:
                break
            continue
        f = REVIEW_RESULT_FIELD.match(line)
        if not f:
            if fields:
                break
            continue
        fields[f.group(1).strip().lower()] = f.group(2).strip().strip("*")
    result: dict = {}
    verdict = fields.get("verdict", "").strip().lower()
    if verdict in ("approve", "approved"):
        result["verdict"] = "approve"
    elif verdict in ("changes-required", "changes required", "changes_required"):
        result["verdict"] = "changes-required"
    must_fix_raw = fields.get("must-fix", fields.get("must fix", ""))
    digits = re.search(r"\d+", must_fix_raw)
    if digits:
        result["must_fix"] = int(digits.group())
    return result


def _tool_result_text(block_: dict) -> str:
    content = block_.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def scan_transcript(transcript_path: str):
    """One sequential pass over the transcript.

    Returns (reviews, edit_after, test_after):
      reviews — ordered list of {"must_fix": int|None} for every reviewer-shaped call found,
        in transcript order; must_fix is None when that call's own result had no parseable
        REVIEW RESULT block (or none was found at all before Stop).
      edit_after / test_after — whether an Edit-family tool call / a TEST_CMD-shaped Bash call
        was observed after the most recent review that reported must_fix > 0 (diagnostic only,
        included in the block message; not itself part of the gating decision — see docstring).
    Returns (None, False, False) on any read/parse failure — the caller fails open on None,
    exactly as the original presence-only check did.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return None, False, False
    reviews: list = []
    pending: dict = {}  # tool_use id -> index into `reviews`, awaiting its tool_result
    have_problem = False
    edit_after = False
    test_after = False
    try:
        with open(transcript_path, "r", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if not isinstance(entry, dict):
                    # One anomalous line (valid JSON, not an object) must not abort the whole
                    # scan via the outer except below — that would silently discard every
                    # review already parsed from earlier lines, including a real unresolved
                    # MUST-FIX finding, and fail open in the unsafe direction (allow Stop).
                    continue
                content = (entry.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for block_ in content:
                    if not isinstance(block_, dict):
                        continue
                    btype = block_.get("type")
                    if btype == "tool_use":
                        name = block_.get("name", "")
                        if is_review_call(name, block_.get("input")):
                            reviews.append({"must_fix": None})
                            tid = block_.get("id")
                            if tid:
                                # Correlatable with a later tool_result; if it never arrives (or
                                # carries no parseable block) this entry just stays must_fix=None,
                                # i.e. legacy presence-only for that call — never worse than before.
                                pending[tid] = len(reviews) - 1
                        elif have_problem and name in EDIT_TOOLS:
                            edit_after = True
                        elif have_problem and name == "Bash":
                            cmd = str((block_.get("input") or {}).get("command") or "")
                            if TEST_CMD.search(cmd):
                                test_after = True
                    elif btype == "tool_result":
                        tid = block_.get("tool_use_id")
                        if tid in pending:
                            idx = pending.pop(tid)
                            parsed = parse_review_result(_tool_result_text(block_))
                            mf = parsed.get("must_fix")
                            if mf is None and parsed.get("verdict") == "approve":
                                mf = 0
                            reviews[idx]["must_fix"] = mf
                            if mf is not None and mf > 0:
                                have_problem = True
                                edit_after = False
                                test_after = False
    except Exception:
        return None, False, False
    return reviews, edit_after, test_after


def deny(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError("hook input must be a JSON object")
    except Exception:
        sys.exit(0)

    cwd = data.get("cwd") or os.getcwd()
    transcript_path = data.get("transcript_path", "")

    try:
        candidates = find_complete_unreviewed_changes(cwd)
    except Exception:
        sys.exit(0)

    if not candidates:
        sys.exit(0)

    try:
        reviews, edit_after, test_after = scan_transcript(transcript_path)
    except Exception:
        sys.exit(0)

    if reviews is None:
        sys.exit(0)  # transcript unreadable/unparseable — fail open, as always

    names = ", ".join(candidates)

    if not reviews:
        deny(
            f"require_material_review: OpenSpec change(s) [{names}] have every task checked off, "
            "but no independent fresh-context review was dispatched this session (looked for an "
            "Agent/Task call whose subagent_type or name contains \"review\", or a "
            "Skill call with \"review\" in its name — e.g. ecc:code-reviewer, ecc:security-reviewer, "
            "ecc:python-reviewer, ecc:orch-review, or a reviewer teammate). Dispatch an appropriate "
            "reviewer on the diff, fix any MUST FIX findings, then finish."
        )
        return

    most_recent_must_fix = reviews[-1]["must_fix"]
    if most_recent_must_fix is None or most_recent_must_fix == 0:
        sys.exit(0)  # a review happened and either cleared it or didn't cooperate with the
        # structured format — legacy presence-only pass, never stricter than before 2.0

    # The most recent review's own result reports unresolved MUST FIX findings. An edit and a
    # re-run of validation afterward are not, by themselves, evidence of resolution (Decision
    # D3, strengthened) — only a fresh independent review of the resulting change clears this,
    # and because the decision always looks at the *most recent* review's own verdict, a
    # second review-shaped call is structurally required to change the outcome.
    progress = [
        "a follow-up edit was observed" if edit_after else "no follow-up edit has been observed yet",
        "the affected validation was re-run" if test_after else "validation has not been re-run yet",
    ]
    deny(
        f"require_material_review: OpenSpec change(s) [{names}] are complete, but the most recent "
        f"independent review reported {most_recent_must_fix} unresolved MUST FIX finding(s) "
        f"({'; '.join(progress)}). An edit and a validation re-run are not, by themselves, evidence "
        "the finding was resolved — fix it, re-run the affected validation, then dispatch a FRESH "
        "independent review (a new Agent/Task/Skill call) of the resulting change, asking it to end "
        "its response with a REVIEW RESULT block (Verdict: approve/changes-required, Must-fix: N). "
        "Only when that fresh review reports zero remaining MUST FIX findings will this gate clear."
    )


if __name__ == "__main__":
    main()
