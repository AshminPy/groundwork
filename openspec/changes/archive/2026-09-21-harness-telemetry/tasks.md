## 1. Capture

- [x] 1.1 `hooks/groundwork_telemetry.py`: parse block, current-turn facts, outcome, privacy limits, fail-open, opt-out
- [x] 1.2 `rules/output-contract.md`: Harness metadata block section (inherited by every playbook)
- [x] 1.3 Snapshot: `harness: Groundwork <version>; profile: <…>` line; installer writes VERSION

## 2. Install

- [x] 2.1 `merge_settings.py` / `unmerge_settings.py`: fourth Stop hook entry; `install.sh` chmod + VERSION; `uninstall.sh` keeps records

## 3. Tests, docs, review

- [x] 3.1 `tests/test_telemetry.py` (new) + updates in `test_hooks.py` / `test_playbooks.py`; full suite green
- [x] 3.2 Non-regression: rules, guards and playbooks byte-identical to the pre-change baseline; existing behaviour re-verified
- [x] 3.3 README, ARCHITECTURE, CHANGELOG 1.3.0, VALIDATION
- [x] 3.4 Independent review (code + security/privacy); fix MUST FIX; live example record captured
