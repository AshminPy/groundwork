#!/usr/bin/env python3
"""Stop hook — deterministically require an independent fresh-context review before
a MATERIAL (spec-driven) change is allowed to finish.

Groundwork extension (not part of ECC or OpenSpec). Neither enforces review: ECC's
reviewer agents are invocable but nothing dispatches them, and OpenSpec tracks task
checkboxes only. Rather than trust a self-declared "MATERIAL" tier (gameable) or a
self-declared "I reviewed it" claim, this hook uses two facts it can check directly:

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

If (1) is true and (2) is false, the Stop is blocked with the concrete change name and
what's missing. It re-checks on every Stop, so once a review is actually dispatched the
block clears itself — no state file, no self-declaration. Claude Code itself caps a
Stop hook at 8 consecutive blocks (docs/en/hooks §Stop), so a session can never be
trapped; the transcript may also lag the in-memory turn, in which case the next Stop
sees the reviewer call.

Fail-open on any error (missing git, unreadable transcript, no repo): never block a
session over a broken guard.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# (?<![a-z]) so "preview"/"previewer" never count; "reviewer", "code-review", "orch-review" still do.
REVIEW_PATTERN = re.compile(r"(?<![a-zA-Z])review", re.IGNORECASE)
CHECKBOX_UNDONE = re.compile(r"^\s*-\s*\[\s\]", re.MULTILINE)
CHECKBOX_ANY = re.compile(r"^\s*-\s*\[[ xX]\]", re.MULTILINE)
AGENT_TOOLS = ("Task", "Agent")
AGENT_REVIEW_FIELDS = ("subagent_type", "name")


def dirty_change_names(cwd: str) -> set[str]:
    """Names of openspec/changes/<name> directories that git shows as modified or untracked.

    Parses each porcelain line's path into segments instead of substring-matching the raw
    output: with `thing` (committed) and `add-thing` (dirty) in the same repo, a substring
    test wrongly flagged `thing` too (found by independent review of 1.1.0).
    """
    try:
        status = subprocess.run(
            # --untracked-files=all: a brand-new change directory otherwise collapses to one
            # "?? openspec/changes/" line instead of listing its files (caught by the 1.0.0 tests).
            ["git", "-C", cwd, "status", "--porcelain", "--untracked-files=all", "--", "openspec/changes"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return set()
    if status.returncode != 0:
        return set()
    names = set()
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:  # rename: "old -> new"
            path = path.split(" -> ", 1)[1]
        path = path.strip().strip('"')
        parts = path.split("/")
        if len(parts) > 2 and parts[0] == "openspec" and parts[1] == "changes":
            names.add(parts[2])
    return names


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


def transcript_has_review(transcript_path: str) -> bool:
    if not transcript_path or not os.path.isfile(transcript_path):
        return False
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
                message = entry.get("message") or {}
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for block_ in content:
                    if not isinstance(block_, dict) or block_.get("type") != "tool_use":
                        continue
                    if is_review_call(block_.get("name", ""), block_.get("input")):
                        return True
    except Exception:
        return False
    return False


def deny(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
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
        if transcript_has_review(transcript_path):
            sys.exit(0)
    except Exception:
        sys.exit(0)

    names = ", ".join(candidates)
    deny(
        f"require_material_review: OpenSpec change(s) [{names}] have every task checked off, "
        "but no independent fresh-context review was dispatched this session (looked for an "
        "Agent/Task call whose subagent_type or name contains \"review\", or a "
        "Skill call with \"review\" in its name — e.g. ecc:code-reviewer, ecc:security-reviewer, "
        "ecc:python-reviewer, ecc:orch-review, or a reviewer teammate). Dispatch an appropriate "
        "reviewer on the diff, fix any MUST FIX findings, then finish."
    )


if __name__ == "__main__":
    main()
