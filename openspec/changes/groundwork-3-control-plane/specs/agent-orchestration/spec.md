# Spec Delta

## Purpose

Decides which on-demand agents run for a request, in what order, and when the work goes back for another round or stops and asks the owner.

## ADDED Requirements

### Requirement: Every request is routed to exactly one tier
The main session SHALL classify each request into exactly one tier: T0 answer, T1 quick fix, T2 standard, T3 material, or T4 guarded. Deterministic rules SHALL be evaluated before model judgment, and T4 rules SHALL take precedence over all others. When neither the rules nor the judgment settle it, the higher of the candidate tiers SHALL be chosen.

#### Scenario: Production keyword forces T4
- **WHEN** a request names a production environment or a destructive command such as `terraform destroy`
- **THEN** the run is recorded as T4, even if the change is one line

#### Scenario: Uncertain classification goes up
- **WHEN** the routing judgment cannot decide between T2 and T3
- **THEN** the run is recorded as T3

### Requirement: The routing decision is recorded
Each run SHALL record its tier, the rule or judgment that chose it, and the time, as a decision record that can be traced back later.

#### Scenario: Owner asks why a run was T3
- **WHEN** the owner runs `gw why` on a run
- **THEN** the output shows the tier and the routing rule that matched

### Requirement: Each tier starts only its own agents
The main session SHALL start only the agents defined for the run's tier. T0 uses explorer. T1 uses a builder and the verify gate. T2 adds investigator (for bugs), qa and final-reviewer. T3 adds planner, egm and docs. T4 adds investigator, planner, egm, the owner approval gate, final-reviewer and docs.

#### Scenario: Typo fix runs no planner
- **WHEN** a run is T1
- **THEN** no planner, qa, egm, final-reviewer or docs agent is started

### Requirement: Stages run in order behind gates
An agent SHALL be started only when its stage is open. On T3 and T4, builders SHALL NOT start until egm has approved the plan and tests. On T4, builders SHALL NOT start until the owner has approved. Docs SHALL NOT start until every task is done or explicitly blocked.

#### Scenario: Builder before approval is refused
- **WHEN** the main session tries to start a builder on a T3 run whose egm verdict is missing
- **THEN** the start is denied with the reason "egm approval required"

### Requirement: Agents do not start other agents
No Groundwork agent SHALL be able to start another agent. Only the main session SHALL assign tasks and start agents.

#### Scenario: Builder tries to delegate
- **WHEN** a builder agent attempts to start a subagent
- **THEN** the attempt is not possible or is denied, and the builder must return a handoff instead

### Requirement: Review loops are limited to two rounds
The egm-to-planner loop and the final-reviewer-to-builder loop SHALL each run at most two rounds. After the second failed round, the run SHALL stop that loop and ask the owner, listing the open items.

#### Scenario: Third review round is not started
- **WHEN** final-reviewer reports open items after round 2
- **THEN** no builder is restarted for those items and the owner is shown the open items

### Requirement: Work can move up a tier
Any agent SHALL be able to return "tier up" with a reason when the work is bigger than its tier allows. The main session SHALL then re-route the run and record the change as a decision.

#### Scenario: Quick fix turns out to be material
- **WHEN** a T1 builder finds that the change touches a module interface
- **THEN** the builder returns tier up, and the run is re-routed to T3 with a new decision record

### Requirement: A blocked task does not stop other tasks
When a task cannot continue because of missing access, an unclear requirement or a failed dependency, it SHALL be marked blocked with a reason, and independent tasks SHALL continue.

#### Scenario: One domain is blocked
- **WHEN** a task needs a builder that does not exist yet
- **THEN** that task is marked blocked with the reason, and the other tasks keep running
