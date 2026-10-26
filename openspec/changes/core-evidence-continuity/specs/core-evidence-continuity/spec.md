## ADDED Requirements

### Requirement: Usage is recorded per session without message content
The statusLine SHALL append at most one usage record per session per minute, containing session identity, repository, model, the cumulative cost estimate, context percentage and plan-usage percentages, and SHALL NOT store prompt or answer text.

#### Scenario: Two sessions draw from the same plan window
- **WHEN** two sessions are active in the same 5-hour window and the user runs `groundwork usage`
- **THEN** both sessions are listed, ranked by their cost increase in the window, and the report states that limits are shared by all sessions rather than naming one session as having exceeded them

#### Scenario: Usage record cannot be written
- **WHEN** the usage file cannot be written
- **THEN** the statusLine still renders and no error is shown in the status line

### Requirement: Task context survives compaction and new sessions
Groundwork SHALL keep one brief per task and reload it through the session-start snapshot after compaction and at session start, and SHALL prompt the session to update the brief once context reaches the configured checkpoint percentage.

#### Scenario: Automatic compaction
- **WHEN** a session with an active task is compacted
- **THEN** the next session-start snapshot contains that task's brief verbatim, with rejected hypotheses first

#### Scenario: Another session works on a different task in the same repository
- **WHEN** two sessions in one repository work on different ledger tasks
- **THEN** each session's brief is loaded and updated separately and neither overwrites the other

### Requirement: Citations in answers are checked against the files
Groundwork SHALL report file-and-line citations whose file or line does not exist in the session's working directories, or whose quoted text is not at those lines, without blocking the turn.

#### Scenario: Wrong line cited
- **WHEN** an answer cites `payapi/client.py:34` for a value defined at line 9 and quotes it
- **THEN** the citation is reported as "quote not at the cited lines"

### Requirement: Recommendations do not rest on unproven premises
When the decision gate is enabled, a recommendation to act SHALL state its premise as PROVEN with evidence or HYPOTHESIS with the cheapest test, and a recommendation resting on a HYPOTHESIS SHALL be presented as "test first" with the challenge review's result.

#### Scenario: Rollback recommended without proving the new version is at fault
- **WHEN** an answer recommends pinning back to a previous version and its premise ("the new version causes the failure") has no supporting evidence
- **THEN** the recommendation is presented as "test first" with the cheapest discriminating test, and the challenge review's result is attached

### Requirement: Every feature is measured against current Groundwork
Each feature SHALL be compared with Groundwork as installed on held-out benchmark cases graded by a frozen grader that never reads an arm's own status.

#### Scenario: Comparison with mismatched graders
- **WHEN** the two runs were graded with different grader fingerprints
- **THEN** the comparison refuses to produce results
