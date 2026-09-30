# groundwork-integrations-cli Specification

## Purpose
Exposes the existing Integration Catalog (`scripts/groundwork_integrations.py`) through the
stable `groundwork` CLI as a discoverable `groundwork integrations` subcommand — `list`/`show`/
`refresh`/`doctor` — without reimplementing its truth model or logic. `doctor` additionally
narrates why each observation (`available`/`configured`/`connected`/`used`) is what it is, from
the same probes `show` already uses.

## Requirements

### Requirement: `groundwork integrations` dispatches to the installed Integration Catalog script
The `groundwork` CLI SHALL provide an `integrations` subcommand that forwards every argument after
`integrations` verbatim to the installed `groundwork_integrations.py`, producing output and an
exit code byte-identical to invoking that script directly with the same arguments.

#### Scenario: `list` produces identical output to direct invocation
- **GIVEN** Groundwork is installed
- **WHEN** the user runs `groundwork integrations list`
- **THEN** stdout and the exit code are byte-identical to running the installed
  `groundwork_integrations.py list` directly

#### Scenario: `show NAME` produces identical output to direct invocation
- **GIVEN** Groundwork is installed
- **WHEN** the user runs `groundwork integrations show github`
- **THEN** stdout and the exit code are byte-identical to running the installed
  `groundwork_integrations.py show github` directly

#### Scenario: `--help` reaches the installed script's real help text
- **GIVEN** Groundwork is installed
- **WHEN** the user runs `groundwork integrations --help`
- **THEN** the output is the installed `groundwork_integrations.py`'s own help text, not a
  generic or truncated stub

#### Scenario: missing installed script fails cleanly
- **GIVEN** `groundwork_integrations.py` is not present at its expected installed path
- **WHEN** the user runs `groundwork integrations list`
- **THEN** the command prints a clear stderr message naming the missing path and exits non-zero,
  with no unhandled traceback

### Requirement: `groundwork_integrations.py doctor NAME` narrates existing observations without
changing them
`doctor NAME` SHALL print everything `show NAME` prints, plus a one-line reason for each of the
`available`/`configured`/`connected`/`used` observations, computed from the same probes `show`
already uses — never a second, independently-run check whose result could disagree with `show`'s.

#### Scenario: `doctor`'s observations match `show`'s exactly
- **GIVEN** any known integration
- **WHEN** `doctor NAME` and `show NAME` are run in the same environment
- **THEN** the `Available`, `Configured`, `Connected`, and `Summary state` lines are identical
  between the two outputs

#### Scenario: each mechanism's connectivity probe runs exactly once
- **GIVEN** an integration with a real connectivity check (e.g. GitHub's `gh auth status`)
- **WHEN** `doctor NAME` is run once
- **THEN** that connectivity check is executed exactly once, not once per internal computation

#### Scenario: unknown integration name fails cleanly
- **GIVEN** a name not in the catalog
- **WHEN** `doctor NAME` is run
- **THEN** it prints "not a known integration" and exits 1, with no traceback

### Requirement: the Integration Catalog's truth model is unchanged by this CLI surface
Adding `groundwork integrations` and `doctor` SHALL NOT alter the existing `available`/
`configured`/`connected`/`used` semantics, the summary priority
(`CONNECTED` > `CONFIGURED` > `AVAILABLE` > `NOT CONFIGURED`), or introduce any new MCP
presence/connectivity tier beyond what already exists.

#### Scenario: presence alone still never implies connectivity
- **GIVEN** an MCP server listed by `claude mcp list` with no real connectivity check implemented
- **WHEN** its observation is computed through any entry point (`list`, `show`, `doctor`, `refresh`)
- **THEN** `connected` is `false`
