# Spec Delta

## Purpose

Gives users and Claude sessions one truthful, queryable source for which external-system integrations Groundwork knows about, what capability each satisfies, which access mechanism is approved for it, and its actual, evidence-backed readiness state — never a marketing claim.

## ADDED Requirements

### Requirement: Integration catalog definition
The system SHALL maintain a structured, code-defined catalog of known integrations. Each catalog entry SHALL declare: an integration name, one or more capability ids (dotted form, e.g. `kubernetes.logs.read`), one or more approved access mechanisms each typed `mcp`, `cli`, or `api`, a trust/access characteristics description, and its configuration requirements. The catalog SHALL NOT be derived by parsing `docs/INTEGRATIONS.md` at runtime.

#### Scenario: Catalog entry has all required fields
- **WHEN** any catalog entry is loaded
- **THEN** it has a non-empty name, at least one capability id, at least one typed access mechanism, and a trust/access description

### Requirement: Truthful integration state
For each integration, the system SHALL determine and report exactly one of four states: `AVAILABLE` (an approved access mechanism is present, e.g. a CLI binary on PATH or a server listed by the MCP client), `CONFIGURED` (non-secret configuration for that integration exists), `CONNECTED` (a real reachability or authentication check for that specific mechanism ran and succeeded), or `NOT CONFIGURED` (none of the above hold). The system SHALL NOT report `CONNECTED` unless a real check actually ran and succeeded for that mechanism; mere presence or listing SHALL NOT be sufficient. A failed or errored check SHALL NOT be reported as `CONNECTED`.

#### Scenario: Presence alone does not imply connected
- **WHEN** an integration's mechanism is present (binary on PATH, or listed by the MCP client) but no reachability/auth check has been run for it
- **THEN** the system reports its state as `AVAILABLE`, never `CONNECTED`

#### Scenario: Successful real check yields connected
- **WHEN** a defined reachability/authentication check for an integration's mechanism is run and it succeeds
- **THEN** the system reports that integration's state as `CONNECTED`

#### Scenario: Failed check never yields connected
- **WHEN** a defined reachability/authentication check for an integration's mechanism is run and it fails, errors, or times out
- **THEN** the system reports a state no stronger than `AVAILABLE`, and never `CONNECTED`

### Requirement: List command
The system SHALL provide a command that lists every catalog integration with its approved access mechanism(s) and current state in a single concise table.

#### Scenario: List shows every catalog integration
- **WHEN** the list command is run
- **THEN** every integration defined in the catalog appears exactly once, with its access mechanism(s) and current state

### Requirement: Detail command
The system SHALL provide a command that, given an integration name, reports its purpose, capabilities, approved access mechanisms, trust/access characteristics, configuration requirements, current state, and which configured Routines explicitly depend on it. The Routines-dependency information SHALL be derived deterministically from Routines' own stored configuration and SHALL NOT be inferred or guessed for playbooks or other consumers.

#### Scenario: Detail view for a known integration
- **WHEN** the detail command is run for an integration name present in the catalog
- **THEN** the output includes its purpose, capabilities, approved mechanisms, trust/access characteristics, configuration requirements, and current state

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
- **THEN** its output includes each catalog integration's access mechanism(s) and current state

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
