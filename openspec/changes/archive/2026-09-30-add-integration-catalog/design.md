# Design

## Context

See `proposal.md` - Why. Relevant existing code, verified by direct inspection of `main` this session (not assumed):

- `docs/INTEGRATIONS.md` is a static, hand-authored research table (6 columns: Domain, Preferred access, Trust level, Read/Write, Auth model, Context strategy) — no live state, no CLI, no per-capability breakdown.
- `scripts/groundwork_config.py` and `scripts/groundwork_routines.py` are the existing CLI conventions to match: stdlib-only, `argparse`, a `main()` dispatch, installed by `install.sh` into `~/.claude/groundwork/bin/`.
- `scripts/groundwork_routines.py`'s `check_access()` (routines-specific) already does the kind of probing this change needs — `shutil.which()` presence checks, `subprocess.run([...], timeout=...)` for `gh auth status`/`claude mcp list` — but it is routine-config-shaped, not a general integration probe, and it lives in a file that is itself routine-specific.
- `hooks/` and `scripts/` install to **different directories** (`~/.claude/hooks/` vs `~/.claude/groundwork/bin/`) — any shared-helper file living in one is not importable from the other post-install. This rules out extracting a shared probe module between `groundwork_shared.py` (hooks-only today) and a new script.
- `setup.sh`'s `verify_capabilities()` already shells out to `groundwork_routines.py doctor` and indents its output for the Routines section of `--doctor` — the pattern this change's doctor section reuses.
- Prior investigation this session (research reports, accepted by the user) established: Claude Code's native Tool Search already does lazy/deferred MCP tool-schema loading; there is no documented, safe mechanism for a plugin to force per-task MCP server activation; `anaisbetts/mcp-installer` is rejected (Desktop-only, no uninstall, plaintext secrets, unsandboxed execution).

## Goals / Non-Goals

**Goals:**
- One structured, code-defined source of truth for integration capability/mechanism/state.
- A truthful state model that cannot overclaim `CONNECTED`.
- A CLI consistent with existing Groundwork scripts, plus a `--doctor` section.
- Keep `docs/INTEGRATIONS.md` from silently drifting from the code, without a runtime parser.

**Non-Goals:**
- No MCP/package installer, marketplace, or package manager of any kind.
- No custom dynamic MCP tool-loading/activation engine — Claude Code's Tool Search is relied on as-is.
- No enforcement of per-task MCP activation (no documented Claude Code hook exists for this).
- No statusLine/terminal UX (future change; this change only needs to leave state in a form that change can read later — no new work here beyond what the CLI already produces).
- No new observation beyond the three independent readiness booleans (`available`/`configured`/`connected`) and the separate `used` observation (`true`/`false`/`unknown`) — a `NOT CONFIGURED` label is a display-only summary condition ("none of the three readiness booleans is true"), never a fourth persisted readiness observation, and `used` is never folded into the readiness summary.
- No credential storage, reading, or display.

## Decisions

**1. Catalog lives as a Python module-level data structure inside `scripts/groundwork_integrations.py`, not a separate JSON/YAML file.**
Alternatives considered: (a) a separate `integrations_catalog.json` data file — rejected as an unnecessary extra file for ~9-14 small entries, and it would need its own schema validation the Python structure gets for free from `dataclasses`/type checks; (b) parsing `docs/INTEGRATIONS.md` at runtime — explicitly rejected by the user ("do not create brittle production logic that parses a Markdown table"). A single `tuple[IntegrationEntry, ...]` of a small `dataclass` is the smallest structure that is both the catalog's source of truth and trivially unit-testable.

**2. `docs/INTEGRATIONS.md` stays hand-authored prose; a test cross-checks its domain names against the catalog's integration names.**
Full doc generation from the catalog was considered and rejected as over-engineering for a ~9-14-row table whose real value (trust-level reasoning, context-strategy notes) is prose the catalog doesn't need to carry. Instead, `tests/test_groundwork_integrations.py` asserts every catalog integration name has a corresponding row in `docs/INTEGRATIONS.md`, so the two cannot silently diverge — satisfies "deterministically checked against" without a parser in production code (the test itself may do a light, test-only text scan of the doc; this never ships as runtime logic).

**3. Probes are written fresh in `groundwork_integrations.py`, not shared with `groundwork_routines.py`.**
Per Context above, `hooks/` vs `scripts/` install-path separation already rules out one axis of sharing; `groundwork_routines.py` and `groundwork_integrations.py` are both under `scripts/` so a shared import is technically possible, but `check_access()` is tightly coupled to routine-config field names (`access`, `mcp_server`, etc.) — generalizing it now would touch tested, shipped Routines code for a small win. The new file implements its own small `_probe_cli_version`, `_probe_cli_auth`, `_probe_mcp_listed` helpers, deliberately matching `check_access()`'s pattern (subprocess + timeout + safe-fail) rather than its code, and this is noted in a comment pointing at the precedent.

**4. `available`, `configured`, `connected` are independent booleans, each computed separately; a single display summary is derived, never stored.**
An earlier draft of this change modeled these as one linear lifecycle (`NOT CONFIGURED` -> `AVAILABLE` -> `CONFIGURED` -> `CONNECTED`, each requiring the previous) — rejected after independent review: it cannot represent a real, truthful case like configuration recorded for a mechanism that isn't currently installed (`configured=true`, `available=false`), which the linear model would have forced into a lie. Final rule: `available` is computed from presence alone (CLI binary on PATH, or MCP server listed); `configured` is computed from whether Groundwork's own stored configuration (the active capability profile's `cloud`/`platform`/`integrations` lists in `config.json`) references that integration's key — a simple, uniform check applicable identically to every catalog entry; `connected` is computed only where a real check is implemented for that mechanism (today: `gh auth status` for the GitHub CLI mechanism — the same one already trusted in `groundwork_routines.py`), and is `false` whenever no such check exists, exactly as it is on a check that ran and failed. A single display summary label (`CONNECTED` > `CONFIGURED` > `AVAILABLE` > `NOT CONFIGURED`, highest true wins) is computed on demand for `list`/`show`'s summary line — it is never itself stored or treated as the source of truth; `show`'s detail view always exposes the three raw booleans alongside it.

**5. `USED` is derived from existing telemetry, read at query time, not written by this change.**
`groundwork_telemetry.py` already extracts tool/MCP names from the transcript for its own JSONL record on Stop. This change's `show` command, when telemetry is available, reads the most recent record(s) for a `used` signal; it does not add a new hook or its own tracking file. If no reliable signal exists, `show` reports `USED: unknown` rather than guessing.

## Risks / Trade-offs

- **[Risk] Probe subprocess calls could hang on a broken PATH tool** -> Mitigation: every probe carries an explicit timeout (matching `check_access()`'s existing timeout precedent) and treats a timeout as a failed check, never `CONNECTED`.
- **[Risk] `docs/INTEGRATIONS.md` drift if someone edits the doc without touching the catalog, or vice versa** -> Mitigation: the doc-consistency test (Decision 2) fails CI/`pytest` on drift; it does not silently pass.
- **[Risk] A future contributor mistakes the catalog for an enforcement mechanism and builds MCP-activation logic on top of it** -> Mitigation: the spec's "Guidance, not enforcement" requirement, plus an explicit architecture note in `docs/ARCHITECTURE.md`, state this in writing.
- **[Trade-off] `show`'s Routines-dependency field will be empty/absent for integrations no Routine currently uses (e.g. Kubernetes, Terraform)** -> Accepted: the spec explicitly forbids inferring this for playbooks, so an honest "no Routine currently depends on this" is correct, not a gap.
- **[Correction, pre-implementation]** The first draft of this proposal described `available`/`configured`/`connected`/`used` together as one "4-state model." Owner review on PR #23 caught that this conflates an independent-dimensions readiness model with task/session telemetry, and that a linear lifecycle would force false claims (see Decision 4). Corrected before any code was written; noted here for the audit trail rather than silently rewritten.

## Migration Plan

Purely additive: new script, new test file, small edits to `install.sh`/`setup.sh`/three docs. No existing config schema, hook, or CLI command changes. Rollback is deleting the new file and reverting the small edits — no data migration, no state to roll back.
