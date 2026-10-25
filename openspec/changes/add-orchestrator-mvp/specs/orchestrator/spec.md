## ADDED Requirements

### Requirement: Subscription-only worker execution
The orchestrator SHALL run every worker as the official `claude -p` executable with its existing login. It SHALL refuse to start a worker unless `claude auth status` reports a logged-in `claude.ai` login on the `firstParty` provider. It SHALL remove `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and alternate-provider switches from the worker environment, SHALL never pass `--bare` or a permission-bypass mode, SHALL pass the prompt on stdin and argv as a list, and SHALL pass `--permission-prompts none`.

#### Scenario: Not on a subscription login
- **WHEN** `claude auth status` reports an API-key login
- **THEN** the task becomes BLOCKED with that reason and no worker process starts

#### Scenario: Quota reached
- **WHEN** a worker result reports a usage or rate limit
- **THEN** the task becomes BLOCKED with failure `quota`, no repair is attempted, and no other credential or provider is tried

### Requirement: Typed classification
The orchestrator SHALL classify every request into exactly one of QUESTION, TROUBLESHOOTING, PROJECT or DOCUMENTATION with a risk level, a reason and a workflow name. Deterministic rules SHALL decide when one category clearly wins; otherwise one Haiku call with a JSON schema SHALL decide. A classification that does not validate against the schema SHALL block the task before any execution.

#### Scenario: Clear question
- **WHEN** the request is `How does the session snapshot hook work?`
- **THEN** the category is QUESTION, decided by rules, with no model call

#### Scenario: Invalid model classification
- **WHEN** the model returns a category outside the four
- **THEN** the task becomes BLOCKED and no worker runs

### Requirement: Persistent, traceable task state
Each task SHALL have an id, a machine-readable contract (request, category, objective, workspace, constraints, required evidence, acceptance criteria, risk, status, approval, workflow, roles, model and effort with reason, retry count, validation results, outcome) and an explicit state. Every state change SHALL be recorded with a timestamp and reason. State SHALL survive a process exit.

#### Scenario: Show history
- **WHEN** `groundwork orch show <id>` runs after a finished task
- **THEN** it prints each state transition, each worker session and each check result

### Requirement: Approval before writes
A task that may change files SHALL stop in WAITING_APPROVAL until `groundwork orch approve <id>`; `reject` SHALL cancel it. Writes SHALL happen only in a git worktree on a `gw/<task>` branch. The orchestrator SHALL NOT commit, push, merge or release.

#### Scenario: Project request
- **WHEN** a PROJECT task is planned
- **THEN** it waits for approval, and only after approval a worktree is created and the implementation worker runs inside it

### Requirement: Deterministic validation and bounded repair
A task SHALL be PASSED only when its deterministic checks pass; a worker's own claim SHALL never be enough. Read-only workflows SHALL fail if any workspace file changed. A failed check SHALL send the failing output back to the same worker session for at most two repairs. Auth, quota, permission, model, timeout and cancellation failures SHALL NOT trigger repairs. When no check could run, the final status SHALL NOT be VERIFIED.

#### Scenario: Repair succeeds
- **WHEN** the first check run fails and the repaired code passes
- **THEN** the task is PASSED, VERIFIED, with retry count 1

#### Scenario: Repairs exhausted
- **WHEN** checks still fail after two repairs
- **THEN** the task is FAILED and the report shows the last failing check output

#### Scenario: Unauthorized write
- **WHEN** a read-only worker run leaves a changed file in the workspace
- **THEN** the task is FAILED with reason `unauthorized_write` and the event is recorded

### Requirement: Crash recovery without repeated side effects
Each worker call and each worktree creation SHALL be an operation with a durable id. On resume, a finished operation SHALL return its stored result without running again. An operation that started a write but did not finish SHALL block the task for the owner instead of running again. Sessions whose process is gone SHALL be marked abandoned.

#### Scenario: Crash after a finished worker call
- **WHEN** the process dies after an implementation worker finished but before the workflow saved its next step
- **THEN** `groundwork orch resume <id>` continues to validation and the worker is not called again

### Requirement: Configurable model routing
Model, effort and tools per role SHALL come from a policy file. Each worker call SHALL record the role, model, effort and the policy reason. An unknown model in the policy SHALL be rejected at load time.

#### Scenario: Default routing
- **WHEN** an ambiguous request is classified
- **THEN** the classifier call uses model `haiku` and effort `low` as the policy says
