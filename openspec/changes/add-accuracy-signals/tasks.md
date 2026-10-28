## 0. Hygiene
- [x] 0.1 Move the test-polluted `signals.jsonl` out of the real telemetry folder (done 2026-10-27)
- [x] 0.2 `tests/_isolate.py` (imported first by every test file and by `conftest.py`) defaults `GROUNDWORK_SIGNALS_PATH` to a temp file; a test that the real file is untouched

## 1. Collection
- [x] 1.1 Telemetry: lazy `try` import of the task gate's `split_segments`; leading-executable `classify_command`; masked and chain rules (D5). The task gate is not changed
- [x] 1.2 Tool rows: `prompt_id`, `tool_use_id`, Bash `kind` and `result` (D5); review signal from completed PostToolUse(Agent/Task) via `is_review_call`, keyed by `agentId`
- [x] 1.3 `signals.jsonl` writer (O_NOFOLLOW|O_NONBLOCK, regular file, 0600) and dispatch table (D2): SubagentStop review, UserPromptSubmit correction (D10), PostCompact
- [x] 1.4 Stop record: citations (D7), `ctx_pct`, `cost_usd`, `head`/`repo` on commit turns; remove the prototype file hashes and salt
- [x] 1.5 Guardrail records (D6) in the push guard, task gate, review gate and reply check: lazy import in `try`, `cause`, `tool_use_id`
- [x] 1.6 `TELEMETRY_EVENTS` tuple in `merge_settings.py`, imported by `unmerge_settings.py`; telemetry uses PostCompact (the brief's PreCompact entry stays); uninstall comment

## 2. Report
- [x] 2.1 Loaders keep the D3 fields; turn builder (merge Stops per prompt, `no_stop`, time fallback); attribute before windowing
- [x] 2.2 Ledger reader for Q3a/Q3b from `history` (last 60 events; truncated tasks left out and counted; all repo ledgers; no command text)
- [x] 2.3 Metrics Q1a–Q11 per D4, with labels, outcome-unstated share and the n < 5 / 5–19 rules
- [x] 2.4 `--github` (D8): commit turns, validation, pagination, status, mapping, `records=` last line
- [x] 2.5 Markdown + HTML section; replace the old Rework / Verified accuracy lines; benchmark footer line

## 3. Verification
- [x] 3.1 Tests: labelled fixtures per D5/D7/D10, attribution cases, ledger fixtures, CI mapping, guard-module-missing; update pinned tests (test_telemetry key sets, test_hooks/test_setup 18/6)
- [x] 3.2 Mutation checks on each metric's key clause
- [x] 3.3 Full suite; docs (README privacy, ARCHITECTURE, CHANGELOG, UPGRADE-ROLLBACK, hook docstrings)
- [ ] 3.4 Independent review loop until 0 must-fix
- [x] 3.5 Live headless `claude -p` run: `prompt_id` on PostToolUse/SubagentStop/PostCompact, failing test → `fail`, correction, review signal; measure hook latency (done 2026-10-28: all signals observed live; subagent and background-agent rows and SubagentStop carry the parent prompt's `prompt_id`; foreground Agent results carry `agentId`; hooks 55-72 ms median)

