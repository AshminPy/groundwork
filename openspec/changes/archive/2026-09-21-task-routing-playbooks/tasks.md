## 1. Router and playbooks

- [x] 1.1 `rules/task-routing.md`: routing steps, material-ambiguity rule, category table with mappings, universal output contract, existing-rule-wins clause
- [x] 1.2 Ten playbooks under `playbooks/` with Goal / Workflow / Evidence / Ask Before Acting When / Completion Criteria / Output Format

## 2. Install

- [x] 2.1 `install.sh` copies `playbooks/*.md` to `$CLAUDE_DIR/groundwork/playbooks/`; `uninstall.sh` removes the directory

## 3. Tests and validation

- [x] 3.1 `tests/test_playbooks.py`: every category has a playbook, six sections present, size cap, router references every category, install copies playbooks idempotently, no playbook under rules/
- [x] 3.2 `scripts/check_routing.py` + `tests/routing_scenarios.json`: live twelve-scenario routing and ambiguity check via `claude -p` (skips when logged out)
- [x] 3.3 Non-regression: SHA-256 of pre-existing critical files unchanged; `python3 tests/test_hooks.py` still 92 passed

## 4. Docs

- [x] 4.1 README section, ARCHITECTURE mention, CHANGELOG 1.2.0, VALIDATION evidence

## 5. Review

- [x] 5.1 Independent fresh-context review; fix MUST FIX; re-run tests
