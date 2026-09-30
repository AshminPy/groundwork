# groundwork-routine-cli-ux Specification

## Purpose
Exposes the existing Routines capability (`scripts/groundwork_routines.py`) through the stable
`groundwork` CLI as a discoverable `groundwork routines` subcommand — `list`/`run`/`schedule`/
`doctor` — without reimplementing its execution engine, truth model, or scheduling mechanism.
`doctor` additionally gains an optional routine-name filter, narrowing its existing per-routine
computation to one routine on request, from the same probes the unfiltered `doctor` already uses.

## ADDED Requirements

### Requirement: `groundwork routines` dispatches to the installed Routines script
The `groundwork` CLI SHALL provide a `routines` subcommand that forwards every argument after
`routines` verbatim to the installed `groundwork_routines.py`, producing output and an exit code
byte-identical to invoking that script directly with the same arguments.

#### Scenario: `list` produces identical output to direct invocation
- **GIVEN** Groundwork is installed
- **WHEN** the user runs `groundwork routines list`
- **THEN** stdout and the exit code are byte-identical to running the installed
  `groundwork_routines.py list` directly

#### Scenario: `--help` reaches the installed script's real help text
- **GIVEN** Groundwork is installed
- **WHEN** the user runs `groundwork routines --help`
- **THEN** the output is the installed `groundwork_routines.py`'s own help text, not a generic or
  truncated stub

#### Scenario: missing installed script fails cleanly
- **GIVEN** `groundwork_routines.py` is not present at its expected installed path
- **WHEN** the user runs `groundwork routines list`
- **THEN** the command prints a clear stderr message naming the missing path and exits non-zero,
  with no unhandled traceback

### Requirement: `groundwork routines run <name>` never duplicates the existing execution engine
`run <name>` SHALL execute via the existing `run_routine()`/`build_command()` code path unchanged —
the exact command construction (`--permission-mode dontAsk --permission-prompts none`, tool
allowlist from `_capabilities_for()`) that production scheduled invocations already use, never a
second, independently-built command.

#### Scenario: a scheduled unattended invocation and a manual `groundwork routines run` use the
same command shape
- **GIVEN** any of the six shipped routines, fully configured
- **WHEN** the routine is invoked via `groundwork routines run <name>` and separately via the
  launchd-scheduled path
- **THEN** both invocations are built by the same `build_command()` function and both always
  include `--permission-mode dontAsk` and `--permission-prompts none`, and never a permission-bypass
  flag

### Requirement: `groundwork_routines.py doctor` optionally narrows to one routine without
changing its data or side effects
`doctor` (no argument) SHALL continue to report every routine, exactly as before this change —
in particular, `setup.sh --doctor`'s existing call site is unaffected. `doctor NAME` SHALL report
only that routine's row, computed by the same per-routine logic the unfiltered call already uses,
and SHALL NOT perform any check (including a live connectivity probe) for a routine other than the
one requested.

#### Scenario: bare `doctor` is unchanged
- **GIVEN** any installation state
- **WHEN** `doctor` is run with no routine name
- **THEN** its output covers all six routines, identical to this command's behavior before this
  change

#### Scenario: `doctor NAME`'s row matches the unfiltered row exactly
- **GIVEN** any known routine
- **WHEN** `doctor NAME` and bare `doctor` are run in the same environment
- **THEN** the row for that routine is identical between the two outputs

#### Scenario: filtering to one routine never probes another
- **GIVEN** two routines where only one has a real, executable connectivity check (e.g.
  `pr_followup`'s `gh auth status`)
- **WHEN** `doctor` is run scoped to the routine WITHOUT the real check
- **THEN** the other routine's connectivity check is never executed

#### Scenario: an unknown routine name fails cleanly
- **GIVEN** a name not among the six shipped routines
- **WHEN** `doctor NAME` is run
- **THEN** it exits non-zero with an argparse-reported invalid-choice error, no traceback

### Requirement: the Routines truth model is unchanged by this CLI surface
Adding `groundwork routines` and `doctor`'s name filter SHALL NOT alter the existing readiness
states (`NOT ENABLED`/`BLOCKED`/`READY`/`READY (connectivity not verifiable)`), the separate
run-result states (`complete`/`partial`/`blocked`/`failed`/`skipped`), or collapse them into a
single status.

#### Scenario: readiness and run-result vocabularies stay distinct
- **GIVEN** any routine's `doctor`/`list` output and its most recent run result
- **WHEN** both are read through any entry point (direct script or `groundwork routines`)
- **THEN** the readiness-time state and the run-result state are reported using their existing,
  separate vocabularies, never merged into one combined value
