# Design — Groundwork Routine CLI UX (Next Release Program, Phase 4)

## Architecture-quality §2 answers (MATERIAL tier: new user-facing CLI surface)

- **What is likely to change?** More `groundwork_routines.py` subcommands could be added later;
  the pass-through dispatch (DECISION 1) already accommodates that with zero `groundwork_cli.py`
  changes, exactly as it already did for `integrations`/`update`/`rollback`.
- **What should be configuration rather than code?** Nothing new — routine enablement/scope/
  schedule stay entirely in the existing `config.json`, untouched by this change.
- **What needs a stable interface?** `groundwork routines <subcommand> [args...]` — the contract is
  "forwarded verbatim," itself the stable interface; the actual subcommand set is owned entirely by
  `groundwork_routines.py`.
- **How would another instance/provider/environment be added?** Not applicable — no new routine,
  access mechanism, or scheduler is introduced.
- **Which manual operational steps can reasonably be automated?** None beyond what already exists;
  this change only makes existing automation (`run`, `schedule`) discoverable from one entry point.
- **What fails if a dependency is unavailable, and how is that failure handled/surfaced?** If the
  installed `groundwork_routines.py` is missing, `groundwork routines ...` prints a clear stderr
  message naming the missing path and exits 1 — same pattern as `doctor`'s/`integrations`'s/
  `update`'s existing guards.
- **How will an operator observe/troubleshoot this?** `doctor [NAME]` — unchanged purpose, now
  reachable with a single-routine filter.
- **How will it be tested? Deployed/rolled back?** Real subprocess tests (see `tasks.md`); deployed
  via the existing `install.sh` (zero changes needed — both scripts already copied to the installed
  bin dir since Groundwork 2.1); rollback is the existing `setup.sh --rollback`/git revert,
  unchanged.
- **What security boundary exists?** None new — `groundwork routines` only ever forwards to a
  script that already runs with the invoking user's own permissions, using the same fail-closed
  `claude -p --permission-mode dontAsk --permission-prompts none` invocation `run_routine()`
  already builds; no privilege change, no new credential handling.
- **Scaling/cost implications?** None — a single local subprocess call, same cost profile as every
  other dispatch subcommand.

## DECISION 1 — `groundwork routines` is a pure `argv[0]`-interception pass-through, identical to
the `integrations`/`update`/`rollback` pattern

EVIDENCE: Read `scripts/groundwork_routines.py` directly (full file) — it already has its own
complete, tested argparse CLI (`run`, `schedule`, `list`, `latest`, `doctor`), installed
unconditionally by `install.sh` (`install.sh:113-114`, alongside `groundwork_config.py` which it
imports) since Groundwork 2.1, unchanged by this phase except `doctor`'s new optional name filter
(DECISION 2). `integrations`/`update`/`rollback`'s own dispatch in `groundwork_cli.py` already
established the working pattern — `main()` intercepts the subcommand name before
`argparse.parse_args()` ever runs (working around the documented `argparse.REMAINDER` + `-h`
interaction, https://bugs.python.org/issue9334), with a `add_help=False` stub subparser existing
only so `groundwork --help`'s summary lists the subcommand.

WHY: this is the smallest design that satisfies "reuse the existing implementation, do not
duplicate its business logic" literally — not even the list of routine subcommand names is
duplicated here; `groundwork_routines.py`'s own argparse remains the single source of truth.
Reusing the exact pattern already proven correct for three prior subcommands (rather than
inventing a fourth variant) keeps `groundwork_cli.py` genuinely thin and its dispatch logic
uniform.

TRADEOFFS: `groundwork --help`'s one-line summary for `routines` is hand-written, so it can drift
from the real subcommand list over time — acceptable, since `groundwork routines --help` (the
actually-authoritative detail) can never drift, matching the same accepted tradeoff from Phase 2.

VALIDATION METHOD: `tests/test_groundwork_cli.py::test_routines_dispatches_not_reimplements` —
byte-identical output vs. direct invocation across `list`/`doctor`/`doctor NAME`, `--help`
pass-through, unknown-name error path, top-level `--help` listing.

UNCERTAINTY: none material.

## DECISION 2 — `doctor` gains an optional routine-name filter inside `groundwork_routines.py`
itself, not a client-side filter in `groundwork_cli.py`

EVIDENCE: `_doctor_rows(cfg)` (`groundwork_routines.py:714-752`, pre-existing) already builds one
dict per routine by iterating `ROUTINES.items()`; `setup.sh --doctor`'s `verify_capabilities()`
calls the bare `doctor` subcommand with no name (`setup.sh:745`) and must keep working unchanged.
The requested shape (`groundwork routines doctor <routine>`) needs narrowing to one routine's
detail — exactly the gap Phase 2 closed for `groundwork_integrations.py` with its own `doctor NAME`
addition.

WHY: filtering inside `_doctor_rows()` itself (an early `continue` when `name is not None and
rname != name`) means a probe that has a real side effect — `check_access()`'s live `gh auth
status` subprocess call for `pr_followup` — is never run for routines nobody asked about, not just
excluded from the printed output after being computed anyway. Filtering in `groundwork_cli.py`
instead (asking `groundwork_routines.py` for everything, then discarding rows client-side) would
either duplicate `_doctor_rows()`'s per-routine logic there or waste the real connectivity check on
every other routine regardless of what was requested. Keeping the filter inside the existing
function, with a default of `None` that reproduces today's exact behavior, is the smallest change
that satisfies the requirement without touching `setup.sh`'s call site or any other caller.

TRADEOFFS: none identified — purely additive, and the `choices=sorted(ROUTINES)` argparse
validation (matching `run`/`schedule`/`latest`'s existing convention) gives unknown-name rejection
for free, with no bespoke error-handling code needed.

VALIDATION METHOD: `tests/test_groundwork_routines.py::test_doctor_name_filter` — bare `doctor`
still covers all six routines (regression-proofing `setup.sh --doctor`'s call site); a filtered row
is identical to its unfiltered counterpart; filtering to `jira_eod` never invokes `pr_followup`'s
real `gh auth status` check (proven via a call-counting stub, the same technique Phase 2's
`test_doctor_command` used for the identical concern); filtering to `pr_followup` itself still runs
that real check; CLI-level output is byte-identical to `format_doctor_text()` on just that routine's
row; an unknown name is rejected the same way `run`/`schedule`/`latest` already reject one.

UNCERTAINTY: none material.
