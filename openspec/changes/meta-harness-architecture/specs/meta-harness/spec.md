## ADDED Requirements

### Requirement: Claims are checked against their sources
The Question and Documentation workflows SHALL record each material claim with source references. They SHALL mark a claim as located only when the orchestrator finds the quoted text at the cited file range or allowlisted URL.

#### Scenario: Quote not found at the cited lines
- **WHEN** a worker cites an existing file, but the quote is not in the cited line range
- **THEN** the claim is recorded as not located, and the answer is at most UNVERIFIED

### Requirement: Reviewer sessions are independent
A reviewer SHALL run in a new Claude Code session with read-only tools. It SHALL get primary evidence that the orchestrator collected, and SHALL never get a resumed implementer session.

#### Scenario: Support review of a material claim
- **WHEN** a support review runs
- **THEN** it uses a new session ID, and its prompt contains the orchestrator-fetched source excerpt

### Requirement: Profiles are isolated by account
Each profile SHALL have its own state files and a pinned account organisation. Preflight SHALL block a task whose login organisation differs from its profile's.

#### Scenario: Work task on a personal login
- **WHEN** a work-profile task starts while `claude auth status` reports a different `orgId`
- **THEN** the task is BLOCKED before any worker runs

### Requirement: Session spawning is bounded
The orchestrator SHALL enforce a per-task session limit, the existing repair limit of two, and at most two concurrent workers.

#### Scenario: Session budget exhausted
- **WHEN** a task would start a session beyond its limit
- **THEN** the task is BLOCKED with the reason, and no session starts

### Requirement: Claim statuses are assigned by code
Each material claim SHALL receive exactly one status, decided first-match-wins in the order CONTRADICTED, VERIFIED, SOURCE_SUPPORTED, UNVERIFIED: VERIFIED only when an orchestrator-run deterministic probe matches an observable claim whose cited sources are fresh; CONTRADICTED when a deterministic rule or a valid Set B excerpt contradicts it; SOURCE_SUPPORTED when it is located, fresh, meets the requirement policy and is reviewed as supported; otherwise UNVERIFIED with a reason code. Only code rules SHALL mark a claim non-material. No numeric confidence SHALL be shown.

#### Scenario: Vendor doc version differs from the pinned version
- **WHEN** a claim's located vendor-doc source states a version different from the version the repository pins
- **THEN** the claim is CONTRADICTED by rule, and the answer status is CONTRADICTED after the one allowed repair

#### Scenario: Interpretive claim reviewed as supported
- **WHEN** an interpretive claim is located, fresh, meets its requirement policy, and the reviewer returns supported with a Set A excerpt
- **THEN** the claim is SOURCE_SUPPORTED, never VERIFIED

### Requirement: Context handoff happens only at a safe boundary
When context utilisation reaches the configured threshold, the Session Manager SHALL mark a handoff as pending, SHALL NOT interrupt a running call, and SHALL start a fresh session only after the current operation is done and its validation passes. A failed handoff SHALL leave the prior session and checkpoint intact and block the task.

#### Scenario: Git state changed before handoff
- **WHEN** a pending handoff finds the git HEAD differs from the recorded one
- **THEN** the task is BLOCKED with `handoff_validation`, and no new session starts

### Requirement: Benchmark grading is independent of the harness
Benchmark graders SHALL read only final answers, resulting files and side-effect counters, never an arm's own status or claims. Held-out keys SHALL live in `~/groundwork-bench-keys/`, outside every arm's working folder and its ancestors. Every arm SHALL run with deny rules for the keys and credential paths, proven by a canary test through each arm's real launch path before any case runs. Where an arm emits a tool-call stream, any tool call touching the keys SHALL invalidate that run. For every arm, a match of key or canary fingerprints in the outputs SHALL invalidate that run.

#### Scenario: An arm reads the answer key
- **WHEN** an arm's stream shows a tool call on a path under `~/groundwork-bench-keys/`, or its output contains a key fingerprint
- **THEN** that run is marked invalid and excluded from the metrics
