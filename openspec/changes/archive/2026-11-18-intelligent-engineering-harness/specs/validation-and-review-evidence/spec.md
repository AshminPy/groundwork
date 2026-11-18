## Purpose
Defines the evidence required behind every test, review, and completion claim: a progressive validation ladder derived from the project's own tooling, runtime validation when runtime behaviour matters, and independent review with MUST FIX / NICE TO HAVE classification.

## ADDED Requirements

### Requirement: Validation is derived from project evidence
Claude SHALL derive verification commands from the project's own README, Makefile, package manifests, CI configuration, or test layout, and SHALL NOT run generic commands (e.g. `pytest`, `npm test`, `terraform validate`) unless project evidence shows they apply.

#### Scenario: Project documents its commands
- **WHEN** the repository has a Makefile target, package script, CI job, or README section for tests, lint, or build
- **THEN** Claude runs those commands and reports the exact command and result line

#### Scenario: No documented commands
- **WHEN** no project evidence names a verification command
- **THEN** Claude infers the narrowest applicable check from the actual files present, labels it INFERENCE, and says what remains unverified

### Requirement: Progressively stronger validation
Claude SHALL apply the validation ladder in order where relevant — static/config validation, unit tests, integration tests, build/package validation, infrastructure validation, controlled runtime test, real non-production/live validation — and SHALL test the real path when the change is runtime-dependent and a safe environment is available.

#### Scenario: Runtime-dependent change
- **WHEN** the change affects an API, deployed service, MCP call, Kubernetes resource, cloud resource, logs, metrics, or traces
- **THEN** Claude validates against the real path (actual request, health check, real call, kubectl read, log/metric/trace observation) when safe and available, and never claims runtime success from mocks alone

#### Scenario: Real validation not possible
- **WHEN** the real environment, credentials, or authorization are unavailable
- **THEN** Claude marks the step RUNTIME VALIDATION REQUIRED, states exactly what remains unverified, and sets the completion status to PARTIAL or BLOCKED, never COMPLETE

### Requirement: Independent review with actionable classification
For MATERIAL work Claude SHALL obtain an independent fresh-context review (ECC reviewer, subagent reviewer, or Agent Team reviewer teammate) that classifies findings as MUST FIX (correctness, security, reliability, deployment/runtime failure, significant maintainability) or NICE TO HAVE, SHALL fix MUST FIX findings and re-validate, and SHALL NOT loop on cosmetic or style preferences.

#### Scenario: MUST FIX finding
- **WHEN** a reviewer reports a MUST FIX finding
- **THEN** Claude fixes it, re-runs the relevant validation, and records the fix in the completion evidence

#### Scenario: Only NICE TO HAVE findings
- **WHEN** a review returns only NICE TO HAVE findings
- **THEN** the change may complete; the findings are listed, not blocking

### Requirement: Completion status keeps every distinction
The completion block SHALL report Code, Tests, Reviewed, Merged, Deployed, and Live validated separately with evidence, and Overall SHALL be COMPLETE only when every applicable row has evidence.

#### Scenario: Tests green but no runtime check in scope
- **WHEN** tests pass and deployment or live validation is in scope but was not performed
- **THEN** Overall is PARTIAL with the missing rows marked ❌ "not attempted", never N/A
