## 1. Rules

- [x] 1.1 Add `rules/architecture-quality.md`: governing principle, dimensions-as-criteria, pre-MATERIAL questions, variation-point rule, no-abstraction-without-reason, DECISION record pointer
- [x] 1.2 Update `rules/engineering-workflow.md`: UNDERSTAND state table, execution-model section (main/subagent/team + fallback), continuation procedure, `Reviewed:` row, no `--dangerously-skip-permissions` default, hook description update
- [x] 1.3 Update `rules/evidence-policy.md`: validation ladder, derive-commands rule, mocks-never-prove-runtime, compressed DECISION record, `Reviewed` row in the completion-evidence table

## 2. Hooks

- [x] 2.1 Extend `hooks/require_material_review.py` to match `name` and `description` on Agent/Task calls; document the 8-block platform cap
- [x] 2.2 Add `hooks/groundwork_session_snapshot.py` (SessionStart): git facts, OpenSpec progress, signal files, discovered verification commands; ≤ 2,500 chars; 3 s git timeouts; fail-open

## 3. Installer

- [x] 3.1 `scripts/merge_settings.py`: register SessionStart hook idempotently; `--agent-teams` opt-in env
- [x] 3.2 `scripts/unmerge_settings.py`: remove the SessionStart entry; leave user-set env alone
- [x] 3.3 Add `scripts/migrate_legacy_rules.py` and call it from `install.sh`; copy the new hook; support `--agent-teams`; fix the stale `docs/WORKFLOW.md` reference
- [x] 3.4 `uninstall.sh`: remove the new hook file

## 4. Tests

- [x] 4.1 Review-gate cases: teammate by `name`, reviewer by `description`, implementer-only (negative), Agent call with empty input
- [x] 4.2 Snapshot hook cases: git+openspec repo (progress, gate marker, branch), Makefile/package.json discovery, cap, non-git dir, malformed input
- [x] 4.3 Settings merge/unmerge: fresh file, idempotent second run, user override preserved, round trip, `--agent-teams`
- [x] 4.4 Legacy migration: files moved to backup, no-op when absent
- [x] 4.5 Run the full suite: `python3 -m pytest tests -q` and `python3 tests/test_hooks.py`

## 5. Docs

- [x] 5.1 README, ARCHITECTURE, TROUBLESHOOTING, UPGRADE-ROLLBACK updated for the third rule, third hook, migration, `--agent-teams`
- [x] 5.2 VALIDATION.md: append this iteration's deterministic evidence and model-behaviour observations, clearly separated
- [x] 5.3 CHANGELOG 1.1.0

## 6. Validation and review

- [x] 6.1 Install into a temporary `CLAUDE_CONFIG_DIR` copy of the live config; prove idempotency and no overwrite
- [x] 6.2 Independent fresh-context review (code + Python + security reviewers); fix MUST FIX; re-run tests
- [x] 6.3 Live install on this machine with a settings backup; installed hooks executed with real SessionStart/Stop payloads
- [ ] 6.4 Fresh-session proof via `claude -p` (BLOCKED 2026-09-20: `Failed to authenticate: OAuth session expired and could not be refreshed` — needs `claude login` on this machine, then re-run)
