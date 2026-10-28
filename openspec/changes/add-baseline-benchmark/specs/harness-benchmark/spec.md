## ADDED Requirements

### Requirement: Fair arms
The benchmark SHALL run V, E and G with the same model, effort, request text, tool list, fixture, time limit and Bash sandbox. The arms are plain Claude Code (V), Claude Code with ECC and OpenSpec (E), and Groundwork (G). They SHALL differ only in their configuration directory and `PATH` prefix, and each arm's installed versions SHALL be recorded.

#### Scenario: Canary before cases
- **WHEN** a run starts
- **THEN** every arm passes the isolation canary and its metadata check before any case runs, or nothing runs

#### Scenario: Bash probe not refused
- **WHEN** a canary Bash probe reads a fake key or reaches the network
- **THEN** no write-capable case runs, and the report says it covers read-only cases only

### Requirement: Frozen held-out split
The scored-case split SHALL be seeded and stratified by category. It SHALL be frozen before the first baseline run, together with its hash, the case-file hash and the grader fingerprint. Calibration SHALL use dev cases only, after the freeze.

#### Scenario: Grader changed after freezing
- **WHEN** a grader rule changes
- **THEN** the split and fingerprint are re-frozen and dev results are re-run before held-out results are read

### Requirement: Independent grading
Scores SHALL come from hidden tests and frozen rules, never from the agent's own status. The grader SHALL run them after the agent exits, and hidden tests SHALL enter the run copy only at that point.

#### Scenario: Agent claims success
- **WHEN** the final text matches the frozen claim regex but the hidden tests fail
- **THEN** the run scores as not completed and counts as an incorrect claim

### Requirement: Paired statistics and decision rule
The report SHALL show paired held-out differences (G minus the reference arm), with bootstrap confidence intervals, wins, ties and losses. It SHALL also show the noise floor and the minimum detectable difference. It SHALL apply the pre-registered directional rule.

#### Scenario: Difference within noise
- **WHEN** the completion confidence interval includes 0
- **THEN** the report says "no measurable difference" for that comparison

#### Scenario: Groundwork worse
- **WHEN** the completion confidence interval's upper bound is below 0
- **THEN** the report says G is worse for that comparison

### Requirement: Budget control
A calibration pass SHALL run before the full baseline. The runner SHALL stop cleanly at the plan-usage limit and resume.

#### Scenario: Usage limit reached
- **WHEN** five-hour usage reaches 80%
- **THEN** the runner stops and a re-run with the same run id continues
