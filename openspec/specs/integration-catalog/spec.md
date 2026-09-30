# integration-catalog Specification

## Purpose
Gives users and Claude sessions one truthful, queryable source for which external-system integrations Groundwork knows about, what capability each satisfies, which access mechanism is approved for it, and its actual, evidence-backed readiness state — never a marketing claim.

## Requirements

### Requirement: Integration catalog definition
The system SHALL maintain a structured, code-defined catalog of known integrations. Each catalog entry SHALL declare: an integration name, one or more capability ids (dotted form, e.g. `kubernetes.logs.read`), one or more approved access mechanisms each typed `mcp`, `cli`, or `api`, a trust/access characteristics description, and its configuration requirements. The catalog SHALL NOT be derived by parsing `docs/INTEGRATIONS.md` at runtime.

#### Scenario: Catalog entry has all required fields
- **WHEN** any catalog entry is loaded
- **THEN** it has a non-empty name, at least one capability id, at least one typed access mechanism, and a trust/access description

### Requirement: Independent readiness observations
For each integration, the system SHALL determine and report three independent boolean readiness observations, none of which imply or require each other except where stated: `available` (an approved access mechanism is present, e.g. a CLI binary on PATH or a server listed by the MCP client), `configured` (non-secret Groundwork configuration referencing that integration exists), and `connected` (a real reachability or authentication check for that specific mechanism actually ran and succeeded). These are readiness observations, not a single lifecycle stage — `configured` MAY be true while `available` is false (e.g. configuration recorded for a mechanism not currently installed), and any combination of the three booleans is valid and MUST be preserved rather than collapsed. The system SHALL NOT set `connected` true unless a real check actually ran and succeeded for that mechanism; mere presence, listing, or configuration SHALL NOT be sufficient. A failed, errored, or timed-out check SHALL NOT set `connected` true.

#### Scenario: Presence alone does not imply connected
- **WHEN** an integration's mechanism is present (binary on PATH, or listed by the MCP client) but no reachability/auth check has been run for it
- **THEN** the system reports `available: true` and `connected: false`

#### Scenario: Configured without available
- **WHEN** non-secret configuration exists for an integration whose mechanism is not currently present
- **THEN** the system reports `configured: true` and `available: false` simultaneously, without forcing either to match the other

#### Scenario: Successful real check yields connected
- **WHEN** a defined reachability/authentication check for an integration's mechanism is run and it succeeds
- **THEN** the system reports `connected: true` for that integration

#### Scenario: Failed check never yields connected
- **WHEN** a defined reachability/authentication check for an integration's mechanism is run and it fails, errors, or times out
- **THEN** the system reports `connected: false`, regardless of the `available`/`configured` values

### Requirement: Task/session usage observation
For each integration, the system SHALL determine and report a `used` observation, separate from the three readiness observations above, with three possible values: `true` (existing telemetry provides reliable evidence this integration was invoked for the relevant task/session), `false` (reliable telemetry evidence shows it was not invoked), or `unknown` (no reliable evidence exists either way). The system SHALL NOT build new tracking to support this; it SHALL read existing telemetry only, and SHALL report `unknown` rather than guess when telemetry is absent or inconclusive.

#### Scenario: Used is unknown without reliable telemetry
- **WHEN** no telemetry record exists, or an existing record does not reliably indicate this integration's use
- **THEN** the system reports `used: unknown`, never a guessed `true` or `false`

### Requirement: Display summary state
For display purposes only (the `list` command and the summary line of `show`), the system SHALL derive one concise summary label from the three readiness observations, computed (never stored or persisted) in this priority order: `CONNECTED` if `connected` is true; else `CONFIGURED` if `configured` is true; else `AVAILABLE` if `available` is true; else `NOT CONFIGURED`. `NOT CONFIGURED` SHALL be treated purely as the display condition for "none of the three readiness observations are true" and SHALL NOT be modeled or persisted as if it were itself a positive observation equivalent to `available`/`configured`/`connected`. The `used` observation is never folded into this summary label.

#### Scenario: Summary label reflects the highest true readiness observation
- **WHEN** an integration's readiness observations are computed
- **THEN** its displayed summary label is `CONNECTED` if `connected` is true, else `CONFIGURED` if `configured` is true, else `AVAILABLE` if `available` is true, else `NOT CONFIGURED`

### Requirement: List command
The system SHALL provide a command that lists every catalog integration with its approved access mechanism(s) and current display summary state (per the Display summary state requirement) in a single concise table.

#### Scenario: List shows every catalog integration
- **WHEN** the list command is run
- **THEN** every integration defined in the catalog appears exactly once, with its access mechanism(s) and display summary state

### Requirement: Detail command
The system SHALL provide a command that, given an integration name, reports its purpose, capabilities, approved access mechanisms, trust/access characteristics, configuration requirements, its three raw readiness observations (`available`, `configured`, `connected`, shown individually, not collapsed into the summary label), its `used` observation, and which configured Routines explicitly depend on it. The Routines-dependency information SHALL be derived deterministically from Routines' own stored configuration and SHALL NOT be inferred or guessed for playbooks or other consumers.

#### Scenario: Detail view for a known integration
- **WHEN** the detail command is run for an integration name present in the catalog
- **THEN** the output includes its purpose, capabilities, approved mechanisms, trust/access characteristics, configuration requirements, its three individual readiness observations, and its `used` observation

#### Scenario: Detail view for an unknown integration
- **WHEN** the detail command is run for a name not present in the catalog
- **THEN** the system reports that the integration is not known, without crashing or fabricating information

#### Scenario: Routines dependency is deterministic only
- **WHEN** the detail command reports which Routines depend on an integration
- **THEN** it lists only Routines whose own stored configuration explicitly declares that integration's access mechanism, and never a playbook or other consumer inferred without such a deterministic link

### Requirement: Doctor integration
`setup.sh --doctor` SHALL include a section showing the integration catalog's list output, in the same read-only manner as its existing Routines section.

#### Scenario: Doctor shows integration states
- **WHEN** `setup.sh --doctor` is run
- **THEN** its output includes each catalog integration's access mechanism(s) and current display summary state

### Requirement: No secret exposure
No catalog, probe, list, show, or doctor output SHALL ever include a credential, token, password, API key, or other secret value.

#### Scenario: Output is scanned for secret-shaped values
- **WHEN** any command's output is inspected
- **THEN** it contains no value matching a credential/token/password/API-key/secret shape

### Requirement: Non-mutating, bounded operation
All catalog probes SHALL be read-only, SHALL NOT install, configure, or modify any package, server, or credential, and SHALL be bounded by a timeout so a hanging check cannot hang the command. On any probe error, the system SHALL fail safe (report the integration's state as no stronger than what was already established, without crashing the command).

#### Scenario: Malformed or missing configuration fails safe
- **WHEN** an integration's configuration is missing or malformed
- **THEN** the system reports the affected integration's state without crashing and without executing any installation or mutating action

### Requirement: Guidance, not enforcement, of access mechanism activation
Where the system recommends an approved access mechanism for a capability, it SHALL present this as guidance only. It SHALL NOT claim to enforce, activate, or deactivate any specific MCP server or tool for a given task at runtime.

#### Scenario: Output never claims enforced activation
- **WHEN** the system reports a recommended access mechanism for a capability
- **THEN** its wording states this as a recommendation and does not claim that Groundwork itself activates or deactivates that mechanism at runtime
