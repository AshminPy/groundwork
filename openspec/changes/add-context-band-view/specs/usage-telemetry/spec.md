## ADDED Requirements

### Requirement: Context fill at task end
The per-task record SHALL include `observed.ctx_pct`, the context-window % from the same session's latest statusLine usage record, when that record is at most 15 minutes old and holds a number from 0 to 100. Otherwise the field SHALL be absent. Reading it SHALL be bounded and fail-open, and SHALL NOT store anything beyond the number.

#### Scenario: Recent statusLine reading
- **WHEN** a turn ends and the session's newest usage record is 30 seconds old with `ctx_pct` 71.26
- **THEN** the per-task record has `observed.ctx_pct` 71.3

#### Scenario: No usable reading
- **WHEN** there is no usage record for the session, or the newest one is older than 15 minutes or not a number
- **THEN** the per-task record has no `ctx_pct` field
