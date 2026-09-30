# Tasks

## 1. Catalog module and data structures

- [x] 1.1 Create `scripts/groundwork_integrations.py` with a small frozen `IntegrationEntry`/`AccessMechanism` structure (dataclasses or namedtuples) and populate the catalog (GitHub, Jira, Confluence, AWS, GCP, Kubernetes, Terraform, Spacelift, and the observability tools already researched in `docs/INTEGRATIONS.md`), each with capability ids, typed approved mechanisms, trust/access characteristics, and config requirements; verify with `python3 scripts/groundwork_integrations.py list` printing one row per entry with no traceback.
- [x] 1.2 Add `tests/test_groundwork_integrations.py` with a structural-validity test (every entry has a non-empty name, >=1 capability id, >=1 typed mechanism, a trust/access description) and verify it passes: `python3 -m pytest tests/test_groundwork_integrations.py -k structural -q`.

## 2. Truthful state determination and probes

- [x] 2.1 Implement bounded, non-mutating probe helpers (`_probe_cli_version`, `_probe_cli_auth`, `_probe_mcp_listed`) matching the timeout/safe-fail pattern already used by `groundwork_routines.py`'s `check_access()` (subprocess + explicit timeout + except-safe), written fresh in this file per design.md Decision 3 (no cross-import from `hooks/`).
- [x] 2.2 Implement `determine_observation(entry) -> IntegrationObservation` computing `available`/`configured`/`connected` as three independent booleans (not a linear lifecycle) per design.md Decision 4, plus `summary_state(observation) -> str` deriving the display-only label (`CONNECTED` > `CONFIGURED` > `AVAILABLE` > `NOT CONFIGURED`, highest true wins) without persisting it.
- [x] 2.3 Add tests covering the specific combinations: (available=F,configured=F,connected=F)->`NOT CONFIGURED`; (T,F,F)->`AVAILABLE`; (F,T,F)->`CONFIGURED` with `available` still reported `False`; (T,T,F)->`CONFIGURED`; (T,T,T)->`CONNECTED`. Also: presence-only never sets `connected=True`; a mocked successful check sets `connected=True`; a mocked failed/erroring/timed-out check never sets `connected=True`; missing/malformed config yields `configured=False` safely, not a crash. Verify: `python3 -m pytest tests/test_groundwork_integrations.py -k state -q`.

## 3. CLI commands

- [x] 3.1 Implement `list` (table: Integration | Access | State, State = the derived summary label) and `show <name>` (purpose, capabilities, approved mechanisms, trust/access characteristics, configuration requirements, the three raw `available`/`configured`/`connected` booleans shown individually, plus the summary label) using argparse, matching `groundwork_config.py`'s CLI shape.
- [x] 3.2 Implement the Routines-dependency line in `show`, reading `groundwork_routines.py`'s own routine configuration deterministically (no inference for playbooks); handle an unknown integration name in `show` with a clean "not known" message, no traceback.
- [x] 3.3 Add tests: `list` output formatting (one row per catalog entry); `show` output for a known integration includes all required fields; `show` for an unknown name reports not-known without crashing; Routines-dependency line only lists a Routine when its stored config explicitly declares that mechanism; a scan of all command output against credential/token/password/API-key/secret-shaped patterns finds nothing. Verify: `python3 -m pytest tests/test_groundwork_integrations.py -k "cli or secret" -q`.

## 4. `used` observation from existing telemetry

- [x] 4.1 Implement a read-only lookup of the most recent telemetry record(s) (`groundwork_telemetry.py`'s existing JSONL output) for a `used` signal per integration (`True`/`False`/`None` for unknown) — kept separate from the three readiness booleans, never merged into `summary_state()`.
- [x] 4.2 Add a test with a fixture telemetry file confirming `used=True` reflects a real recent record, `used=False` when telemetry reliably shows no invocation, and `used=None` (reported as `unknown`) when no telemetry file exists or the record is inconclusive. Verify: `python3 -m pytest tests/test_groundwork_integrations.py -k used -q`.

## 5. Install and doctor wiring

- [x] 5.1 Add `groundwork_integrations.py` to `install.sh`'s script-install list (same treatment as `groundwork_report.py`/`groundwork_config.py`/`groundwork_routines.py`) and verify `./install.sh` (or a dry review of the diff) places and `chmod +x`'s it identically to the existing three.
- [x] 5.2 Add an "Integrations" section to `setup.sh --doctor` that shells out to `groundwork_integrations.py list` and indents its output, mirroring the existing Routines doctor section; verify by running `./setup.sh --doctor` against a repo checkout and confirming the new section appears with no error.

## 6. Documentation

- [x] 6.1 Extend `docs/INTEGRATIONS.md` with the capability-id / approved-mechanism information per domain and a short section describing the new `list`/`show` commands.
- [x] 6.2 Add `tests/test_groundwork_integrations.py` coverage asserting every catalog integration name has a corresponding row in `docs/INTEGRATIONS.md` (doc-consistency check, test-only text scan — never runtime logic); verify: `python3 -m pytest tests/test_groundwork_integrations.py -k doc_consistency -q`.
- [x] 6.3 Add a short, clearly-labeled architecture note (in `docs/ARCHITECTURE.md`) stating Groundwork relies on Claude Code's native Tool Search for lazy MCP tool-schema loading and provides capability/integration guidance only, never enforced per-task MCP activation.
- [x] 6.4 Update `README.md`'s repository-layout tree with the new script and test file, and add a `CHANGELOG.md` entry describing the Integration Catalog addition.

## 7. Full validation

- [x] 7.1 Run the full test suite (`python3 -m pytest tests -q`) and confirm no regressions beyond this change's own new tests.
- [x] 7.2 Run `openspec validate add-integration-catalog --strict` and resolve any reported issues.
- [x] 7.3 Dispatch an independent, fresh-context review of the diff; fix only findings it reports as material (MUST FIX), and re-run the affected tests after each fix.
