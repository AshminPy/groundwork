## Why

Groundwork's safety and review controls are partly advisory. The Phase 0 audit (`baseline.md`) found four gaps that can be closed deterministically:

- The review gate accepts any reviewer-named tool call. It does not check that the review covered the current code. An edit after a passing review does not invalidate it.
- Reply checks validate structure only. A cited `file:line` is never checked to exist.
- Nothing records discoveries outside the task's goal, or compares the final change against that goal.
- The permission boundary between hard-deny, ask and autonomous work is spread across user settings, the installer and two hooks, with no single definition and no tests for the boundary as a whole.

## What Changes

- **Review independence (first):** a review counts only when it comes from a subagent (a fresh context, not an inline skill), its result carries a `REVIEW RESULT` block, and the block names the change fingerprint it reviewed. A later code change makes the review stale. A new `groundwork task fingerprint` command prints the fingerprint a reviewer must report. A background reviewer's verdict is read from the transcript Claude Code writes for that subagent.
- **Evidence validation:** the reply check verifies that cited repository paths exist and that cited line ranges are inside the file.
- **Scope control:** intake records the goal and acceptance criteria. Unrelated discoveries go to a task note instead of becoming work. Completion lists changed files the plan never names, as a warning, not a block.
- **Permission boundaries:** one documented three-tier policy, built from native permission rules first and existing hooks second, with a regression test per tier.
- **Coordination and models:** documentation of the native path (agent view, background sessions, worktrees, Remote Control for governed work). No new orchestrator.

## Capabilities

### New Capabilities
- `review-independence`: a review is bound to the reviewed content and to a fresh context.
- `evidence-validation`: cited repository evidence is checked to exist.
- `scope-control`: the original goal is kept, and discoveries are recorded rather than acted on.

### Modified Capabilities
- `execution-model-selection`: the review gate no longer counts inline Skill reviews as independent.
- `task-lifecycle` is extended later (PR 3) by a note command.

## Impact

- Code: `hooks/require_material_review.py`, `hooks/groundwork_reply_check.py`, `hooks/groundwork_tasks.py`.
- Tests: one regression file per safeguard under `tests/`. Fixtures are built inside each test; file fixtures, if any are needed, go under `tests/fixtures/<safeguard>/`.
- Behaviour change: a review without a fingerprint no longer clears the Stop gate. The block message says exactly what the reviewer must emit.
- No new dependencies, frameworks or services.
