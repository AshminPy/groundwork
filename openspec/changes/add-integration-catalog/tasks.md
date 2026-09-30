# Tasks

## 1. Catalog module and data structures

- [ ] 1.1 Create `scripts/groundwork_integrations.py` with a small frozen `IntegrationEntry`/`AccessMechanism` structure (dataclasses or namedtuples) and populate the catalog (GitHub, Jira, Confluence, AWS, GCP, Kubernetes, Terraform, Spacelift, and the observability tools already researched in `docs/INTEGRATIONS.md`), each with capability ids, typed approved mechanisms, trust/access characteristics, and config requirements; verify with `python3 scripts/groundwork_integrations.py list` printing one row per entry with no traceback.
- [ ] 1.2 Add `tests/test_groundwork_integrations.py` with a structural-validity test (every entry has a non-empty name, >=1 capability id, >=1 typed mechanism, a trust/access description) and verify it passes: `python3 -m pytest tests/test_groundwork_integrations.py -k structural -q`.

## 2. Truthful state determination and probes

- [ ] 2.1 Implement bounded, non-mutating probe helpers (`_probe_cli_version`, `_probe_cli_auth`, `_probe_mcp_listed`) matching the timeout/safe-fail pattern already used by `groundwork_routines.py`'s `check_access()` (subprocess + explicit timeout + except-safe), written fresh in this file per design.md Decision 3 (no cross-import from `hooks/`).
- [ ] 2.2 Implement `determine_state(entry)` returning exactly one of `AVAILABLE` / `CONFIGURED` / `CONNECTED` / `NOT CONFIGURED` per the order and independence rules in design.md Decision 4.
- [ ] 2.3 Add tests: presence-only never yields `CONNECTED`; a mocked successful check yields `CONNECTED`; a mocked failed/erroring/timed-out check never yields `CONNECTED`; missing config yields `NOT CONFIGURED`/`AVAILABLE` correctly, not a crash. Verify: `python3 -m pytest tests/test_groundwork_integrations.py -k state -q`.

## 3. CLI commands

- [ ] 3.1 Implement `list` (table: Integration | Access | State) and `show <name>` (purpose, capabilities, approved mechanisms, trust/access characteristics, configuration requirements, current state) using argparse, matching `groundwork_config.py`'s CLI shape.
- [ ] 3.2 Implement the Routines-dependency line in `show`, reading `groundwork_routines.py`'s own routine configuration deterministically (no inference for playbooks); handle an unknown integration name in `show` with a clean "not known" message, no traceback.
- [ ] 3.3 Add tests: `list` output formatting (one row per catalog entry); `show` output for a known integration includes all required fields; `show` for an unknown name reports not-known without crashing; Routines-dependency line only lists a Routine when its stored config explicitly declares that mechanism; a scan of all command output against credential/token/password/API-key/secret-shaped patterns finds nothing. Verify: `python3 -m pytest tests/test_groundwork_integrations.py -k "cli or secret" -q`.

## 4. USED state from existing telemetry

- [ ] 4.1 Implement a read-only lookup of the most recent telemetry record(s) (`groundwork_telemetry.py`'s existing JSONL output) for a `USED` signal per integration; when telemetry is absent or inconclusive, report `USED: unknown` rather than guessing.
- [ ] 4.2 Add a test with a fixture telemetry file confirming `USED` reflects a real recent record, and confirming `USED: unknown` when no telemetry file exists. Verify: `python3 -m pytest tests/test_groundwork_integrations.py -k used -q`.

## 5. Install and doctor wiring

- [ ] 5.1 Add `groundwork_integrations.py` to `install.sh`'s script-install list (same treatment as `groundwork_report.py`/`groundwork_config.py`/`groundwork_routines.py`) and verify `./install.sh` (or a dry review of the diff) places and `chmod +x`'s it identically to the existing three.
- [ ] 5.2 Add an "Integrations" section to `setup.sh --doctor` that shells out to `groundwork_integrations.py list` and indents its output, mirroring the existing Routines doctor section; verify by running `./setup.sh --doctor` against a repo checkout and confirming the new section appears with no error.

## 6. Documentation

- [ ] 6.1 Extend `docs/INTEGRATIONS.md` with the capability-id / approved-mechanism information per domain and a short section describing the new `list`/`show` commands.
- [ ] 6.2 Add `tests/test_groundwork_integrations.py` coverage asserting every catalog integration name has a corresponding row in `docs/INTEGRATIONS.md` (doc-consistency check, test-only text scan — never runtime logic); verify: `python3 -m pytest tests/test_groundwork_integrations.py -k doc_consistency -q`.
- [ ] 6.3 Add a short, clearly-labeled architecture note (in `docs/ARCHITECTURE.md`) stating Groundwork relies on Claude Code's native Tool Search for lazy MCP tool-schema loading and provides capability/integration guidance only, never enforced per-task MCP activation.
- [ ] 6.4 Update `README.md`'s repository-layout tree with the new script and test file, and add a `CHANGELOG.md` entry describing the Integration Catalog addition.

## 7. Full validation

- [ ] 7.1 Run the full test suite (`python3 -m pytest tests -q`) and confirm no regressions beyond this change's own new tests.
- [ ] 7.2 Run `openspec validate add-integration-catalog --strict` and resolve any reported issues.
- [ ] 7.3 Dispatch an independent, fresh-context review of the diff; fix only findings it reports as material (MUST FIX), and re-run the affected tests after each fix.
