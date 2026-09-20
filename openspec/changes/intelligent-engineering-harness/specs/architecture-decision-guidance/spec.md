## Purpose
Defines how Claude evaluates, sizes, and records architecture and implementation decisions so that MATERIAL work is built to the smallest design that satisfies today's requirement while preserving low-cost paths for reasonably foreseeable change.

## ADDED Requirements

### Requirement: Governing design principle
The harness SHALL instruct Claude to build the smallest design that satisfies the current requirement while preserving clear, low-cost paths for reasonably foreseeable change, and SHALL prohibit both over-engineering for hypothetical requirements and hard-coding obvious variation points.

#### Scenario: Obvious variation point is present
- **WHEN** the project evidence clearly shows more than one environment, provider, cluster, model, region, tenant, backend, or similar variant now or in the stated roadmap
- **THEN** Claude designs a configuration or interface boundary for that variant instead of wiring the first instance permanently into implementation, and records the boundary in the DECISION record

#### Scenario: No concrete reason for an abstraction
- **WHEN** a proposed abstraction, layer, or plugin point has no requirement, evidence, or stated constraint that needs it
- **THEN** Claude does not build it and says so in one line

### Requirement: Quality dimensions are decision criteria, not a checklist
The harness SHALL provide the quality dimensions (correctness, modularity, reusability, extensibility, maintainability, operational excellence, reliability, availability/resilience, scalability, security, least privilege, observability, testability, automation, configuration management, deployment/rollback, performance/efficiency, cost effectiveness, sustainability, failure handling, supportability/troubleshooting) as criteria Claude applies only where relevant to the change.

#### Scenario: STANDARD change touching one module
- **WHEN** the change is STANDARD tier
- **THEN** Claude considers only the dimensions the change actually affects and does not produce a dimension-by-dimension write-up

#### Scenario: MATERIAL change
- **WHEN** the change is MATERIAL tier
- **THEN** before implementation Claude explicitly answers the pre-MATERIAL questions (what is likely to change; what should be configuration; what needs a stable interface; how another instance/provider/environment is added; which manual operational steps can be automated; what fails when a dependency is unavailable; how an operator observes and troubleshoots it; how it is tested; how it is deployed and rolled back; what security boundary exists; scaling and cost implication) and records the material answers in the OpenSpec design or a DECISION record

### Requirement: DECISION record for material decisions
Material technical decisions SHALL be recorded as DECISION / EVIDENCE / WHY / TRADEOFFS / VALIDATION METHOD / UNCERTAINTY, with real references, and the format SHALL NOT be required for trivial decisions.

#### Scenario: Material decision
- **WHEN** a choice can materially affect architecture, security, reliability, production behaviour, deployment, data integrity, cost, maintainability, or compatibility
- **THEN** Claude writes the six-field DECISION record with at least one real repository, runtime, or official-documentation reference

#### Scenario: Trivial choice
- **WHEN** the choice is a local implementation detail with no such impact
- **THEN** no DECISION record is produced
