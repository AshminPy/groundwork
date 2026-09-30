# Proposal — Groundwork Routine CLI UX (Next Release Program, Phase 4)

## Why

Phases 1–3 gave Groundwork a single discoverable entry point (`groundwork --help`/`version`/
`doctor`/`integrations`/`update`/`rollback`). The Routines capability
(`scripts/groundwork_routines.py`, Groundwork 2.1) already has its own complete, tested
`list`/`run`/`schedule`/`latest`/`doctor` CLI — but, like the Integration Catalog before Phase 2,
it is only reachable by knowing its exact installed path
(`python3 ~/.claude/groundwork/bin/groundwork_routines.py <cmd>`). `setup.sh --routines` exposes
only a subset (`list`/`latest`); `run` (manual trigger) isn't reachable from `setup.sh` at all.

### Product Value Gate (concise)

| Command | Decision | Why |
|---|---|---|
| `groundwork routines list` | BUILD | Real, existing, tested (`_cmd_list`) — shows enabled/mutates/schedule/readiness/last-run per routine. Pure pass-through, same pattern as `integrations`/`update`. |
| `groundwork routines status` | DO NOT BUILD (as a separate command) | `list` already **is** the status view — one line per routine with enabled/mutates/schedule/readiness/last-run. A second command name for identical output would be duplication, not new value; `list` serves this purpose. |
| `groundwork routines run <routine>` | BUILD | Real, existing, already safety-controlled synchronous execution path (`run_routine()` via `_cmd_run`) — the exact same code path production scheduled (launchd) invocations already use, confirmed by reading the plist's own `ProgramArguments`. Clear value: manual trigger with immediate feedback. |
| `groundwork routines doctor <routine>` | BUILD REDUCED SCOPE | `doctor` (bare, all routines) already exists and already backs `setup.sh --doctor`. Extended `groundwork_routines.py`'s own `_doctor_rows()`/`_cmd_doctor` with an **optional** name filter — mirrors the Phase 2 `groundwork_integrations.py doctor NAME` precedent exactly: same per-routine computation, no new probes, bare `doctor` (setup.sh's call site) unchanged. |
| `groundwork routines schedule <routine> <freq>` | BUILD | Real, existing, already production-used (`setup.sh` calls it internally during capability configuration) launchd/cron management — currently unreachable from the `groundwork` CLI. Real value: change a routine's schedule without re-running the full `setup.sh --configure` wizard. |
| `groundwork routines unschedule <routine>` | DO NOT BUILD | `schedule <routine> disabled` already is the exact, existing, documented way to unschedule (deletes the plist) — a second spelling for the same action adds no capability, only a naming preference. |
| `groundwork routines latest <routine>` | DO NOT BUILD (not in requested scope) | Exists and works, but wasn't part of the requested CLI shape; the existing direct-script interface (`groundwork_routines.py latest NAME`, documented in `docs/ROUTINES.md`) stays the way to reach full last-run content, preserved unchanged. |

## What Changes

- `groundwork routines ...` — a new top-level subcommand on the existing `groundwork` CLI that
  forwards every argument verbatim to the installed `groundwork_routines.py` (pure pass-through,
  zero business logic duplicated — same `argv[0]` interception pattern already used for
  `integrations`/`update`/`rollback`, working around the same `argparse.REMAINDER` + `-h`
  interaction — `https://bugs.python.org/issue9334`).
- `scripts/groundwork_routines.py`'s `doctor` subcommand gains an **optional** routine-name
  argument, narrowing its output to one routine — the same per-routine computation `_doctor_rows()`
  already performs, filtered before any routine-specific check runs (so filtering to one routine
  never triggers another routine's connectivity probe). The bare `doctor` call (no name) — the
  exact call `setup.sh --doctor`'s `verify_capabilities()` already makes — is unchanged.
- No `install.sh` change: `groundwork_routines.py`/`groundwork_config.py` are already copied to the
  installed bin dir (since Groundwork 2.1).
- Tests: `tests/test_groundwork_routines.py` gains `test_doctor_name_filter` (single-routine
  filtering matches the unfiltered row exactly, never probes a routine that wasn't asked about,
  CLI-level byte-parity, unknown-name rejection via the same `choices=` convention `run`/`schedule`/
  `latest` already use); `tests/test_groundwork_cli.py` gains a dispatch-fidelity test mirroring
  `test_integrations_dispatches_not_reimplements`.
- Docs: `README.md`/`docs/ROUTINES.md` updated to document `groundwork routines ...` as the
  preferred interface, direct script invocation kept as a documented, unchanged alternative.

## Non-Goals (explicitly out of scope for this change)

- No second execution engine — `run` always calls the existing `run_routine()`/`build_command()`
  (`--permission-mode dontAsk --permission-prompts none`, never a bypass flag), unmodified.
- No change to the truth model — `enabled`/`capability_blocked_reason`/`access`/`available`/
  `connected`/`readiness_state()`'s `READY`/`READY (connectivity not verifiable)`/`BLOCKED`/
  `NOT ENABLED`, and the separate run-result vocabulary (`complete`/`partial`/`blocked`/`failed`/
  `skipped`), are all unchanged and kept visibly distinct, not collapsed into one status.
- No new scheduling mechanism — `schedule` dispatches to the existing, already-tested
  `schedule_routine()` (macOS launchd; a printed cron-elsewhere note on other OSes), unchanged.
- No `groundwork routines status`/`unschedule`/`latest` subcommands — see the Product Value Gate.
- No change to `groundwork_integrations.py` or any prior phase's behavior.

## Acceptance Criteria (Phase 4 gate)

1. `groundwork routines list`/`run NAME`/`doctor [NAME]`/`schedule NAME FREQ` each produce output
   byte-identical to invoking the installed `groundwork_routines.py` directly with the same
   arguments — proving dispatch, not reimplementation.
2. `groundwork routines --help` reaches the installed script's own real help text.
3. `doctor NAME`'s row is identical to that routine's row in the unfiltered `doctor` output, and
   filtering to one routine never triggers a connectivity check for a different routine.
4. `run NAME` never hangs waiting for an interactive prompt — the fetched command always includes
   `--permission-mode dontAsk --permission-prompts none`, never a bypass flag (already enforced by
   the existing `test_build_command_always_fails_closed_for_every_routine`, unmodified by this
   change and re-verified still green).
5. Full test suite green, `openspec validate groundwork-routine-cli-ux --strict` valid, independent
   fresh-context review with 0 MUST FIX remaining.
