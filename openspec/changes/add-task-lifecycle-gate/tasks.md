## 1. Implementation
- [x] 1.1 `hooks/groundwork_tasks.py`: ledger (per-repository key, atomic locked writes), intake classifier, native plan reader (tasks.md progress, `## Verification`), phase, evidence and fingerprint, completion, CLI
- [x] 1.2 `hooks/groundwork_task_gate.py`: UserPromptSubmit intake, PreToolUse `ask` for sensitive actions, PostToolUse/PostToolUseFailure evidence and completion on native archive
- [x] 1.3 Remove the approval-code build: owner commands, plan-section and scope gates, the `UserPromptExpansion` registration (removed from older installs on merge and unmerge)
- [x] 1.4 Snapshot lines for open tasks (task, phase, progress, evidence, next action); `groundwork task` CLI pass-through
- [x] 1.5 Install, uninstall, settings merge/unmerge, setup verify
- [x] 1.6 Docs: TASK-LIFECYCLE.md, ARCHITECTURE, engineering-workflow §2.2, CHANGELOG

## 2. Verification
- [x] 2.1 `tests/test_task_lifecycle.py`: classifier, authorization classes, shell-parser regressions, MATERIAL lifecycle (intake, ordinary work without prompts, plan revision, evidence, completion, native archive), recovery, separation, kill switch
- [ ] 2.2 Full suite and `openspec validate add-task-lifecycle-gate --strict`
- [ ] 2.3 Independent fresh-context review; MUST FIX findings fixed
- [ ] 2.4 Live acceptance with real `claude -p` sessions in a sandbox config directory against a fixture repository: MATERIAL intake and OpenSpec plan, implementation without approval prompts, plan revision, a sensitive action asking for authorization, evidence, completion, native archive, fresh-session recovery

## Verification

- `python3 -m pytest tests -q --ignore=tests/mutation`
- `python3 tests/test_task_lifecycle.py`
