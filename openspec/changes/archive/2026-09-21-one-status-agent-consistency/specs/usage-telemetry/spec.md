## ADDED Requirements

### Requirement: Agent facts reconciled with observed calls
`declared.agent_count`, `declared.execution_mode` and `declared.agent_roles` SHALL be reconciled against the Agent calls observed in the current turn: when calls were observed, the count is the observed number, the mode is at least `subagents`, and declared roles are kept only when their number matches; when no calls were observed and the block declares a single agent, the count is 0 with no roles; when nothing could be observed (unreadable transcript) the declared values are kept as stated.

#### Scenario: declared count disagrees with observed calls
- **WHEN** the block says `2 subagents` and lists two roles but one Agent call was observed
- **THEN** `declared.agent_count` is 1 and `declared.agent_roles` is the observed agent type
