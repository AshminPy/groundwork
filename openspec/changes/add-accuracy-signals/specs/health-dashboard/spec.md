## MODIFIED Requirements

### Requirement: Local health dashboard from telemetry
The system SHALL generate `~/.claude/groundwork/reports/dashboard.html` from the telemetry files without a server or an LLM, embedding only aggregated counters and short labels, with client-side filters for period, profile, playbook, version and environment. It SHALL use no network unless `generate --github` is given (opt-in CI truth).

#### Scenario: empty telemetry
- **WHEN** the telemetry files are missing or empty
- **THEN** the dashboard is still written, shows 0 tasks and N/A metrics, and the command exits 0

### Requirement: Honest metrics
Every rate SHALL show its numerator and denominator, and metrics without data SHALL show N/A or "insufficient data", never 0%. A rate with fewer than 5 cases SHALL show "insufficient data (n)", and one with 5 to 19 cases SHALL be flagged "low data". Trends SHALL appear only when both periods have at least 5 cases. Each Performance-gaps metric SHALL carry its labels (observed, declared, pattern, estimate, opt-in). Each declared-based metric SHALL show the outcome-unstated share of its population.

#### Scenario: no ground truth
- **WHEN** a Performance-gaps question has no data source, or too few cases
- **THEN** it shows "not collected" with the reason, or "insufficient data (n)", never 0%

## ADDED Requirements

### Requirement: Performance gaps section
The dashboard and Markdown snapshot SHALL include a Performance gaps section answering questions 1a to 11 of the design, each with its definition, numerator and denominator, labels and notes. Questions 3a and 3b SHALL read the Groundwork task ledger without rendering any of its command text.

#### Scenario: Said complete while tests failed
- **WHEN** a turn changed files, declared complete, and its last test call with a known result failed
- **THEN** it counts in the 1a numerator; a masked or background test is ignored for 1a

#### Scenario: Verified with an unknown-result test
- **WHEN** a turn declared verified and ran only `pytest -q | tail -5`
- **THEN** it is not counted as verified without a check (1b)

#### Scenario: Two Stops in one turn
- **WHEN** a reply check blocked the first Stop of a prompt (outcome complete), and the follow-up Stop's reply states no outcome
- **THEN** the turn is counted once, with outcome complete, and counts toward question 11

#### Scenario: Final test state (Q2)
- **WHEN** a file-changing turn's test calls are fail, then pass
- **THEN** its final test state is pass; a turn whose only test was piped is "unknown"; a turn with no test call is "none"

#### Scenario: First review found defects (Q3b)
- **WHEN** a MATERIAL task's history shows reviews with must-fix 2, then 0
- **THEN** it counts in the 3b numerator, and its reviews-until-clean value is 2

#### Scenario: Correction after completion (Q4)
- **WHEN** a turn declared complete is followed 10 minutes later in the same session by a prompt flagged as a correction
- **THEN** it counts in the Q4 numerator; a flagged prompt 3 hours later does not count

#### Scenario: Citations (Q5)
- **WHEN** the window's turns hold citations checked 6, resolved 5, unchecked 2
- **THEN** Q5 shows 5/6 with "low data", and "2 not checkable"

#### Scenario: Guardrail follow-through (Q7)
- **WHEN** a task-gate ask is followed by a PostToolUseFailure row with the same `tool_use_id`
- **THEN** that ask counts as approved; an ask with no matching tool row counts as declined

#### Scenario: Cost (Q8)
- **WHEN** two turns end 30 seconds apart and share one statusLine reading
- **THEN** the second turn is outside cost coverage, and coverage shows it

#### Scenario: Compaction (Q9)
- **WHEN** a session compacts once
- **THEN** the 1a and Q4 rates of the three turns before and the three turns after are shown side by side, labelled association

#### Scenario: Version comparison (Q10)
- **WHEN** versions 2.5.0 and 2.6.0 each have at least 5 cases for a metric
- **THEN** both rates are shown; a version with fewer cases shows "insufficient data (n)"

#### Scenario: Unstated outcome with a failing test
- **WHEN** a file-changing turn states no outcome and its last test failed
- **THEN** it is counted in the "outcome unstated, last test failed" row

#### Scenario: Window edge
- **WHEN** a failing test belongs to a turn outside the window
- **THEN** it affects no in-window turn

#### Scenario: Shipped before review
- **WHEN** a ledger MATERIAL task records a sensitive operation before its first review at must-fix 0
- **THEN** it counts in the 3a numerator

#### Scenario: Task ledger empty
- **WHEN** the ledger has no MATERIAL tasks
- **THEN** 3a and 3b show "not collected: task ledger empty"

### Requirement: Turn attribution
Turns SHALL be (`session_id`, `prompt_id`), with the Stop records of a turn merged (the last stated outcome and validation, citations summed). Tool rows and signals SHALL join on `prompt_id`; records without one SHALL use the labelled time fallback; tool rows of prompts without a Stop SHALL be counted as `no_stop`. Attribution SHALL happen before window filtering.

#### Scenario: Prompt with no Stop
- **WHEN** a prompt has tool rows but no Stop record
- **THEN** it is counted apart as "with tool calls but no Stop record" and joins no other turn

### Requirement: Opt-in CI truth
`generate --github` SHALL check the newest 50 in-window commit turns read-only through `gh api --method GET`:
- paginated check-runs and the combined status;
- only after validating `owner/repo` and the 40-hex SHA;
- with a 10-second timeout per call;
- mapping conclusions as in design D8.

Without the flag, no subprocess SHALL run. A missing or unauthenticated `gh` SHALL show "not available". The last stdout line SHALL remain `records=…`.

#### Scenario: No flag
- **WHEN** `generate` runs without `--github`
- **THEN** no subprocess calls `gh`, and question 6 shows "opt-in: run generate --github" with the number of commit turns recorded

#### Scenario: Unsafe repo value
- **WHEN** a recorded `repo` is `../../user`
- **THEN** that commit is skipped and no `gh` call is made for it
