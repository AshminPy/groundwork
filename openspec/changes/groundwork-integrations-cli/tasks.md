# Tasks — Groundwork Integrations CLI (Next Release Program, Phase 2)

## 0. Baseline
- [x] 0.1 Verify PR #30 merged, local `main` == `origin/main`, post-merge validation green before
      starting (pytest 84 passed, `openspec validate groundwork-cli-foundation --strict` valid,
      real `groundwork --help`/`version`/`doctor` all worked)
- [x] 0.2 Investigate the existing `scripts/groundwork_integrations.py` implementation (full file
      read) and `docs/INTEGRATIONS.md`/`setup.sh`'s `verify_capabilities()` before designing
      anything — confirmed it already has a complete, tested `list`/`show`/`refresh` CLI and is
      already installed by `install.sh`, unconditionally, since Groundwork 2.1

## 1. Implementation
- [x] 1.1 `scripts/groundwork_integrations.py`: add `doctor NAME` — reason lines for each
      observation, computed from the existing probes, probing each mechanism exactly once (see
      design.md DECISION 2 for the double-probe bug caught and fixed before shipping)
- [x] 1.2 `scripts/groundwork_cli.py`: add `integrations` as a pure `argparse.REMAINDER`
      pass-through; fix the `-h`/`--help` interception bug found during live testing by
      intercepting `integrations` in `main()` before `argparse` parses it (see design.md
      DECISION 1)
- [x] 1.3 No `install.sh` change needed — `groundwork_integrations.py` and `groundwork_cli.py` were
      both already copied to the installed bin dir by the existing Phase 1/2.1 install steps

## 2. Tests
- [x] 2.1 `tests/test_groundwork_integrations.py::test_doctor_command` — reason lines present,
      `doctor`'s observations match `show`'s exactly, each connectivity probe runs exactly once
      (real call-count assertion via a stub binary), unknown-name error path
- [x] 2.2 `tests/test_groundwork_cli.py::test_integrations_dispatches_not_reimplements` — real
      install, byte-identical output vs. direct invocation across `list`/`show`/`doctor`,
      `--help` reaches the real installed script's help text (not a stub), unknown-name error
      path, top-level `groundwork --help` still lists `integrations`

## 3. Documentation
- [x] 3.1 `README.md`: document `groundwork integrations list`/`show`/`doctor`/`refresh` alongside
      the existing `--help`/`version`/`doctor` documentation
- [x] 3.2 `docs/INTEGRATIONS.md`: document the `groundwork integrations` CLI as the preferred
      interface; keep the direct-script invocation documented as an unchanged, working alternative

## 4. Validation
- [x] 4.1 `python3 -m pytest tests -q` — full suite green
- [x] 4.2 `openspec validate groundwork-integrations-cli --strict`
- [x] 4.3 Real end-to-end runtime validation: disposable `$HOME`/`$CLAUDE_CONFIG_DIR` sandbox, real
      `install.sh`, `groundwork integrations list/show/doctor/refresh/--help` all exercised for
      real, not assumed
- [x] 4.4 Independent fresh-context review — verdict **0 MUST FIX**. Verified live: the
      `--help` bug claim reproduced in isolation (confirms DECISION 1's fix is real, not
      assumed), `doctor`/`show` observations byte-matched in both a connected and
      not-connected state, the `gh auth status` call-count fix confirmed via a stub binary
      (exactly one call), truth model confirmed untouched by diff. One SHOULD FIX — the
      `any(...)` combination formula was written in two places (inline in `_cmd_doctor` and in
      `determine_observation`), a real "second independent computation" risk even though the two
      were behaviorally identical today. Fixed by extracting `_combine_observation()` as the one
      place the formula lives; both callers now share it while `_cmd_doctor` still probes each
      mechanism exactly once (the earlier fix is preserved, not reverted). Re-validated: full
      suite green (86 passed), `openspec validate --strict` valid.

## 5. Report
- [x] 5.1 Commit, push, create/update a draft PR — do not merge
