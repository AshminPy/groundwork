## 1. Foundation

- [x] 1.1 Package skeleton `orchestrator/groundwork_orchestrator/`, pinned `requirements.txt`, dev venv ignored by git
- [x] 1.2 `contract.py`: states, final statuses, task contract, classification schema + validator
- [x] 1.3 `store.py`: SQLite tasks / transitions / operations / sessions; idempotent `run_op`
- [x] 1.4 `routing.json` + `routing.py`: role → model, effort, reason; reject unknown models (tools stay in code)

## 2. Workers

- [x] 2.1 `claude_adapter.py`: preflight, argv builder, env scrub, stdin prompt, JSON parse, failure classes, timeout/cancel with process-group kill
- [x] 2.2 Stub `claude` for tests (scripted results, argv log)

## 3. Workflow

- [x] 3.1 `classifier.py`: deterministic rules, Haiku fallback with `--json-schema`, schema rejection
- [x] 3.2 `validation.py`: check runner (argv, timeout), workspace integrity, write scope, cited-source existence, final status
- [x] 3.3 `workspace.py`: allowlist, worktree creation (idempotent)
- [x] 3.4 `graph.py`: LangGraph workflow with approval interrupt, bounded repair, finalize; ledger reuse
- [x] 3.5 `cli.py`: `query`, `list`, `show`, `approve`, `reject`, `resume`, `allow`; abandoned-session reconciliation

## 4. Integration

- [x] 4.1 `groundwork query` / `groundwork orch` pass-through in `scripts/groundwork_cli.py`, plus CLI test
- [x] 4.2 `install.sh --with-orchestrator` and `uninstall.sh` removal
- [x] 4.3 `orchestrator/README.md` (purpose, how it works, configuration, run, validation, troubleshooting, security, limitations)

## 5. Verification

- [x] 5.1 Automated tests T01–T09, T12–T14, T17–T20 pass (T10, T11, T15, T16 are Phase 2/3)
- [x] 5.2 Existing suite still passes (T19)
- [x] 5.3 Live acceptance A (question), B (troubleshooting with a fix), C (small project) on the real CLI
- [x] 5.4 Independent review, MUST FIX cleared

## Verification

- `orchestrator/.venv/bin/python -m pytest orchestrator/tests -q`
- `python3 -m pytest tests -q`
- `openspec validate add-orchestrator-mvp --strict`
