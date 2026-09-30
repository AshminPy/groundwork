# Spec Delta

## Purpose

Gives Groundwork a truthful, fast, correctly session-isolated Claude Code `statusLine` that shows Groundwork-specific state — never a field the system cannot actually, currently stand behind.

## ADDED Requirements

### Requirement: Data-source contract
The system SHALL classify every displayable field as exactly one of LIVE (supplied directly by Claude Code's stdin JSON, or computed by a fast, bounded-timeout operation performed fresh on each render), LAST-COMPLETED-TURN (available only from the most recently completed turn's own telemetry record), CACHED (read from a file populated by a separate, earlier process — never computed fresh inside the statusLine), or UNAVAILABLE (no durable, authoritative source exists anywhere in Groundwork today). The system SHALL NOT display a field classified UNAVAILABLE, and SHALL NOT convert an UNAVAILABLE field into an inferred or guessed value.

#### Scenario: Unavailable fields are never displayed
- **WHEN** rendering the statusLine
- **THEN** no review/MUST-FIX state, role/persona label, or evidence-label (VERIFIED/UNVERIFIED/ASSUMPTION/etc.) count appears anywhere in the output, because none has a durable, authoritative source

#### Scenario: A last-completed-turn field is visually distinguished from a live field
- **WHEN** the statusLine displays a LAST-COMPLETED-TURN field (playbook, execution mode, or validation/tests-run state)
- **THEN** its rendering uses a documented, consistent visual convention that a live field does not use, so a reader cannot mistake it for the current, in-progress turn's state

### Requirement: Integration Catalog readiness is cache-only in the statusLine
The statusLine process SHALL NOT invoke `claude mcp list`, `gh auth status`, or any other Integration Catalog probe. It SHALL read Integration Catalog readiness only from a pre-computed cache file. Each cached integration's readiness SHALL carry its own `checked_at` timestamp. If no cache file exists, or a given integration has no entry in it, the statusLine SHALL display no readiness information for that integration (or an explicit unknown/not-yet-refreshed indicator) rather than omitting it silently in a way indistinguishable from "not configured." Every displayed integration readiness observation SHALL visibly communicate that it is a CACHED (not LIVE) observation, via a compact age indicator shown even while the entry is still fresh — not only once it crosses the staleness threshold — so CACHED readiness is never visually indistinguishable from a LIVE field. This indicator SHALL remain compact (no verbose per-entry labels such as "CACHED:").

#### Scenario: No cache file exists yet
- **WHEN** the Integration Catalog cache file does not exist (e.g. a fresh install that has never run install/configure/doctor)
- **THEN** the statusLine displays no integration readiness, or an explicit "not yet refreshed" indicator, and never infers a readiness state

#### Scenario: A fresh cache entry still shows it is cached
- **WHEN** a cached integration's `checked_at` is recent (younger than the staleness threshold)
- **THEN** the statusLine's rendering still shows a compact age indicator for that entry (e.g. an elapsed-time annotation), so it is never mistaken for a LIVE observation, while remaining visually distinct from a stale entry

#### Scenario: Cache exists but is stale
- **WHEN** a cached integration's `checked_at` is older than a documented staleness threshold
- **THEN** the statusLine's rendering makes that age visible (e.g. an elapsed-time annotation) AND carries an additional, distinct marker that a merely-fresh entry's rendering does not — so a stale entry never merely shows a bigger number — and never presents the cached value as current/live

#### Scenario: Cache refresh happens only at existing lifecycle points
- **WHEN** the Integration Catalog cache is refreshed
- **THEN** it happens only as a result of `install.sh` running, `setup.sh` writing/updating `config.json` (initial setup or `--configure`), or an explicit invocation of `groundwork_integrations.py refresh` (including as a side effect of `setup.sh --doctor`'s existing Integrations section) — never from a scheduled, cron, launchd, or otherwise continuously-running background process

### Requirement: Session isolation
The statusLine SHALL use the `session_id` supplied in Claude Code's own stdin JSON as the sole authoritative session identifier for any session-scoped Groundwork state. When reading the shared telemetry log for last-completed-turn fields, it SHALL consider only records whose `session_id` matches the current session's `session_id`. It SHALL NOT read the telemetry log's most recent record without this filter. The system SHALL NOT introduce a single global "current state" file that stores session-specific data readable by any session other than the one that wrote it. Machine-wide state (Integration Catalog readiness) is exempt from this per-session isolation requirement, as it does not represent task/session-scoped information.

#### Scenario: Two concurrent sessions do not see each other's last-turn state
- **WHEN** two Claude Code sessions with different `session_id` values are both active on the same machine, and one has more recent telemetry than the other
- **THEN** each session's statusLine shows only its own session's last-completed-turn fields (or UNAVAILABLE, if none of its own records are found within the bounded scan), never the other session's

#### Scenario: A session with no matching telemetry record degrades cleanly
- **WHEN** the current session's `session_id` has no matching record in the telemetry log (e.g. a brand-new session that has not yet completed a turn)
- **THEN** last-completed-turn fields are UNAVAILABLE for that render, with no error and no fallback to another session's data

#### Scenario: An interrupted or crashed session leaves no misleading state
- **WHEN** a session crashes or a turn is interrupted before its Stop hook runs
- **THEN** no telemetry record exists for that turn, and a later statusLine render for that session shows its previous completed turn's state (or UNAVAILABLE, if none exists) rather than any partial or corrupted record

### Requirement: Performance
The statusLine process SHALL NOT perform any of the following: `claude mcp list`, `gh auth status`, any other Integration Catalog probe, any network call, or any expensive/unbounded repository scan. Any local `git` operation it performs SHALL carry an explicit, short timeout, and its failure or timeout SHALL degrade that field to omitted/unavailable rather than blocking the render. Execution time SHALL be measured during validation, not merely asserted.

#### Scenario: Execution completes without invoking expensive operations
- **WHEN** the statusLine renders
- **THEN** no subprocess call to `claude`, `gh`, or any cloud/integration CLI occurs, and total execution time is measured and recorded as part of validation evidence

### Requirement: Configuration
The system SHALL support a small, standalone statusLine personalization file, separate from `config.json`, covering at minimum: compact vs. detailed rendering, per-section show/hide (integrations, context, cost, validation), and a plain-text-vs-Unicode-symbol rendering choice. It SHALL NOT be stored inside `config.json`. Malformed or missing personalization configuration SHALL fail safe to documented defaults, never a crash.

#### Scenario: Personalization survives a capability reconfiguration
- **WHEN** a user has customized statusline personalization and later runs `setup.sh --configure` (which rewrites `config.json` from a fixed template)
- **THEN** the statusline personalization is unaffected, because it is stored in a separate file `config.json`'s rewrite never touches

### Requirement: Installation and settings integration
The system SHALL install the statusLine script the same way other Groundwork scripts are installed, and SHALL register it as the `statusLine` command in `settings.json` only if that key is not already set by the user. It SHALL NOT overwrite an existing user-configured `statusLine`.

#### Scenario: An existing user statusLine is preserved
- **WHEN** `settings.json` already has a `statusLine` key configured to something other than Groundwork's own script
- **THEN** installing/updating Groundwork does not change that key
