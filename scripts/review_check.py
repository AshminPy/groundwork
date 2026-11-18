#!/usr/bin/env python3
"""Pull request review check: the PR description must carry an independent reviewer's REVIEW RESULT block that
reports Must-fix: 0 and names, as `Reviewed:`, the content fingerprint of the PR head commit.

Run by .github/workflows/review-check.yml on every PR update, so a push after the review makes the check fail until
a fresh review is recorded. Locally: PR_BODY="$(gh pr view N --json body -q .body)" python3 scripts/review_check.py

The fingerprint is `groundwork task fingerprint --commit HEAD` (hooks/groundwork_tasks.py commit_fingerprint):
a git tree hash of the commit without openspec/, so plan edits do not make a review stale and code changes do.
Exit 0 when the block matches, 1 when it does not, 2 when the check cannot run.
"""
import os
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
sys.path.insert(0, str(HOOKS))
from groundwork_tasks import commit_fingerprint, repo_root  # noqa: E402
from require_material_review import parse_review_result  # noqa: E402


def check(body: str, root: str, rev: str = "HEAD") -> tuple[bool, str]:
    fp = commit_fingerprint(root, rev)
    if not fp:
        return False, f"cannot compute the content fingerprint of {rev}"
    result = parse_review_result(body or "")
    fix = (f"Get an independent reviewer subagent to review the PR head, ending with a REVIEW RESULT block "
           f"(Verdict, Must-fix: N, Reviewed: {fp}), and put that block at the end of the PR description.")
    if result.get("must_fix") is None or not result.get("reviewed"):
        return False, f"the PR description has no REVIEW RESULT block with Must-fix and Reviewed. {fix}"
    if result["must_fix"] > 0:
        return False, f"the recorded review reports {result['must_fix']} unresolved MUST FIX finding(s). {fix}"
    if result["reviewed"] != fp:
        return False, (f"the recorded review covered {result['reviewed']}, but the PR head is {fp}: the code changed "
                       f"after the review. {fix}")
    return True, f"review recorded for the PR head ({fp}): verdict {result.get('verdict') or 'not stated'}, Must-fix 0"


def main() -> int:
    root = repo_root(os.getcwd())
    if not root:
        print("review-check: not inside a git repository", file=sys.stderr)
        return 2
    ok, msg = check(os.environ.get("PR_BODY", ""), root, os.environ.get("REVIEW_CHECK_REV", "HEAD"))
    print(f"review-check: {msg}", file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
