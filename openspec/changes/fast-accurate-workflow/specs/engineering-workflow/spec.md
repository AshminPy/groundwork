## ADDED Requirements

### Requirement: Plans are fact-checked
Every claim a design makes about existing code or behaviour SHALL cite `path:line` or the command whose output shows it, and SHALL be checked against that source before implementation starts. A claim that cannot be checked SHALL be labelled UNVERIFIED.

#### Scenario: Claim about existing code
- **WHEN** a design says the ledger keeps every history event
- **THEN** it cites the line that defines the history limit, and the check shows the limit before review

### Requirement: MUST FIX bar stated before review
The reviewer's brief SHALL state the MUST FIX bar, using the workflow's existing MUST FIX categories, before the review starts. Heuristic edge cases in results already labelled pattern-matched or an estimate SHALL be NICE TO HAVE, unless the finding falls in one of the existing MUST FIX categories.

#### Scenario: Pattern-matched metric edge case
- **WHEN** a reviewer finds a phrasing the correction pattern misses
- **THEN** it is reported as NICE TO HAVE and does not by itself start another review round

### Requirement: Push after each green step
When a task includes pushing, or the session runs in an ephemeral container, the feature branch SHALL be committed and pushed after each step whose tests pass, never to `main`. The step that completes an OpenSpec change's `tasks.md` SHALL stay uncommitted until an independent review reports `Must-fix: 0`, because the review Stop hook checks only uncommitted changes.

#### Scenario: Container restart
- **WHEN** the cloud container restarts mid-task
- **THEN** the work up to the last green step is on the remote branch

#### Scenario: Last task box ticked
- **WHEN** a step completes every task in an OpenSpec change and its tests pass
- **THEN** it is not committed until an independent review reports `Must-fix: 0`, so the review Stop hook still applies

### Requirement: Cloud sessions have the repository's tools
A cloud session on this repository SHALL have pytest and the pinned OpenSpec CLI available, and SHALL run Python with `PYTHONDONTWRITEBYTECODE=1`. The hook SHALL do nothing outside cloud sessions.

#### Scenario: Fresh cloud container
- **WHEN** a cloud session starts without pytest
- **THEN** the SessionStart hook installs it, and `python3 -m pytest tests -q` runs

#### Scenario: Local session
- **WHEN** the hook runs without `CLAUDE_CODE_REMOTE=true`
- **THEN** it exits 0 and installs nothing
