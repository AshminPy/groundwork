# Spec Delta

## Purpose

Makes MCP servers easy to see and control while keeping them least-privilege: only servers the owner approved, enabled only where needed, with credentials kept out of files.

## ADDED Requirements

### Requirement: No MCP servers are enabled by default
Installing or enabling Groundwork SHALL NOT add or enable any MCP server.

#### Scenario: Fresh install
- **WHEN** Groundwork is enabled in a new project
- **THEN** the session's MCP server list is the same as before

### Requirement: Only catalogued servers can be enabled
Groundwork SHALL enable an MCP server only if it is in the approved catalog for the active profile. Each entry SHALL state the server's name, scope, how it authenticates, whether it can write, and which agents may use it.

#### Scenario: Unlisted server
- **WHEN** the owner asks Groundwork to enable a server that isn't in the catalog
- **THEN** it is not enabled, and the owner is told to approve it and add a catalog entry first

### Requirement: Server status is visible in one place
`/groundwork:mcp` SHALL list each catalogued server with its state (enabled or disabled, connected or failing) and its tool count. It SHALL enable or disable a server for the current project.

#### Scenario: Failing server
- **WHEN** an enabled server can't connect
- **THEN** the list shows it as failing, with the error message

### Requirement: Credentials never go into files
MCP credentials SHALL come only from secure plugin configuration or the environment. No credential SHALL be written to the catalog, the run folder, telemetry or an export.

#### Scenario: Token entry
- **WHEN** the owner enters a server token
- **THEN** it is kept in secure storage, and no Groundwork file contains it

### Requirement: Agents use only their allowed servers
The guard SHALL deny an agent's call to the tools of any MCP server whose catalog entry doesn't allow that agent.

#### Scenario: Docs agent and a cloud server
- **WHEN** the docs agent calls a tool from a cloud-provider server not allowed for docs
- **THEN** the call is denied
