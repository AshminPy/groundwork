## 0. Scaffolding
- [x] 0.1 Archive the six fully completed changes; fix placeholder spec Purposes so `openspec validate --all --strict` passes
- [x] 0.2 Write `baseline.md`, `proposal.md`, `design.md` and this task list

## 1. Review independence (PR 1)
- [x] 1.1 `groundwork task fingerprint` prints the change fingerprint and the HEAD SHA
- [x] 1.2 The Stop gate counts only Agent/Task calls whose result has a REVIEW RESULT block with `Reviewed:` equal to the current fingerprint; Skill calls and blocks without a fingerprint do not count
- [x] 1.3 A code change after the review makes it stale, and the message names both fingerprints
- [x] 1.4 Add `tests/test_review_independence.py` covering a self-review, a stale review, a current review and a background reviewer (Skill, MUST FIX re-review and teammate cases are in `tests/test_hooks.py`)
- [x] 1.5 Update the existing gate tests in `tests/test_hooks.py` to the new rule without weakening them
- [x] 1.6 Real `claude -p` Stop-hook run against a scratch repo
- [x] 1.7 Fresh independent review of the PR diff, recording the reviewed fingerprint

## 2. Evidence validation (PR 2)
- [ ] 2.1 The reply check resolves cited repository paths and `path:line` / `path:a-b` ranges, flagging missing files and out-of-range lines
- [ ] 2.2 Add `tests/test_evidence_validation.py` covering a missing file, a stale line range, a valid citation, a URL and a non-repo path

## 3. Scope control (PR 3)
- [ ] 3.1 `groundwork task note <KEY> "<discovery>"` records an unrelated discovery without making it a task
- [ ] 3.2 At completion, list changed files the plan never names, as a warning only
- [ ] 3.3 Add `tests/test_scope_control.py` covering an unrelated TODO, a blocking dependency and a stale issue

## 4. Permission boundaries (PR 4)
- [ ] 4.1 Document the three tiers and map each to a native rule or an existing hook
- [ ] 4.2 Add `tests/test_permission_boundaries.py`: hard-deny, ask and autonomous probes through the real hooks

## 5. Coordination, models and benchmark (documentation and owner decisions)
- [ ] 5.1 Runbook: coordinator plus background sessions, worktrees, Remote Control for governed work, and the cloud-parity limits
- [ ] 5.2 Benchmark run on the `add-baseline-benchmark` runner, only after the owner approves the run budget
