## ADDED Requirements

### Requirement: Playbook, Routine, Role, Skill and Tool are distinct concepts
`rules/task-routing.md` SHALL name Playbook, Routine, Role, Skill and Tool as five distinct concepts, each with its own one-line definition, and SHALL state that a Routine's own scheduled run still follows the same router and `engineering-workflow.md` internally — a different trigger (a schedule, not a user message) and execution mode (headless, non-interactive), not a second rule system.

#### Scenario: Vocabulary check
- **WHEN** `rules/task-routing.md` is read
- **THEN** it contains a section naming all five concepts (Playbook, Routine, Role, Skill, Tool), and `tests/test_playbooks.py` asserts all five terms are present

#### Scenario: Existing output-contract section renumbered, not restructured
- **WHEN** the five-concepts section is inserted before the existing "Universal output contract" section
- **THEN** the output-contract section is renumbered to stay sequential, its own content is otherwise unchanged, and the router test suite is updated to match the new heading number

### Requirement: Capability resolution order is judgment guidance, not a decision tree
`rules/engineering-workflow.md` SHALL state a capability-resolution order — existing repository/project tooling, then a Claude Code native capability, then a trusted already-installed skill, then a trusted already-configured MCP server or official CLI/API, then browser/Chrome, then the user for a genuine decision or authorization — as guidance applied proportionally to the task, not a hard-coded if/else tree, and SHALL state explicitly that choosing a capability does not itself decide tier, evidence, or authorization requirements, which remain governed by the existing rules unchanged.

#### Scenario: Mutation still requires the existing authorization rule regardless of mechanism
- **WHEN** a mutation is about to happen through any resolved capability — Bash, MCP, CLI, or browser
- **THEN** the same existing authorization rule (`engineering-workflow.md` §4) gates it, and capability *availability* is explicitly stated to never imply mutation *permission*

#### Scenario: Browser-driven mutation requires read-back verification
- **WHEN** a browser-driven action mutates external state
- **THEN** the rule text requires reading the result back (reload/re-fetch) before reporting the mutation VERIFIED — a successful click or submit alone is not sufficient evidence
