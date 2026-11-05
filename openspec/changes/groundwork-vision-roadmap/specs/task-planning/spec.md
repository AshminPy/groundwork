# Spec Delta

## Purpose

Helps Claude plan and order engineering tasks: the estimate, dependencies and priority recorded in each task's native OpenSpec plan, readiness, a deterministic and explained "what next", and intake of several tasks at once.

## ADDED Requirements

### Requirement: Planning facts live in the native plan
For a task with an OpenSpec change, Groundwork SHALL read planning facts from an un-numbered `## Planning` section in the change's `proposal.md`, `design.md` or `tasks.md`. It SHALL read the section as it is on every check and SHALL NOT keep a separate copy. The section can hold three kinds of line:
- `Estimate: <low>-<high> <unit>`: the unit is `hours` or `days`. The line can add `confidence: low|medium|high` and a short basis. An en dash is accepted in place of the hyphen;
- `Depends on: <KEY>[, <KEY>...]`;
- `Priority: high|normal|low`.

Groundwork SHALL report a line it cannot parse as unparsed and otherwise ignore it. A missing section SHALL mean no estimate, no dependencies and normal priority. A task without an OpenSpec change SHALL have no estimate, no dependencies and normal priority. Revising the section SHALL take effect on the next check and SHALL never void evidence or need approval.

#### Scenario: Planning facts are read from the plan
- **WHEN** COR-201's `proposal.md` has `## Planning` with `Estimate: 2-4 days, confidence: medium, basis: two similar VMs in modules/compute` and `Depends on: COR-202`
- **THEN** `groundwork task show COR-201` shows that estimate and the dependency on COR-202

#### Scenario: The plan is revised
- **WHEN** the owner edits the line to `Estimate: 1-2 days` during implementation
- **THEN** the next `groundwork task show COR-201` shows the new estimate and all recorded evidence still counts

#### Scenario: An unparsable line
- **WHEN** the section has `Estimate: soon`
- **THEN** the task shows no estimate and names the unparsed line

### Requirement: Estimates are labelled as estimates
Every place Groundwork shows an estimate SHALL label it as an estimate. That covers `groundwork task list`, `show`, `next`, the SessionStart snapshot and the statusLine. Each place SHALL show the range and the confidence, or `confidence unstated`. Groundwork SHALL NOT show an estimate as a date or a commitment. It SHALL NOT compute or invent an estimate; only the plan supplies one.

#### Scenario: An estimate is shown
- **WHEN** a task's plan has `Estimate: 2-4 days, confidence: medium`
- **THEN** the output reads as an estimate of 2-4 days with medium confidence and contains no completion date

#### Scenario: No estimate
- **WHEN** a task's plan has no `Estimate:` line
- **THEN** the output says the task has no estimate and does not show a number

### Requirement: Readiness from blockers and dependencies
A task SHALL be blocked when any of these holds:
- it has an open blocker recorded with `groundwork task block`;
- a task it depends on is open in the same repository's ledger;
- it depends on a key the ledger does not track. Groundwork SHALL then show the key as not tracked in this repository;
- it is part of a dependency cycle. Groundwork SHALL name the cycle.

Otherwise the task SHALL be ready. Removing the dependency line or clearing the blocker SHALL make the task ready on the next check.

#### Scenario: Waiting on another task
- **WHEN** COR-201 depends on COR-202 and COR-202 is open
- **THEN** COR-201 is blocked, with the reason that it waits on COR-202

#### Scenario: The dependency completes
- **WHEN** COR-202 completes
- **THEN** COR-201 is ready

#### Scenario: An untracked dependency
- **WHEN** COR-201 depends on DBA-77, which has no record in this repository's ledger
- **THEN** COR-201 is blocked and DBA-77 is shown as not tracked in this repository

#### Scenario: A cycle
- **WHEN** COR-1 depends on COR-2 and COR-2 depends on COR-1
- **THEN** both are blocked and the cycle is named

### Requirement: Deterministic, explained prioritisation
`groundwork task next` SHALL list the repository's open tasks in a deterministic order. It SHALL give the reason for each position and SHALL name the first ready task as the recommended next task. The order SHALL be decided by these keys, each applied only to break a tie in the keys above it:
1. ready before blocked;
2. higher priority first;
3. tasks that more open tasks depend on first;
4. tasks in implementing or verifying before tasks in planning;
5. smaller estimate upper bound first, and tasks without an estimate last;
6. older first.

`groundwork task list` and the SessionStart snapshot SHALL use the same order and SHALL name the recommended next task. The order SHALL be a recommendation only: Groundwork SHALL NOT start, stop, block or reorder work by itself.

#### Scenario: Unblocking work comes first
- **WHEN** COR-201 (estimate 2-4 days) depends on COR-202 (estimate 0.5-1 days), both are open with normal priority, and COR-202 has no blocker
- **THEN** `groundwork task next` recommends COR-202, gives "COR-201 depends on it" as the reason, and lists COR-201 as blocked

#### Scenario: The same inputs give the same order
- **WHEN** `groundwork task next` runs twice on an unchanged ledger and unchanged plans
- **THEN** both runs print the same order

#### Scenario: Owner priority wins over effort
- **WHEN** two ready tasks have no dependencies, one has `Priority: high` and a larger estimate, and the other has normal priority
- **THEN** the high-priority task is recommended

### Requirement: Several tasks in one prompt
When a submitted prompt names two or more keys that are not in the ledger, and each heads its own clause asking for work, Groundwork SHALL record each as its own task. Each task SHALL get:
- its clause as the mission;
- its own tier and risk;
- its own OpenSpec change when it is MATERIAL.

This SHALL happen in addition to selecting the task the prompt is for under the task-lifecycle rules. Claude SHALL be told which tasks were recorded and to order them with `groundwork task next`. A key that is only referred to, as in `after COR-2 is merged`, SHALL NOT create a task.

#### Scenario: Two tickets in one message
- **WHEN** the prompt `COR-201: Deploy a GoldenGate VM in GCP. COR-202: Create the GCS bucket for its trail files.` is submitted
- **THEN** COR-201 and COR-202 are both recorded, each with its own OpenSpec change, and Claude is told both keys and to run `groundwork task next`

#### Scenario: A reference is not a task
- **WHEN** the prompt `After COR-2 is merged, deploy COR-3 to staging` is submitted
- **THEN** only COR-3 is recorded

### Requirement: Planning guidance at MATERIAL intake
When Groundwork records a new MATERIAL task, the context it adds SHALL ask Claude to do four things before implementation:
- inspect the repository for analogous implementations and conventions;
- put prerequisites first in `tasks.md`;
- record missing information that genuinely blocks the work with `groundwork task block`;
- write the `## Planning` section with an estimate range, its confidence and basis, and any dependencies.

The guidance SHALL be added once, when the task is created. It SHALL NOT be added for STANDARD tasks, questions, or later prompts about the same task.

#### Scenario: A new infrastructure task
- **WHEN** `COR-123: Deploy GoldenGate VM in GCP` is submitted and recorded as MATERIAL
- **THEN** the added context contains the four planning asks

#### Scenario: A later prompt on the same task
- **WHEN** a second prompt mentions COR-123 while it is open
- **THEN** the four planning asks are not repeated
