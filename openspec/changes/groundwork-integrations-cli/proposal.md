# Proposal — Groundwork Integrations CLI (Next Release Program, Phase 2)

## Why

Phase 1 (`openspec/changes/groundwork-cli-foundation/`, merged) gave Groundwork a single,
discoverable `groundwork` entry point with `--help`/`version`/`doctor`. The Integration Catalog
(`scripts/groundwork_integrations.py`, Groundwork 2.1) already exists, is already installed by
`install.sh`, and already has its own tested CLI (`list`/`show`/`refresh`) — but it is only
reachable by knowing its exact installed path
(`python3 ~/.claude/groundwork/bin/groundwork_integrations.py`). That fragmentation is the same
"stable, discoverable entry point" problem Phase 1 solved for `version`/`doctor`, now recurring
for the Integration Catalog specifically.

## What Changes

- `groundwork integrations ...` — a new top-level subcommand on the existing `groundwork` CLI that
  forwards every argument verbatim to the installed `groundwork_integrations.py` (pure pass-through,
  zero business logic duplicated — see `design.md` DECISION 1).
- `scripts/groundwork_integrations.py` gains one new subcommand, `doctor NAME`: `show`'s detail plus
  a one-line reason for each of the four observations (`available`/`configured`/`connected`/`used`),
  computed from the exact same already-tested probes `show`/`list`/`refresh` use — never a second
  check, never new truth (see `design.md` DECISION 2).
- Tests: `tests/test_groundwork_cli.py` gains a dispatch-fidelity test (byte-identical output vs.
  direct invocation, across `list`/`show`/`refresh`/`doctor`/`--help`); `tests/test_groundwork_integrations.py`
  gains a `doctor`-specific test, including a mutation-style check that each mechanism's
  connectivity probe runs exactly once per `doctor` call (a real bug caught and fixed during this
  change's own implementation — see `design.md` DECISION 2's "double-probe" note).
- Docs: `README.md` and `docs/INTEGRATIONS.md` updated to document `groundwork integrations ...` as
  the preferred interface, with the direct script invocation kept as documented, unchanged, working
  backward-compatible alternative.

## Non-Goals (explicitly out of scope for this change)

- No change to the Integration Catalog's truth model: `available`/`configured`/`connected`/`used`
  stay exactly as Groundwork 2.1 defined them; the summary priority
  (`CONNECTED` > `CONFIGURED` > `AVAILABLE` > `NOT CONFIGURED`) is unchanged.
- No new connectivity probes: GitHub's `gh auth status` remains the only real `connected` check;
  no other integration gains one in this change (that stays "honestly false until a real check is
  implemented," per the Catalog's own existing design).
- No new MCP discovery tiers ("runtime tool", "authenticated capability") beyond the existing
  presence-only `claude mcp list` check — investigated and explicitly not built, see `design.md`
  DECISION 3.
- No MCP server installation, no credential storage, no third-party service configuration, no
  "Integration Manager" — the Catalog remains read-only, observation-only.
- `groundwork routines`, `groundwork update`, `groundwork rollback` — later phases.
- Rewriting `groundwork_integrations.py`'s existing `list`/`show`/`refresh` logic — unchanged, only
  additive (`doctor`).

## Acceptance Criteria (Phase 2 gate)

1. `groundwork integrations list`/`show NAME`/`refresh`/`doctor NAME` each produce output
   byte-identical to invoking the installed `groundwork_integrations.py` directly with the same
   arguments — proving dispatch, not reimplementation.
2. `groundwork integrations --help` reaches the installed script's own real help text (not a stub),
   despite the Python argparse `REMAINDER`/`-h` interaction that would otherwise intercept it.
3. `doctor NAME`'s `available`/`configured`/`connected`/`used`/summary-state lines are identical to
   `show NAME`'s — the reason lines never disagree with the observation they explain.
4. Each mechanism's connectivity probe (e.g. `gh auth status`) runs exactly once per `doctor`
   invocation, proven by a real call-count test, not assumed.
5. Full test suite green, `openspec validate groundwork-integrations-cli --strict` valid,
   independent fresh-context review with 0 MUST FIX remaining.
