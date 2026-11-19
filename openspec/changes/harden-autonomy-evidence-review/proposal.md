## Why

Groundwork's safety and review controls are partly advisory. The Phase 0 audit (`baseline.md`) found four gaps that can be closed deterministically:

- The review gate accepts any reviewer-named tool call. It does not check that the review covered the current code. An edit after a passing review does not invalidate it.
- Reply checks validate structure only. A cited `file:line` is never checked to exist.
- Nothing records discoveries outside the task's goal, or compares the final change against that goal.
- The permission boundary between hard-deny, ask and autonomous work is spread across user settings, the installer and two hooks, with no single definition and no tests for the boundary as a whole.

## What Changes

- **Review independence (first):** a review counts only when it comes from a subagent (a fresh context, not an inline skill), its result carries a `REVIEW RESULT` block, and the block names the change fingerprint it reviewed. A later code change makes the review stale. A new `groundwork task fingerprint` command prints the fingerprint a reviewer must report. A background reviewer's verdict is read from the transcript Claude Code writes for that subagent.
- **Review of pull requests:** a non-draft `gh pr create` is denied until the most recent reviewer subagent approved exactly the commit it publishes, and a `review-check` GitHub workflow fails a PR whose description does not record an approval of the current head. A push after the review makes the check fail again.
- **Evidence validation:** the reply check verifies that cited repository paths exist and that cited line ranges are inside the file.
- **Scope control:** the task's goal (the intake prompt) and its OpenSpec plan are the reference. Unrelated discoveries go to `groundwork task note` instead of becoming work. Status and completion list changed files the plan never names and TODOs added since the task started, as warnings, never blocks.
- **Permission boundaries:** one documented three-tier policy (`docs/PERMISSIONS.md`), built from native permission rules first and existing hooks second, with a regression test per tier.
- **Coordination and models:** a runbook for the native path (`docs/COORDINATION.md`: background sessions, worktrees, agent view, the task ledger, Remote Control for governed work). No new orchestrator. Model choice stays configurable.
- **Benchmark procedure:** `benchmark.md`, prepared and not run.

## Capabilities

### New Capabilities
- `review-independence`: a review is bound to the reviewed content and to a fresh context.
- `evidence-validation`: cited repository evidence is checked to exist.
- `scope-control`: the original goal is kept, and discoveries are recorded rather than acted on.
- `permission-boundaries`: three tiers with a native mechanism and a test each.

### Modified Capabilities
- `execution-model-selection`: the review gate no longer counts inline Skill reviews as independent.
- `task-lifecycle`: a `note` command and `fingerprint --commit` are added to the task CLI.

## Impact

- Code: `hooks/require_material_review.py`, `hooks/groundwork_reply_check.py`, `hooks/groundwork_tasks.py`, `hooks/groundwork_task_gate.py`, `scripts/review_check.py`, `.github/workflows/review-check.yml`.
- Docs: `docs/PERMISSIONS.md`, `docs/COORDINATION.md`, and the rules and architecture docs.
- Tests: one regression file per safeguard under `tests/`. Fixtures are built inside each test; file fixtures, if any are needed, go under `tests/fixtures/<safeguard>/`.
- Behaviour change: a review without a fingerprint no longer clears the Stop gate, a non-draft PR cannot open without a current independent review, and a reply citing a file or line that does not exist is asked once to correct it. Each message says exactly what to do.
- No new dependencies, frameworks or services.
