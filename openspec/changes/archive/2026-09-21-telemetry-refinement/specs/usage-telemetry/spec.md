## ADDED Requirements

### Requirement: Record layout separates observed from declared
Each record SHALL contain an `observed` object (facts the hook determined from the transcript and environment: profile, tools, MCP servers, agent calls and types, files changed, tests run, implementation and deployment flags) and a `declared` object (fields taken from the model's response: playbook, execution mode, agent count and roles, evidence sources, validation, environment, outcome, clarification flag). Declared fields SHALL be recorded as stated, never presented as verified.

#### Scenario: profile comes from the environment
- **WHEN** `GROUNDWORK_PROFILE=work` is set and the response block states a different profile
- **THEN** `observed.profile` is `work`

### Requirement: Outcome from status language
`declared.outcome` SHALL be derived from the response's own status language — an `Overall:` line, the Status / Result sentence (state word first: complete, partial, blocked, failed, or a playbook status word), a bold verdict opener, or the result heading of a non-status playbook — with precedence failed > blocked > partial > complete, and SHALL be `unknown` when nothing recognisable is present.

#### Scenario: ambiguous status stays unknown
- **WHEN** the Status paragraph is "I looked at the code and the tests."
- **THEN** `declared.outcome` is `unknown`
