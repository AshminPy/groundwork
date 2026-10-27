## ADDED Requirements

### Requirement: Outcome by context fill
The dashboard and the dated Markdown snapshot SHALL show, for the selected period, completion, verified outcome and gap rate per context-fill band (0–30, 30–50, 50–70, 70–85, 85–100%, lower edge inclusive). The band SHALL use the recorded `observed.ctx_pct`. When that is missing, it SHALL use the session's statusLine reading at or before the task end and no more than 15 minutes earlier. Tasks with neither SHALL be counted as not placed. Bands with fewer than 5 known outcomes SHALL be marked low data. The section SHALL state that it shows association, not cause, and SHALL embed no session identifiers.

#### Scenario: Recorded and matched tasks
- **WHEN** one task recorded `ctx_pct` 75 and another has only a statusLine reading of 20 two minutes before it ended
- **THEN** the section reports 2 tasks placed, one in 70–85% marked low data and one in 0–30%

#### Scenario: Reading after the task
- **WHEN** the only statusLine reading for a session is after the task ended
- **THEN** that task is not placed in a band

#### Scenario: No task has a reading
- **WHEN** no task in the period has a recorded or matched context reading
- **THEN** the section states that no task has a context reading and shows no band table
