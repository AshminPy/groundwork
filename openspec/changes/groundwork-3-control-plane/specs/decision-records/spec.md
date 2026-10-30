# Spec Delta

## Purpose

Records why every material decision in a run was made, with its evidence, so any change can be explained and traced back later.

## ADDED Requirements

### Requirement: Only material decisions are recorded
A decision record SHALL be required for these kinds only: routing, tier change, egm verdict, owner approval or rejection, interface or design choice, deviation from the plan, and accepted risk. Other choices SHALL NOT need a record.

#### Scenario: Variable rename
- **WHEN** a builder renames a local variable
- **THEN** no decision record is required

### Requirement: A decision record has a fixed schema
Each record SHALL hold: id, kind, run, task, agent, model, time, question, options, choice, reason, evidence references, assumptions, confidence (high, medium or low), whether it is reversible, approver (auto or owner), and supersedes. `gw decide` SHALL fill in the id, run, task, agent, model and time.

#### Scenario: Short form
- **WHEN** an agent records a decision with only kind, question, choice, reason and evidence
- **THEN** the stored record has every schema field, with the context fields filled in by `gw`

### Requirement: Decisions without reason or evidence are refused
`gw decide` SHALL refuse a record with no reason. It SHALL also refuse an auto-approved record with no evidence reference, or one whose evidence path doesn't exist.

#### Scenario: Invented evidence path
- **WHEN** an agent cites an evidence path that doesn't exist
- **THEN** the record is refused

### Requirement: Hooks record routing and approvals
Routing, tier changes, egm verdicts and owner approvals or rejections SHALL be recorded by hooks and `gw`, without the agent writing them.

#### Scenario: Owner approves a T4 change
- **WHEN** the owner runs `gw approve`
- **THEN** an owner decision is recorded and linked to the plan

### Requirement: Any change can be traced back
`gw why` SHALL take a file path, task id, decision id or run id and print the chain: commit, task, decisions, evidence and routing record. Commits made under a run SHALL carry `Task:` and `Decision:` trailers. A commit under a run without a `Task:` trailer SHALL be denied.

#### Scenario: Why was this file changed
- **WHEN** the owner runs `gw why charts/app/values.yaml`
- **THEN** the output lists the task, the decision ids with their reasons, and the evidence paths

#### Scenario: Commit without trailer
- **WHEN** a builder commits under an active run without a `Task:` trailer
- **THEN** the commit is denied with the trailer format

### Requirement: Contradicting decisions are flagged
A decision that replaces an earlier one SHALL name it in supersedes. `gw decide` SHALL warn when a new decision has the same kind and topic as a live decision but doesn't supersede it. The final reviewer SHALL list each warning as an open item.

#### Scenario: Two live decisions conflict
- **WHEN** a decision chooses IRSA while an earlier live decision chose node roles, without superseding it
- **THEN** `gw` warns, and the review lists the conflict for the owner

### Requirement: Decisions are promoted when a run finishes
When a run finishes, its live decisions SHALL be written into the change's OpenSpec design and into the decision log of the Obsidian page. Owner decisions SHALL be listed separately.

#### Scenario: Doc decision log
- **WHEN** docs writes the run's Obsidian page
- **THEN** the page has a decision log with every live decision and its evidence reference
