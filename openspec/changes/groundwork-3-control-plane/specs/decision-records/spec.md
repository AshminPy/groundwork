# Spec Delta

## Purpose

Records why every material decision in a run was made, with its evidence, so any change can be explained and traced back later.

## ADDED Requirements

### Requirement: A decision record has a fixed schema
Each decision SHALL record: id, run, task, agent, model, time, question, options considered, choice, reason, evidence references, assumptions, confidence (high, medium or low), whether it is reversible, approver (auto or owner), and the id it supersedes, if any.

#### Scenario: Record fields
- **WHEN** a decision is read back
- **THEN** every schema field is present, with null allowed only for supersedes

### Requirement: Decisions without reason or evidence are refused
`gw decide` SHALL refuse a decision that has no reason, or that has no evidence reference and is not marked as an owner decision.

#### Scenario: No evidence
- **WHEN** an agent records a decision with a reason but no evidence and approver auto
- **THEN** the record is refused

### Requirement: Routing and approvals are recorded automatically
Each routing choice, each tier change, each egm verdict and each owner approval or rejection SHALL be written as a decision record without the agent having to do it.

#### Scenario: Owner approves a T4 change
- **WHEN** the owner approves the T4 plan
- **THEN** a decision with approver owner is recorded and linked to the plan

### Requirement: Any change can be traced back
`gw why` SHALL take a file path, task id or decision id and print the chain: commit, task, decision, evidence, and routing record. Commits made by builders SHALL carry `Task:` and `Decision:` trailers.

#### Scenario: Why was this file changed
- **WHEN** the owner runs `gw why charts/app/values.yaml`
- **THEN** the output lists the task, the decision ids with their reasons, and the evidence paths

### Requirement: Contradicting decisions are flagged
A decision that replaces an earlier one SHALL name it in supersedes. The final reviewer SHALL list as an open item any two live decisions that contradict each other.

#### Scenario: Two live decisions conflict
- **WHEN** D-002 chooses node roles and a later D-009 chooses IRSA without superseding D-002
- **THEN** the review lists the conflict for the owner

### Requirement: Decisions are promoted when a run finishes
When a run finishes, its decisions SHALL be copied into the OpenSpec design for the change and into the decision log of the Obsidian doc, with owner decisions listed separately.

#### Scenario: Doc decision log
- **WHEN** docs writes the run's Obsidian page
- **THEN** the page has a decision log with every live decision and its evidence reference
