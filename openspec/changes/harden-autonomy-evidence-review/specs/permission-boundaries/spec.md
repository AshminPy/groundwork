## ADDED Requirements

### Requirement: Three permission tiers
Groundwork SHALL sort actions into HARD DENY, HUMAN APPROVAL and AUTONOMOUS, enforce each tier through a native permission rule or a PreToolUse hook decision, and test each tier through the real hooks.

#### Scenario: Hard deny
- **WHEN** Claude pushes to a protected branch or force-pushes
- **THEN** the call is denied in every permission mode

#### Scenario: Human approval
- **WHEN** Claude reads a credential file, changes a cloud or cluster resource, or edits Claude Code settings
- **THEN** Claude Code's permission prompt asks the owner

#### Scenario: Autonomous
- **WHEN** Claude edits a repository file, runs tests or pushes a feature branch
- **THEN** no Groundwork rule or hook asks or denies
