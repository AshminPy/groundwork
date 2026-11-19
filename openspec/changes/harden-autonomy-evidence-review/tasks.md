## 0. Scaffolding
- [x] 0.1 Archive the six fully completed changes; fix placeholder spec Purposes so `openspec validate --all --strict` passes
- [x] 0.2 Write `baseline.md`, `proposal.md`, `design.md` and this task list

## 1. Review independence
- [x] 1.1 `groundwork task fingerprint` prints the change fingerprint and the HEAD SHA
- [x] 1.2 The Stop gate counts only Agent/Task calls whose result has a REVIEW RESULT block with `Reviewed:` equal to the current fingerprint; Skill calls and blocks without a fingerprint do not count
- [x] 1.3 A code change after the review makes it stale, and the message names both fingerprints
- [x] 1.4 Add `tests/test_review_independence.py` covering a self-review, a stale review, a current review and a background reviewer (Skill, MUST FIX re-review and teammate cases are in `tests/test_hooks.py`)
- [x] 1.5 Update the existing gate tests in `tests/test_hooks.py` to the new rule without weakening them
- [x] 1.6 Real `claude -p` Stop-hook run against a scratch repo
- [x] 1.7 Fresh independent review of the diff, recording the reviewed fingerprint
- [x] 1.8 `groundwork task fingerprint --commit REV`: the same fingerprint for a commit, equal to the working-tree fingerprint when the tree is clean
- [x] 1.9 The task gate denies a non-draft `gh pr create` until the most recent reviewer subagent reported `Must-fix: 0` on the commit it publishes
- [x] 1.10 `scripts/review_check.py` and `.github/workflows/review-check.yml` fail a PR whose description does not record an approval of the current head
- [x] 1.11 PR cases in `tests/test_review_independence.py`: no review, draft, Skill-only, current, plan-only commit, code commit after review, MUST FIX, CI pass and fail
- [x] 1.12 `gh pr edit` that sets the description is checked like `gh pr create`, since the description carries the recorded review
- [x] 1.13 Ruleset definition requiring `review-check` from GitHub Actions on `main`, and what each layer proves (`docs/PERMISSIONS.md`); applying it is an owner action

## 2. Evidence validation
- [x] 2.1 The reply check resolves cited repository paths and `path:line` / `path:a-b` ranges, flagging missing files and out-of-range lines
- [x] 2.2 Add `tests/test_evidence_validation.py` covering a missing file, a stale line range, a valid citation, a URL and a non-repo path

## 3. Scope control
- [x] 3.1 `groundwork task note <KEY> "<discovery>"` records an unrelated discovery without making it a task
- [x] 3.2 Status and completion list changed files the plan never names and TODOs added since the task started, as warnings only
- [x] 3.3 Add `tests/test_scope_control.py` covering an unrelated TODO, a blocking dependency and a stale issue

## 4. Permission boundaries
- [x] 4.1 Document the three tiers and map each to a native rule or an existing hook (`docs/PERMISSIONS.md`)
- [x] 4.2 Add `tests/test_permission_boundaries.py`: hard-deny, ask and autonomous probes through the real hooks

## 5. Coordination, models and benchmark
- [x] 5.1 Runbook: coordinator plus background sessions, worktrees, Remote Control for governed work, and the cloud-parity limits (`docs/COORDINATION.md`)
- [x] 5.2 Benchmark procedure (`benchmark.md`); the paid runs wait for the owner's budget approval
- [ ] 5.3 End-to-end coordination demo: two dependent tasks in the ledger, one background session in its own worktree, results read back, dependency cleared

## 6. Integration
- [x] 6.1 Full test suite, `openspec validate --all --strict`, and an integrated live run of the hooks together
- [x] 6.2 Fresh independent review of the complete change

## Verification
- `python3 tests/test_review_independence.py`
- `python3 tests/test_evidence_validation.py`
- `python3 tests/test_scope_control.py`
- `python3 tests/test_permission_boundaries.py`
- `python3 tests/test_hooks.py`
- `python3 tests/test_task_lifecycle.py`
- `python3 tests/test_reply_check.py`
