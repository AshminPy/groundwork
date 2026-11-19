## Layout

Everything for this change lives in one place:

```
openspec/changes/harden-autonomy-evidence-review/
  proposal.md        why and what
  design.md          this file: decisions and layout
  baseline.md        Phase 0 audit: what exists, what is missing, with evidence
  tasks.md           work in priority order, one section per safeguard
  specs/<capability>/spec.md
tests/
  test_review_independence.py     one regression file per safeguard
  test_evidence_validation.py
  test_scope_control.py
  test_permission_boundaries.py
  fixtures/<safeguard>/           file inputs, only when a test needs them
```

All safeguards ship in one PR, at the owner's request, as separate commits in the order of `tasks.md`, so each can
still be read and reverted alone. Operator docs live in `docs/PERMISSIONS.md` and `docs/COORDINATION.md`; the
benchmark procedure is `benchmark.md` in this folder.

## Architecture questions (architecture-quality.md §2)

- What changes: reviewer prompts and verdict format; the fingerprint scope. The fingerprint function stays the single owner (`hooks/groundwork_tasks.py:642`).
- Another provider or environment: the gate reads only the transcript and git, so it is the same for any reviewer agent.
- Automation: `groundwork task fingerprint` replaces hand-copied hashes.
- Dependency down: no git, or an unreadable transcript, fails open as today. A review block without a fingerprint, or with a stale one, blocks with an exact fix.
- Observability: every block message names the change, the reviewed fingerprint and the current one.
- Testing: unit fixtures, then a real `claude -p` Stop-hook run, which proves runtime behaviour.
- Rollback: revert the PR. No state files are added.
- Security boundary: the reviewer is read-only by instruction. The gate cannot prove a reviewer read the code, only that a fresh-context call reported the current fingerprint.
- Scale and cost: one extra `git` tree hash per Stop when a change is complete. The ledger already bounds its cost.

## Decisions

DECISION            Bind a review to the content fingerprint, not the commit SHA.
EVIDENCE            `fingerprint()` hashes tracked and untracked files, excluding `openspec/` (`hooks/groundwork_tasks.py:642-646`). The Stop gate runs before commit, while the work is uncommitted (`hooks/require_material_review.py:12-16`).
WHY                 A commit SHA does not exist yet when the gate runs, and it would change on an amend with no code change. The fingerprint changes exactly when code changes. A commit SHA is still recorded next to it, for PR traceability.
TRADEOFFS           A reviewer must run one command, or be handed its output.
VALIDATION METHOD   Fixture tests: a same-fingerprint review passes; an edit after review blocks. A real Stop-hook run.
UNCERTAINTY         A reviewer could echo a fingerprint without reading the diff. That cannot be enforced; it is listed under limitations.

DECISION            Only Agent/Task subagent calls count as independent; inline Skill reviews do not.
EVIDENCE            Skills run inside the calling conversation, while subagents start with their own context (code.claude.com/docs/en/sub-agents). The gate currently accepts Skill calls (`hooks/require_material_review.py:146-147`).
WHY                 An inline skill review is self-review by the same context.
TRADEOFFS           `/ecc:code-review`-style skills no longer satisfy the gate on their own. They must dispatch a reviewer subagent.
VALIDATION METHOD   Fixture: a Skill review with a correct block still blocks.
UNCERTAINTY         None material.

DECISION            No new orchestrator. Coordination uses native agent view, background sessions and worktrees.
EVIDENCE            `claude --bg`, `claude agents --json --all` and per-session worktrees under `.claude/worktrees/` (code.claude.com/docs/en/agent-view). Claude Projects cloud threads do not load repo hooks or permission rules (code.claude.com/docs/en/claude-projects).
WHY                 The requirement can be met natively. Governed work must run locally or through Remote Control, where hooks load.
TRADEOFFS           Agent view is a research preview.
VALIDATION METHOD   Documented runbook plus a dry-run listing.
UNCERTAINTY         Agent view behaviour may change between Claude Code releases.

DECISION            Read a background reviewer's verdict from its own subagent transcript.
EVIDENCE            Live run (Claude Code 2.1.316): an Agent call returned only "Async agent launched", and the verdict arrived later as a task notification. Claude Code writes the subagent's conversation to `<session>/subagents/agent-<id>.jsonl`, with `<id>.meta.json` naming its `toolUseId`.
WHY                 Without this, a correct background review could never clear the gate. The subagent file is written by Claude Code, not by the author's reply.
TRADEOFFS           It relies on an undocumented transcript layout. If the layout changes, the gate blocks with a correctable message rather than allowing.
VALIDATION METHOD   Fixture test with the same layout, plus a replay of the real transcript and a live `claude -p` run.
UNCERTAINTY         The layout is observed, not documented.

DECISION            Enforce PR review twice: locally before `gh pr create`, and in a GitHub workflow on every PR update.
EVIDENCE            The Stop gate runs only while the change is uncommitted (`hooks/require_material_review.py` find_complete_unreviewed_changes). A PreToolUse `deny` applies in every permission mode (code.claude.com/docs/en/hooks). `commit_fingerprint` of the committed review head equals the reviewed working-tree fingerprint (checked on this branch: both `7e4d6c4df9f91e2d`).
WHY                 The local check proves the approval came from a fresh-context subagent, which CI cannot see. The CI check proves the recorded approval still matches the head after later pushes, which the local check cannot see.
TRADEOFFS           The review block must be copied into the PR description. A draft PR may open first. The CI check blocks merging only once the owner marks it as a required status check.
VALIDATION METHOD   Fixture tests for both checks; the workflow runs on this PR.
UNCERTAINTY         The CI check cannot tell who wrote the PR description; independence rests on the local check.

DECISION            Citation and scope checks warn or ask once; they never hard-block.
EVIDENCE            The reply check already asks once and stops when `stop_hook_active` is set (`hooks/groundwork_reply_check.py`). A changed file outside the plan can be a legitimate blocker fix.
WHY                 A wrong deterministic block costs more than a missed warning, and the owner asked to avoid false blocks.
TRADEOFFS           A determined agent can ignore a warning; the independent review still sees the diff.
VALIDATION METHOD   Fixture tests: valid citations, other checkouts and illustrative paths pass; drift completes with a warning.
UNCERTAINTY         None material.

DECISION            Secrets stay HUMAN APPROVAL, and no new deny rules are added.
EVIDENCE            The task gate already asks for credential reads through Read and the shell (`tests/test_permission_boundaries.py`). Every HARD DENY item was already enforced except the PR review check.
WHY                 A deny rule cannot be approved case by case, and the owner sometimes needs metadata checks or rotation.
TRADEOFFS           An approved prompt can still expose a secret; the owner's rule against printing secret values applies.
VALIDATION METHOD   Tier probes through the real hooks.
UNCERTAINTY         `/auto-mode-setup` is not a command in Claude Code 2.1.316; `claude auto-mode config` shows built-in defaults only, so there is no custom auto-mode rule to assess.
