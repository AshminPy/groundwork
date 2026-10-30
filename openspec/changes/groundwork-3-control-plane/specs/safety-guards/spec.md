# Spec Delta

## Purpose

Keeps Groundwork safe in auto mode without approval prompts. Guard hooks only allow, deny or add context, and the owner approves only T4 work and one-time setup actions.

## ADDED Requirements

### Requirement: Guard hooks never prompt
No Groundwork hook SHALL return an ask decision or otherwise cause a permission prompt. Each hook SHALL allow, deny with a reason, block with a reason, or add context.

#### Scenario: Routine edit in auto mode
- **WHEN** a builder edits a file it owns in auto mode
- **THEN** no permission prompt is shown

### Requirement: Guards cover every tool that can reach protected data
The pre-tool guard SHALL inspect Bash, Edit, Write, NotebookEdit, Read, Grep, Glob and MCP tool calls. The settings profile SHALL also deny reads of secret paths and set the sandbox to deny reading them.

#### Scenario: Secret read through Grep
- **WHEN** an agent greps a credentials file
- **THEN** the call is denied

### Requirement: Hard denies cover destructive actions
The guard SHALL deny `terraform apply` and `terraform destroy` (including through `-auto-approve`), deleting Kubernetes resources in a production context, force-pushing, and writes to protected paths. Each deny reason SHALL say what to do instead.

#### Scenario: Builder runs terraform apply
- **WHEN** builder-terraform runs `terraform apply`
- **THEN** the command is denied, and the reason says applies go through Spacelift or the T4 path

### Requirement: Production context raises the tier at action time
The guard SHALL detect a production context from the active kube context, the terraform workspace, or a path matching the project's production globs. A mutating action in that context on a run below T4 SHALL be denied with "tier up to T4", and the run's tier SHALL be raised.

#### Scenario: Prod kube context on a T2 run
- **WHEN** a T2 builder runs `kubectl apply` while the current context matches a production pattern
- **THEN** the command is denied, and the run is raised to T4

### Requirement: Per-agent write scope is checked twice
Before a tool runs, the guard SHALL deny edits and writes outside the calling agent's owned paths, and every write by an agent with no binding. When the agent stops, the working tree SHALL be compared with a snapshot taken at its start. Any change outside its owned paths SHALL block the task, because a script can write files that the guard can't see.

#### Scenario: Reviewer edits code
- **WHEN** final-reviewer tries to edit `main.tf`
- **THEN** the edit is denied, and only writes to `review.json` are allowed

#### Scenario: Write through a script
- **WHEN** a builder's Bash command writes a file outside its owned paths
- **THEN** the stop check finds it, blocks the task, and lists the file

#### Scenario: File already dirty
- **WHEN** a file outside the builder's paths was already modified before the builder started
- **THEN** the stop check doesn't blame the builder for it

### Requirement: Done needs a passing scope check
`gw task done` SHALL refuse unless a passing scope-check record exists for the task's current revision, so a stop hook that crashed can't skip the check.

#### Scenario: Stop hook crashed
- **WHEN** agent-stop failed and wrote no scope-check record
- **THEN** `gw task done` fails with "scope check missing"

### Requirement: Guard failures block the action
The pre-tool guard and the dispatch gate SHALL be configured so that a crash, a timeout, invalid output, or a script that cannot start blocks the action. Recording hooks SHALL let the action continue and log their failure.

#### Scenario: Guard script missing
- **WHEN** the pre-tool guard script cannot start
- **THEN** the tool call is blocked

### Requirement: T4 work needs owner approval
On T4 runs, nothing SHALL change outside the run's OpenSpec change folder and its test paths until the owner has approved a plan that includes rollback steps. Builders SHALL produce a dry run or plan output, saved as evidence, before any change.

#### Scenario: Change without dry run
- **WHEN** a T4 builder tries to change a resource with no dry-run evidence for the task
- **THEN** the change is denied

### Requirement: One-time setup actions need explicit approval
Applying the settings profile, adding an MCP catalog entry, approving a third-party tool, and starting a paid eval run SHALL each need the owner's explicit approval. These approvals SHALL happen outside the task workflow.

#### Scenario: Profile apply
- **WHEN** `gw profile apply` runs
- **THEN** it shows the diff and writes nothing until the owner approves

### Requirement: The settings profile is reversible
`gw profile apply` SHALL save a backup before writing, and `gw profile revert` SHALL restore it exactly. Work and personal profiles SHALL be separate.

#### Scenario: Revert restores settings
- **WHEN** the owner runs `gw profile revert` after an apply
- **THEN** the settings file matches the backup byte for byte

### Requirement: Nothing installs at session start
No hook SHALL install packages, change shell startup files, or write outside the plugin data folder, the project's `.groundwork/`, and the approved profile target.

#### Scenario: Missing tool
- **WHEN** a session starts and the OpenSpec CLI is missing
- **THEN** the session-start hook reports it and installs nothing

### Requirement: Auto-mode denials are recorded separately
Actions denied by auto mode SHALL be recorded apart from guard denials and tool failures. The report SHALL count each kind on its own.

#### Scenario: Denials in the report
- **WHEN** auto mode denies two actions and the guard denies one during a run
- **THEN** the report shows 2 auto-mode denials and 1 guard denial
