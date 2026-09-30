# Design — Groundwork Integrations CLI (Next Release Program, Phase 2)

## Architecture-quality §2 answers (MATERIAL tier: new user-facing CLI surface)

- **What is likely to change?** More Integration Catalog subcommands could be added later
  (e.g. an interactive `configure`); the pass-through dispatch design (DECISION 1) already
  accommodates that with zero `groundwork_cli.py` changes.
- **What should be configuration rather than code?** Nothing new — the Catalog's existing
  `config.json`-driven `configured` observation is untouched.
- **What needs a stable interface?** `groundwork integrations <subcommand> [args...]` — the
  contract is "forwarded verbatim," which is itself the stable interface; the actual subcommand
  set is owned entirely by `groundwork_integrations.py`.
- **How would another instance/provider/environment be added?** Not applicable — this change adds
  no new integration to the catalog, only a CLI surface over the existing one.
- **Which manual operational steps can reasonably be automated?** None identified for this change.
- **What fails if a dependency is unavailable, and how is that failure handled/surfaced?** If the
  installed `groundwork_integrations.py` is missing, `groundwork integrations ...` prints a clear
  stderr message naming the missing path and exits 1 — same pattern as `doctor`'s existing guard
  for a missing installed `setup.sh`.
- **How will an operator observe/troubleshoot this?** `doctor NAME` exists specifically for this —
  a one-line reason per observation, narrated from the existing probes.
- **How will it be tested? Deployed/rolled back?** Real subprocess tests (see `tasks.md`); deployed
  via the existing `install.sh` (zero changes needed — `groundwork_integrations.py` and
  `groundwork_cli.py` are both already copied to the installed bin dir); rollback is the existing
  `setup.sh --rollback` / git revert, unchanged.
- **What security boundary exists?** None new — `groundwork integrations` only ever forwards to a
  script that already runs with the invoking user's own permissions; no privilege change, no new
  credential handling (see DECISION 1 evidence).
- **Scaling/cost implications?** None — a single local subprocess call, same cost profile as
  `doctor`'s existing dispatch.

## DECISION 1 — `groundwork integrations` is a pure `argparse.REMAINDER` pass-through, not a
mirrored subparser tree

EVIDENCE: Read `scripts/groundwork_integrations.py` directly (full file, not assumed) — it already
has its own complete, tested argparse CLI (`list`, `show NAME`, `refresh`, now `doctor NAME`),
installed unconditionally by `install.sh` (confirmed: `cp "$HERE/scripts/groundwork_integrations.py"
"$CLAUDE_DIR/groundwork/bin/"`, present since Groundwork 2.1, unchanged by this Phase 2 work).
`doctor`'s own dispatch pattern (Phase 1) — `subprocess.run(["bash", INSTALLED_SETUP_SH,
"--doctor"])` — is the established precedent: forward to an installed, already-tested script,
never reimplement its logic or its argument grammar.

First attempt mirrored `groundwork_integrations.py`'s subcommand names as a nested
`groundwork_cli.py` subparser using `nargs=argparse.REMAINDER` for the trailing args. Live-tested
(`groundwork integrations --help`) and found broken: argparse's own `-h`/`--help` registration on
the intermediate `integrations` subparser intercepted `--help` before `REMAINDER` ever saw it,
printing a useless 3-line stub instead of `groundwork_integrations.py`'s real, detailed help — a
confirmed, live-reproduced instance of the documented CPython `argparse.REMAINDER` + `-h`
interaction (https://bugs.python.org/issue9334: REMAINDER does not reliably coexist with `-h`
interception across parser levels).

Fix: `main()` intercepts `argv[0] == "integrations"` and calls `cmd_integrations(argv[1:])`
directly, before `build_parser().parse_args()` ever runs — the `integrations` entry in
`build_parser()` exists only so it appears in `groundwork --help`'s subcommand summary
(`add_help=False` there too, since that subparser is never actually used to parse `integrations`'s
own args). Re-tested live after the fix: `groundwork integrations --help` now reaches
`groundwork_integrations.py`'s own real help text, byte-identical to the direct invocation
(`tests/test_groundwork_cli.py::test_integrations_dispatches_not_reimplements`).

WHY: this is the smallest design that satisfies "reuse the existing implementation, do not
duplicate its business logic" literally — not even the list of subcommand names is duplicated;
`groundwork_integrations.py`'s own argparse is the single source of truth for what `integrations`
accepts, so the two can never drift out of sync as it gains subcommands later (DECISION vs. the
rejected alternative of a mirrored subparser tree, which would need a `groundwork_cli.py` change
every time `groundwork_integrations.py` adds a subcommand).

TRADEOFFS: `groundwork --help`'s one-line summary for `integrations` is hand-written (not derived),
so it can drift from the real subcommand list over time — acceptable, since `groundwork
integrations --help` (the actually-authoritative detail) can never drift, and the top-level summary
line already says "see 'groundwork integrations --help'".

VALIDATION METHOD: live-reproduced the bug before fixing it (not just reasoned about it); live
re-tested the fix; `tests/test_groundwork_cli.py::test_integrations_dispatches_not_reimplements`
codifies both (dispatch fidelity across 3 real subcommands, and the `--help` pass-through
specifically) so the fix can't silently regress.

UNCERTAINTY: none material.

## DECISION 2 — `doctor NAME` narrates existing observations; probes each mechanism exactly once

EVIDENCE: `groundwork_integrations.py`'s existing `_mechanism_available`/`_mechanism_connected`
return plain booleans and are called directly, by boolean identity (`is True`/`is False`), by ~8
existing tests in `tests/test_groundwork_integrations.py` — changing their signature to also
return a reason would have broken all of them for no functional gain. Instead, `doctor` is
implemented as a pure narration layer: it computes each mechanism's `available`/`connected` boolean
itself (calling the exact same, unmodified primitive functions `show`/`list`/`refresh` already use)
and passes the already-computed boolean into a small reason function
(`_availability_reason`/`_connected_reason`/`_configured_reason`/`_used_reason`) that describes
*why*, without re-deriving the truth.

First implementation called `determine_observation()` (which internally re-probes every mechanism
via its own `any(...)` call) AND separately re-probed each mechanism again for its reason line —
silently running every connectivity check (e.g. `gh auth status`) twice per `doctor` invocation.
Caught before shipping by re-reading the draft adversarially (not by a test failing — no test yet
existed for it), fixed by probing each mechanism exactly once and reusing that result for both the
aggregate YES/NO and the per-mechanism reason
(`avail_by_mech = [(m, _mechanism_available(m)) for m in entry.mechanisms]`, etc.).
`tests/test_groundwork_integrations.py::test_doctor_command` now asserts the call count directly
(a stub `gh` binary that appends to a call-count file), so this can't silently regress back to a
double-probe.

WHY: narration-over-the-same-result, not a second check, satisfies "reuse the existing
implementation, do not duplicate its business logic" for the *decision* logic (what counts as
available/configured/connected/used lives in exactly one place, unchanged) while still adding real
diagnostic value (a reason, not just a restated boolean) — the smallest design that satisfies the
`doctor <name>` requirement.

TRADEOFFS: the `connected` reason does not distinguish *how* a check failed (non-zero exit vs.
missing success marker vs. timeout) — it only says whether a real check exists and, if so, whether
it currently confirms success. Finer-grained reasons would need `_mechanism_connected` itself to
return more than a boolean, which would again ripple into the ~8 existing tests; deferred as
unjustified complexity for a v1 diagnostic (no task exposed a need for that granularity).

VALIDATION METHOD: `test_doctor_command` asserts (a) `doctor`'s `Available`/`Configured`/
`Connected`/`Summary state` lines are byte-identical to `show`'s for the same integration — the
narration can never disagree with the observation it explains; (b) the exactly-once call-count
check described above; (c) the unknown-integration error path, matching `show`'s existing pattern.

UNCERTAINTY: none material.

## DECISION 3 — No new MCP visibility tiers ("runtime tool", "authenticated capability") built in
this change

EVIDENCE: The amendment's own instruction: "If improving MCP visibility, use only supported
discovery and clearly distinguish: static catalog / runtime server / runtime tool / authenticated
capability. Do not fabricate MCP/tool/authenticated-capability state." Read
`scripts/groundwork_integrations.py`'s existing `_mechanism_available()` directly: for an MCP
mechanism it already checks only `mech.mcp_server_name.lower() in _mcp_list_output().lower()` —
i.e. "listed by `claude mcp list`" (a **runtime server** presence check), and its own docstring
already states this is "presence only, never a claim of working connectivity." No existing,
supported discovery mechanism for "runtime tool" (a specific tool schema actually loaded) or
"authenticated capability" (an MCP server actually authenticated) was found in this codebase or in
Claude Code's documented CLI surface during this investigation.

WHY: building a new, unproven discovery mechanism for tiers with no supported API to observe them
would violate the amendment's own explicit constraints ("use only supported discovery," "do not
fabricate... state") and Groundwork's validation-driven-evolution rule
(`docs/FUTURE-SCOPE.md` §12: a mechanism is added only when a real task exposed the gap AND native
capabilities can't already solve it AND the benefit justifies the complexity). No task in this
Phase 2 scope exposed a concrete gap that "runtime server" presence-only reporting fails to serve;
the existing four-tier distinction the instruction asks for is already honestly represented by
exactly one populated tier (*static catalog* = the `CATALOG` tuple itself; *runtime server* =
`available` for MCP mechanisms) with the other two tiers correctly left unclaimed rather than
guessed.

TRADEOFFS: a user cannot currently distinguish "server listed" from "server's tools actually
loaded and authenticated" through this Catalog — acceptable, since claiming that distinction
without a real probe would be worse (fabricated state), and the existing `connected` axis already
gives a real, honestly-scoped authentication signal for the one mechanism (GitHub `gh` CLI) that
has one.

VALIDATION METHOD: code-read confirmation that no MCP-tier fabrication was introduced;
`tests/test_groundwork_integrations.py`'s existing `test_presence_alone_never_yields_connected`
(unchanged, still passing) continues to prove presence is never conflated with connectivity.

UNCERTAINTY: FUTURE — if Claude Code's CLI ever exposes a supported way to enumerate loaded tool
schemas or per-server authentication state, this decision should be revisited; no such API was
found to exist today.
