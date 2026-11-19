## Purpose
Defines how Claude selects the simplest execution model for a task — main session, subagents, or native Claude Code Agent Teams — without the user having to name agents or ask for delegation.

## ADDED Requirements

### Requirement: Simplest execution model wins
The harness SHALL instruct Claude to use the main session for straightforward, mostly sequential work; subagents for focused, isolated investigation, research, or review whose result returns to the main session; and Agent Teams only when several genuinely independent workstreams benefit from parallel or independent reasoning.

#### Scenario: Simple task
- **WHEN** the task is TRIVIAL or a sequential STANDARD change
- **THEN** Claude performs it in the main session and creates no team

#### Scenario: Focused investigation or review
- **WHEN** a sub-task is self-contained, produces verbose output, or must be independent of the main context (e.g. an independent review)
- **THEN** Claude delegates it to a subagent and continues with the returned result

#### Scenario: Genuinely independent workstreams
- **WHEN** a task has two or more workstreams that can proceed without waiting on each other, with separate file ownership (for example architecture + implementation + validation, infrastructure + application changes, competing incident hypotheses, implementation plus independent integration/security validation)
- **THEN** Claude may form an Agent Team, states in one line why a team beats subagents, keeps the team proportional to the work (typically 2–4 teammates), gives each teammate an explicit scope and file ownership, and synthesizes results itself

### Requirement: Teams are used only where the platform supports them
The harness SHALL fall back to subagents when Agent Teams are not enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` unset or `0`) or when the session is non-interactive.

#### Scenario: Teams disabled
- **WHEN** Agent Teams are not enabled or the session runs with `-p`
- **THEN** Claude uses subagents for the same parallelism and does not report a team as having run

### Requirement: Specialists are derived from the task, not hard-coded
The harness SHALL NOT define permanent technology-specific teammate roles; Claude SHALL derive the specialists from the actual project and task, reusing existing subagent definitions (project, user, ECC) when one fits.

#### Scenario: User does not name agents
- **WHEN** the user describes only the outcome they want
- **THEN** Claude decides whether and how to delegate without asking the user to name agents or teams

### Requirement: Review gate recognises every reviewer shape
The review gate SHALL count an independent review as having happened when the session transcript contains an `Agent`/`Task` call whose `subagent_type` or `name` contains "review", or a `Skill` call whose name contains "review". The free-text `description` SHALL NOT count, because an unrelated call such as "Review existing tests before implementing" would otherwise satisfy the gate by coincidence.

#### Scenario: Reviewer teammate
- **WHEN** the lead spawns a teammate with `name: "security-reviewer"` and no `subagent_type`
- **THEN** the review gate treats it as an independent review

#### Scenario: "review" only in a description
- **WHEN** the only match is the word "review" inside an Agent call's `description` (for example an Explore call described as "Review existing test layout")
- **THEN** the review gate still blocks a complete, uncommitted OpenSpec change

#### Scenario: Non-reviewer teammate only
- **WHEN** the only Agent calls in the transcript are implementers or researchers with no "review" in `subagent_type` or `name`
- **THEN** the review gate still blocks a complete, uncommitted OpenSpec change
