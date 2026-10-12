## 1. Implementation
- [x] 1.1 `hooks/groundwork_tasks.py`: ledger (per-repository key, atomic locked writes), intake classifier, plan parser and digest, state transitions, scope audit and fingerprint, completion gate, CLI
- [x] 1.2 `hooks/groundwork_task_gate.py`: UserPromptSubmit intake, UserPromptExpansion approval/cancel, PreToolUse gate, PostToolUse/PostToolUseFailure evidence and scope audit
- [x] 1.3 Owner commands `commands/gw-approve.md`, `commands/gw-cancel.md`
- [x] 1.4 Snapshot lines for open tasks (cap grows only by the task section, so snapshots without tasks are unchanged); `groundwork task` CLI pass-through
- [x] 1.5 Install, uninstall, settings merge/unmerge, setup verify
- [x] 1.6 Docs: TASK-LIFECYCLE.md, ARCHITECTURE enforced-vs-advisory rows, engineering-workflow §2.2 (MATERIAL now needs owner approval), CHANGELOG

## 2. Verification
- [x] 2.1 `tests/test_task_lifecycle.py`: classifier, plan gate, digest, approval channel, gate classes, evidence, completion, continuity, project separation, full deterministic lifecycle (123 checks)
- [x] 2.2 Full suite (138 passed) and `openspec validate --all --strict` (this change valid; the same two pre-existing failures as main: health-dashboard, onboarding)
- [x] 2.3 Live acceptance in a sandbox config directory with real `claude -p` sessions against a local fixture (COR-123 intake, blocked implementation, owner approval, approved execution, out-of-scope block, verification, review, completion, fresh-session recovery). Five sessions passed. The run found three defects, each fixed with a regression test: a placeholder verification command could never match; untracked STANDARD prompts piled up as tasks; generated caches were reported as unauthorized changes. It also found one display bug, fixed: a completed task's approval was shown as VOID.
- [ ] 2.4 Independent fresh-context review; MUST FIX findings fixed
