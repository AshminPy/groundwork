#!/usr/bin/env python3
"""Stop hook — deterministically require an independent fresh-context review before
a MATERIAL (spec-driven) change is allowed to finish.

Custom harness extension (not part of ECC or OpenSpec). Neither enforces review: ECC's
reviewer agents are invocable but nothing dispatches them, and OpenSpec tracks task
checkboxes only. Rather than trust a self-declared "MATERIAL" tier (gameable) or a
self-declared "I reviewed it" claim (T12c skipped review and still reported COMPLETE),
this hook uses two facts it can check directly:

  1. Was an OpenSpec change fully implemented this session? (every checkbox in its
     tasks.md is "[x]", and the change directory is uncommitted/untracked per git —
     i.e. it is this session's own work, not old already-reviewed work.)
  2. Did a reviewer-shaped tool call happen anywhere in this session's transcript?
     (a Task/Agent call whose subagent_type contains "review", or a Skill call whose
     skill name contains "review" — this deliberately does not pin one specific
     reviewer name, so reviewer selection stays contextual per engineering-workflow.md.)

If (1) is true and (2) is false, the Stop is blocked with the concrete change name and
what's missing. It re-checks on every Stop, so once a review is actually dispatched the
block clears itself — no state file, no self-declaration.

Fail-open on any error (missing git, unreadable transcript, no repo): never block a
session over a broken guard.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REVIEW_PATTERN = re.compile(r"review", re.IGNORECASE)
CHECKBOX_UNDONE = re.compile(r"^\s*-\s*\[\s\]", re.MULTILINE)
CHECKBOX_ANY = re.compile(r"^\s*-\s*\[[ xX]\]", re.MULTILINE)


def find_complete_unreviewed_changes(cwd: str) -> list[str]:
    """Return names of openspec changes that are fully task-complete AND look like
    this session's own uncommitted work (not old, already-reviewed, committed work)."""
    changes_dir = Path(cwd) / "openspec" / "changes"
    if not changes_dir.is_dir():
        return []

    try:
        status = subprocess.run(
            # --untracked-files=all: a brand-new change directory otherwise collapses to
            # one "?? openspec/changes/" line instead of listing the change by name, which
            # made the per-change substring match below silently miss fresh (uncommitted)
            # changes (caught by this hook's own test suite before it was ever wired in).
            ["git", "-C", cwd, "status", "--porcelain", "--untracked-files=all", "--", "openspec/changes"],
            capture_output=True, text=True, timeout=5,
        )
        if status.returncode != 0:
            return []  # not a git repo (or git unavailable) — can't tell what's "this session's", skip gating
        dirty_paths = status.stdout
    except Exception:
        return []

    candidates = []
    for entry in sorted(changes_dir.iterdir()):
        if not entry.is_dir() or entry.name == "archive":
            continue
        tasks_file = entry / "tasks.md"
        if not tasks_file.is_file():
            continue
        # Only a change that git shows as modified/untracked is "this session's work";
        # an old, already-committed, already-reviewed change is not re-flagged.
        if entry.name not in dirty_paths:
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
                    name = block_.get("name", "")
                    tool_input = block_.get("input") or {}
                    if name in ("Task", "Agent"):
                        target = str(tool_input.get("subagent_type", ""))
                    elif name == "Skill":
                        target = str(tool_input.get("skill", ""))
                    else:
                        continue
                    if REVIEW_PATTERN.search(target):
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
        "but no independent fresh-context review was dispatched this session (looked for a "
        "Task/Agent call with subagent_type containing \"review\", or a Skill call with "
        "\"review\" in its name — e.g. ecc:code-reviewer, ecc:security-reviewer, ecc:python-reviewer, "
        "ecc:orch-review). Dispatch an appropriate reviewer on the diff, fix any MUST FIX findings, "
        "then finish."
    )


if __name__ == "__main__":
    main()
