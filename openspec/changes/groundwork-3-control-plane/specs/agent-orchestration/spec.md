# Spec Delta

## Purpose

Decides which on-demand agents run for a request, in what order, and when the work goes back for another round or stops and asks the owner.

## ADDED Requirements

### Requirement: Every request is routed to exactly one tier
The main session SHALL classify each new request into exactly one tier: T0 answer, T1 quick fix, T2 standard, T3 material, or T4 guarded. Deterministic rules SHALL set a minimum tier, and the main session SHALL NOT open a run below it. When several rules match, the highest tier SHALL apply.

#### Scenario: Rule floor cannot be lowered
- **WHEN** a prompt matches a T4 rule and the main session runs `gw run new --tier T2`
- **THEN** the command is refused, and the message names the T4 rule

#### Scenario: Conflicting rules
- **WHEN** a prompt matches one T2 rule and one T3 rule
- **THEN** the minimum tier is T3

#### Scenario: Negated wording
- **WHEN** a prompt says "make this production-ready" or "never touch prod"
- **THEN** no T4 rule matches on those words alone

### Requirement: Follow-up prompts join the active run
A prompt SHALL join the active run unless the owner starts a new one with `/groundwork:run`, or no run is active. Joining a run SHALL NOT change its tier, except through tier-up.

#### Scenario: Owner says continue
- **WHEN** a T3 run is active and the owner types "yes, continue"
- **THEN** no new run is created, and the T3 run continues

### Requirement: The routing decision is recorded
Each run SHALL record its tier, the rules that matched, and the main session's reason, as a decision record. T0 answers SHALL be recorded in the session's routing log with the rules that matched.

#### Scenario: Owner asks why a run was T3
- **WHEN** the owner runs `gw why <run-id>`
- **THEN** the output shows the tier, the matched rules and the reason

### Requirement: Each tier has a fixed agent roster
The main session SHALL start only the agents listed for the run's tier. T0: none, with explorer optional for large searches. T1: none, because the main session edits under the guards. T2: investigator for bugs only, qa, one builder, final-reviewer. T3: planner, qa, egm, builders, final-reviewer, docs. T4: investigator, planner, qa, egm, builders, final-reviewer, docs.

#### Scenario: Typo fix starts no agent
- **WHEN** a run is T1
- **THEN** no subagent is started, and the verify gate still runs

#### Scenario: T4 includes qa
- **WHEN** a T4 run reaches the test stage
- **THEN** qa is started

### Requirement: Stages run in order behind gates
An agent SHALL start only when its stage is open. On T3 and T4, builders SHALL NOT start until egm has approved. On T4, builders SHALL NOT start until the owner has approved through `gw approve`. Docs SHALL NOT start until every task is done or blocked.

#### Scenario: Builder before egm approval
- **WHEN** the main session starts a builder on a T3 run with no egm approval
- **THEN** the start is denied with the reason "egm approval required"

#### Scenario: Builder before owner approval
- **WHEN** egm has approved a T4 plan but the owner has not run `gw approve`
- **THEN** the builder start is denied

### Requirement: Each agent start names its task
Every start of a Groundwork task agent (every Groundwork agent except explorer) SHALL name the run id and task id. A start that doesn't name them SHALL be denied. The agent SHALL stay bound to that task until it stops. Explorer and non-Groundwork subagents SHALL run read-only.

#### Scenario: Missing task id
- **WHEN** the main session starts builder-terraform without a task id
- **THEN** the start is denied with the reason "task id required"

### Requirement: Agents do not start other agents
Every Groundwork agent SHALL declare its `tools` list, and no list SHALL include the `Agent` tool. Only the main session SHALL start agents.

#### Scenario: Agent file without tools
- **WHEN** an agent file omits `tools`
- **THEN** the release check fails, because the agent would inherit `Agent`

### Requirement: Review loops are limited to two rounds
The egm-to-planner loop and the final-reviewer-to-builder loop SHALL each run at most two rounds. After the second failed round, the loop SHALL stop, and the open items SHALL be shown to the owner.

#### Scenario: Third review round is not started
- **WHEN** final-reviewer reports open items after round 2
- **THEN** no builder is restarted for those items, and the owner sees the list

### Requirement: Work can move up a tier
Any agent, or the guard at action time, SHALL be able to raise the run's tier with a reason. The run SHALL then continue under the higher tier's roster and gates, and the change SHALL be recorded as a decision. A tier SHALL never be lowered during a run.

#### Scenario: Quick fix turns out to be material
- **WHEN** a T1 edit would change a module interface
- **THEN** the run moves to T3 with a decision record, and planning starts

### Requirement: A blocked task does not stop other tasks
When a task cannot continue, it SHALL be marked blocked with a reason. Tasks that don't depend on it SHALL continue.

#### Scenario: Independent task continues
- **WHEN** T6 is blocked and T5 doesn't depend on it
- **THEN** T5 is still assigned and finishes

### Requirement: The owner approves or rejects through a command
`gw approve <run>` and `gw reject <run> --reason` SHALL record an owner decision and open or close the waiting stage. They SHALL be the only way to pass the T4 gate and the only way to continue after a loop limit.

#### Scenario: Owner rejects a T4 plan
- **WHEN** the owner runs `gw reject r-1 --reason "rollback missing"`
- **THEN** the run stops, no builder starts, and an owner decision with the reason is recorded
