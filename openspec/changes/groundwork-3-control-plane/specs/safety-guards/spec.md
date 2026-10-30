# Spec Delta

## Purpose

Keeps Groundwork safe in auto mode without approval prompts. Guard hooks only allow, deny or add context, and the owner approves only T4 work.

## ADDED Requirements

### Requirement: Guard hooks never prompt
No Groundwork hook SHALL return an ask decision or otherwise cause a permission prompt. Each guard SHALL allow, deny with a reason, or add context.

#### Scenario: Routine edit in auto mode
- **WHEN** a builder edits a file it owns in auto mode
- **THEN** no permission prompt is shown

### Requirement: Hard denies cover protected actions
The pre-tool guard SHALL deny writes to protected paths and secret files, reads of secret files, and destructive commands. Destructive commands include `terraform apply`, `terraform destroy`, deleting Kubernetes resources in production contexts, and force-pushing. The deny reason SHALL say what to do instead.

#### Scenario: Builder runs terraform apply
- **WHEN** builder-terraform runs `terraform apply`
- **THEN** the command is denied, and the reason says applies go through Spacelift or the T4 path

### Requirement: Each agent writes only its own paths
The guard SHALL identify the calling agent from the hook input and deny a write outside the paths that agent owns for its current task. Read-only agents SHALL be denied every write except their own output file.

#### Scenario: Reviewer edits code
- **WHEN** final-reviewer tries to edit `main.tf`
- **THEN** the edit is denied, and only writes to `review.md` are allowed

#### Scenario: Builder writes another task's file
- **WHEN** builder-kubernetes, which owns `charts/app/**`, writes `modules/eks/main.tf`
- **THEN** the write is denied

### Requirement: Guards fail closed, records fail open
If a guard hook cannot run or crashes, the guarded action SHALL be denied. If a recording hook fails, the action SHALL continue and the failure SHALL be logged.

#### Scenario: Guard script error
- **WHEN** the pre-tool guard raises an exception
- **THEN** the tool call is denied with a "guard unavailable" reason

### Requirement: T4 work needs owner approval
On T4 runs, nothing SHALL change outside read-only investigation until the owner has approved the plan, including its rollback steps. Builders SHALL produce a dry run or plan output before any change.

#### Scenario: Owner rejects
- **WHEN** the owner rejects a T4 plan
- **THEN** the run stops, no builder starts, and the rejection is recorded

### Requirement: The settings profile is applied only with approval
Settings a plugin cannot ship SHALL be applied by `gw profile apply`. It SHALL show the exact diff, save a backup, write only after the owner approves, and be reversible with `gw profile revert`. Work and personal profiles SHALL be separate.

#### Scenario: Revert restores settings
- **WHEN** the owner runs `gw profile revert` after an apply
- **THEN** the settings file matches the saved backup byte for byte

### Requirement: Nothing installs at session start
No hook SHALL install packages, change shell startup files, or write outside the plugin data folder, the project's `.groundwork/`, and the approved profile target.

#### Scenario: Missing tool
- **WHEN** a session starts and the OpenSpec CLI is missing
- **THEN** the session-start hook reports it and installs nothing

### Requirement: Auto-mode denials are recorded separately
Actions denied by auto mode SHALL be recorded apart from tool failures, so reports can count them on their own.

#### Scenario: Denial in report
- **WHEN** auto mode denies two actions during a run
- **THEN** the run report shows 2 denials, separate from failed commands
