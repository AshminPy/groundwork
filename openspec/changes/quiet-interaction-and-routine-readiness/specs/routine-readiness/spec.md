# routine-readiness Specification

## Purpose
Gives Groundwork's scheduled Routines a truthful, pre-scheduling readiness verdict, derived from data Groundwork already collects, so a routine is never represented as ready for unattended execution when it will actually be BLOCKED — without introducing a second permission/readiness framework or weakening least-privilege tool grants.

## ADDED Requirements

### Requirement: A scheduled routine cannot depend on interactive approval
Every routine invocation built by `groundwork_routines.py` SHALL include `--permission-mode dontAsk` and `--permission-prompts none`, and SHALL NOT include `--dangerously-skip-permissions`, `--allow-dangerously-skip-permissions`, or any equivalent blanket bypass. This SHALL hold for every routine in `ROUTINES`, not only the one manually exercised during development.

#### Scenario: Every routine's built command fails closed, never hangs
- **WHEN** `build_command()` is called for any routine currently defined in `ROUTINES`
- **THEN** the returned command includes `--permission-mode dontAsk` and `--permission-prompts none`, and never includes a blanket permission-bypass flag

### Requirement: Readiness is synthesized from existing configuration/connectivity data, not a new framework
Groundwork SHALL classify each enabled routine's unattended readiness as `READY`, `READY (connectivity not verifiable)`, or `BLOCKED`, derived entirely from data already computed by `_doctor_rows()`/`check_access()`/`_capabilities_for()` (enabled, access mechanism, available, connected, mutates, and whether `_capabilities_for()` — the exact function `build_command()` itself calls — reports the routine as unable to run with its current configuration). A disabled routine SHALL be classified `NOT ENABLED`. This classification SHALL NOT introduce a new probe, a new external call, or a readiness model parallel to the Integration Catalog's available/configured/connected distinctions. Readiness SHALL agree with `build_command()`: a routine SHALL NOT be classified `READY` if `build_command()` would refuse to spawn `claude` for it under the same configuration — including a routine whose own configuration has no directly-configured access mechanism but depends on another routine's configured access (e.g. `weekly_status`/`work_digest` borrowing `pr_followup`'s configured GitHub access).

#### Scenario: A routine with no access mechanism of its own but an unconfigured borrowed dependency is BLOCKED
- **WHEN** a routine (e.g. `weekly_status`, `work_digest`) is configured to use another routine's access mechanism (e.g. GitHub via `pr_followup`) and that dependency is unconfigured
- **THEN** its readiness is `BLOCKED` with a reason naming the missing configuration, matching what `build_command()` would actually do — never an unqualified `READY`

#### Scenario: A routine needing no external access is READY once enabled
- **WHEN** a routine requires no configured access mechanism (e.g. `news`, `doc_drift`) and is enabled
- **THEN** its readiness is `READY`

#### Scenario: A routine with an unconfigured required access mechanism is BLOCKED
- **WHEN** a routine requires an access mechanism and none is configured
- **THEN** its readiness is `BLOCKED` with a reason naming the missing configuration and how to fix it

#### Scenario: A routine with a configured but unauthenticated access mechanism is BLOCKED
- **WHEN** a routine's configured access mechanism has a real connectivity check (today: `gh_cli` via `gh auth status`) and that check fails
- **THEN** its readiness is `BLOCKED` with the actual connectivity detail as the reason

#### Scenario: A routine with no real connectivity check available is honestly labeled, not falsely READY
- **WHEN** a routine's configured access mechanism has no real connectivity check today (`jira_mcp`, `cli`, `browser`)
- **THEN** its readiness is `READY (connectivity not verifiable)`, never an unqualified `READY`

### Requirement: Readiness is visible before scheduling, using existing output surfaces
The routine readiness verdict SHALL be visible via `setup.sh --routines`, reusing the existing per-routine doctor rendering rather than a new wizard, dashboard, or UI.

#### Scenario: Readiness appears in existing routine status output
- **WHEN** a user runs `setup.sh --routines`
- **THEN** each enabled routine's output includes its READY/BLOCKED verdict and, if BLOCKED, an actionable reason

### Requirement: Mutating routines and their unverifiable-connectivity limitation are stated truthfully
A routine's `mutates` flag SHALL remain visible in its readiness output. `jira_eod`'s known limitation — no Jira access mechanism has a real connectivity check, and its granted tool set is a server-level wildcard rather than a narrowly-scoped write permission — SHALL be documented, not silently resolved with a fabricated narrower grant Claude Code cannot actually express for an arbitrary user-configured MCP server.

#### Scenario: A mutating routine's readiness output distinguishes it from a read-only one
- **WHEN** `jira_eod` (the only `mutates: true` routine) is enabled
- **THEN** its readiness output marks it as mutating and, if `posting` is `automatic`, notes that no live connectivity check exists for its configured Jira access mechanism
