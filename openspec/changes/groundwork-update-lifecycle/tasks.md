# Tasks — Groundwork version/update lifecycle (Next Release Program, Phase 3)

## 0. Baseline
- [x] 0.1 Verify PR #32 (Phase 2) merged, local `main` == `origin/main` before starting
- [x] 0.2 Investigate current state: installed VERSION source, install.sh's VERSION derivation,
      published GitHub Releases/tags (confirmed `v2.2.0` is the only published, non-draft,
      non-prerelease release), current install/backup/rollback mechanism
      (`setup.sh`'s `make_backup()`/`run_rollback()`/`latest_backup()`, `choose_schedule()`'s
      non-interactive reset-to-`weekly` gap), Groundwork-owned vs. user-owned state
- [x] 0.3 Product Value Gate for all 6 commands (see `proposal.md`)

## 1. Implementation
- [x] 1.1 `scripts/groundwork_update.py`: `update [--check] [--version X]` /
      `rollback [--version X]` — GitHub Releases API as the authoritative source
      (`latest_release`/`find_release`, never draft/prerelease/arbitrary-ref), stdlib
      `urllib`+`tarfile` fetch (see design.md DECISION 1), path-traversal-safe extraction
      (`_safe_extract`), CHANGELOG cross-check safeguard, profile/schedule/Agent-Teams
      preservation (see design.md DECISION 3), version-labeled rollback via existing
      `BACKUP-INFO.txt` data (see design.md DECISION 4)
- [x] 1.2 `scripts/groundwork_cli.py`: add `update`/`rollback` as pure pass-through dispatches,
      same `argv[0]` interception pattern as Phase 2's `integrations` (works around
      https://bugs.python.org/issue9334)
- [x] 1.3 `install.sh`: copy `scripts/groundwork_update.py` into the installed bin dir; update the
      `setup.sh` install-step comment to note `--rollback` (like `--doctor`) is also safe to run
      from the installed copy

## 2. Tests
- [x] 2.1 `tests/test_groundwork_update.py` (new) — semver parsing; `latest_release`/`find_release`
      reject draft/prerelease/non-semver/unreachable-network (network stubbed, never live);
      `_safe_extract` rejects path traversal; `_find_backup_for_version` newest-match lookup;
      `--check` non-mutating output including the UNKNOWN path; profile/schedule/Agent-Teams
      preservation reads; full `update`/`rollback` orchestration end to end against a stub
      installer (schedule/profile/teams reach the invoked `setup.sh` verbatim, already-on-target
      no-op, incomplete/mismatched archive refusal, install-failure rollback hint,
      download/extract failure handling, rollback dispatch with and without `--version`)
- [x] 2.2 `tests/test_groundwork_cli.py::test_update_rollback_dispatches_not_reimplements` —
      real install, `--help` reaches the installed script's real help text for both subcommands,
      network-free error paths (`--check --version` combo, `rollback --version` with no matching
      backup) byte-identical to direct invocation, top-level `--help` lists both subcommands

## 3. Documentation
- [x] 3.1 `docs/UPGRADE-ROLLBACK.md`: document `groundwork update`/`update --check`/
      `update --version`/`rollback`/`rollback --version` as the preferred interface; keep the
      existing `git pull && ./setup.sh` workflow documented as a valid, unchanged alternative
- [x] 3.2 `README.md`: add `groundwork update`/`rollback` to the documented command list

## 4. Validation
- [x] 4.1 `python3 -m pytest tests -q` — full suite green (104 passed)
- [x] 4.2 `openspec validate groundwork-update-lifecycle --strict` — valid
- [x] 4.3 Real runtime validation in a disposable sandbox (never the real `$HOME`): `setup.sh
      --non-interactive --profile work --schedule monthly --agent-teams` clean install;
      `groundwork version`; a real live `update --check` against the actual GitHub Releases API
      (Current 2.1.0 / Latest 2.2.0 / Update available: YES); `update --version 9.9.9` realistic
      failure (clean rejection, no mutation); a real live `groundwork update` that fetched and
      installed the actual published v2.2.0 release end to end; post-update state confirmed —
      VERSION, an unrelated `settings.json` key, a planted `mcpServers` entry, profile (`work`),
      Agent-Teams (`1`), and schedule (`monthly`, proving the non-interactive reset-to-weekly gap
      stays closed) all preserved; `doctor`/`integrations list`/statusLine all functional after
      update; `groundwork rollback` restored the complete pre-update installation (VERSION back to
      2.1.0, unrelated settings key intact), not just the VERSION file; no leftover temp
      extraction directory after either run
- [ ] 4.4 Independent fresh-context review focused on the material-risk list (wrong release
      source, unsafe version resolution, arbitrary-ref/code execution, path traversal, subprocess
      injection, credential exposure, config/settings loss, partial/broken update,
      `CLAUDE_CONFIG_DIR` breakage, rollback corruption, duplicated installer logic, materially
      inaccurate docs) — fix MUST FIX only

## 5. Report
- [ ] 5.1 Commit, push `feat/groundwork-update-lifecycle`, create a draft PR — do not merge, do
      not start Phase 4, do not create the next Groundwork release
