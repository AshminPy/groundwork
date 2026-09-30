# Tasks — Groundwork Routine CLI UX (Next Release Program, Phase 4)

## 0. Baseline
- [x] 0.1 Verify PR #33 (Phase 3) merged, local `main` == `origin/main`, post-merge validation
      green before starting (pytest 104 passed, `openspec validate --strict` valid, real
      `groundwork version`/`update --check`/`integrations list`/`doctor` all worked)
- [x] 0.2 Investigate the existing `scripts/groundwork_routines.py` implementation in full (own
      argparse CLI, truth model, execution engine, scheduling mechanism, the six shipped
      routines) and `docs/ROUTINES.md`/`setup.sh`'s routines sections before designing anything
- [x] 0.3 Product Value Gate for `list`/`status`/`run`/`doctor`/`schedule`/`unschedule` (see
      `proposal.md`)

## 1. Implementation
- [x] 1.1 `scripts/groundwork_routines.py`: `doctor` gains an optional routine-name argument,
      filtering `_doctor_rows()` before any per-routine check runs; bare `doctor` (setup.sh's own
      call site) unchanged (see design.md DECISION 2)
- [x] 1.2 `scripts/groundwork_cli.py`: add `routines` as a pure `argv[0]`-interception
      pass-through, identical pattern to `integrations`/`update`/`rollback` (see design.md
      DECISION 1)
- [x] 1.3 No `install.sh` change needed — `groundwork_routines.py`/`groundwork_config.py` were
      already copied to the installed bin dir by the existing Groundwork 2.1 install steps

## 2. Tests
- [x] 2.1 `tests/test_groundwork_routines.py::test_doctor_name_filter` — bare `doctor` unaffected,
      a filtered row is identical to the unfiltered row, filtering to one routine never probes
      another (real call-count assertion via a stub `gh` binary), CLI-level byte-parity, unknown
      name rejected via the existing `choices=` convention
- [x] 2.2 `tests/test_groundwork_cli.py::test_routines_dispatches_not_reimplements` — real
      install, byte-identical output vs. direct invocation across `list`/`doctor`/`doctor NAME`,
      `--help` reaches the real installed script's help text, unknown-name error path, top-level
      `groundwork --help` still lists `routines`

## 3. Documentation
- [x] 3.1 `README.md`: document `groundwork routines list`/`run`/`doctor`/`schedule` alongside the
      existing `--help`/`version`/`doctor`/`integrations`/`update`/`rollback` documentation
- [x] 3.2 `docs/ROUTINES.md`: document the `groundwork routines` CLI as the preferred interface;
      keep the direct-script invocation documented as an unchanged, working alternative

## 4. Validation
- [x] 4.1 `python3 -m pytest tests -q` — full suite green
- [x] 4.2 `openspec validate groundwork-routine-cli-ux --strict`
- [x] 4.3 Real runtime validation in a disposable sandbox (never the real `$HOME`): a real
      `setup.sh --non-interactive --capability-profile sre-cloudops` install; `groundwork routines
      list`/`doctor` run from `/tmp` (installed CLI outside the source repo) against a custom
      `CLAUDE_CONFIG_DIR`; `doctor`/`doctor NAME` covering all three readiness states for real
      (READY: `news`; BLOCKED: `jira_eod`/`pr_followup`/`weekly_status`/`work_digest`; NOT ENABLED:
      `doc_drift`); `run pr_followup` (BLOCKED) refused in 0.09s with zero subprocess spawned;
      `run news` — a real, live `claude -p` call (27.6s) that returned a genuine `PARTIAL`
      semantic status, proving the result-parsing pipeline against real model output, not a stub;
      `doctor`/`list`/the stored result file/telemetry all correctly reported the new PARTIAL and
      BLOCKED run results afterward, with the readiness-time and run-result vocabularies kept
      visibly distinct as designed
- [x] 4.4 Independent fresh-context review — verdict **approve, 0 MUST FIX**. The loop-variable
      shadowing risk named in the review brief was checked line-by-line and adversarially
      reproduced (the reviewer deliberately reintroduced the bug in a scratch copy and confirmed
      `test_doctor_name_filter` fails correctly against it — the test's differential design, not
      an accident, catches this class of bug). No execution-engine duplication, no readiness/
      safety bypass, no new writes to `config.json`/`settings.json`, `install.sh` confirmed
      unchanged, documentation confirmed accurate against the real diff. One NICE TO HAVE (the
      hand-written `--help` summary line can drift — an already-accepted Phase 2 precedent, not
      new risk); no fix needed.

## 5. Report
- [x] 5.1 Commit, push `feat/groundwork-routine-cli-ux`, create a draft PR — do not merge, do not
      start release work. PR #34, draft.
