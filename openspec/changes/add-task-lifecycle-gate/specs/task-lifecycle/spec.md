## ADDED Requirements

### Requirement: Deterministic task intake
Groundwork SHALL classify every submitted prompt in a git repository without a model call. A prompt that names a Jira-style key, or contains an engineering action verb and is not a question, a slash command or a system envelope, SHALL be registered as a task in the repository's task ledger. The ledger SHALL record:
- the task's key, or a generated `GW-<n>` key;
- the mission text;
- the tier (MATERIAL when cloud, infrastructure, data, security, production or deployment signals are present, otherwise STANDARD);
- the risk categories and a per-category checklist of prerequisites and open questions;
- the base commit and the paths already dirty at intake.

For a MATERIAL task it SHALL create the OpenSpec change.

The ticket a prompt is for SHALL be:
- the first key not yet in the ledger that starts the prompt or heads a clause (`KEY:` or `KEY - …`). It is registered even when the prompt also names known keys, in any order;
- otherwise the first open key, which receives that task's state. An open STANDARD task is escalated to MATERIAL (gated, with its own OpenSpec change) when the prompt carries MATERIAL signals and an action verb. A new key elsewhere in such a prompt, such as a dependency (`depends on COR-122`), is a reference and is not registered;
- otherwise a completed or cancelled key that starts the prompt or heads a clause, which starts a fresh task only when the prompt asks for work (an action verb). The old record is kept, and the new task gets its own plan directory;
- otherwise the first new key anywhere (`after COR-1 is merged, deploy COR-2`);
- otherwise the first key.

A keyless engineering prompt while a MATERIAL task waits on the owner SHALL be treated as input to that task, not as a new task. STANDARD work without a ticket key SHALL NOT be recorded.

#### Scenario: Jira-style infrastructure request
- **WHEN** the prompt `COR-123: Deploy a GoldenGate VM in GCP.` is submitted in a repository
- **THEN** task `COR-123` is recorded as MATERIAL with cloud, infrastructure, data, cost and deployment risk, an OpenSpec change `cor-123-deploy-goldengate-vm-gcp` exists, and Claude receives the checklist and the steps to plan and request approval

#### Scenario: A question is not a task
- **WHEN** the prompt `how does terraform state locking work?` is submitted
- **THEN** no task is created and no context is added

#### Scenario: A known task is resumed
- **WHEN** a prompt mentions `COR-123` while it is open
- **THEN** no second task is created and Claude receives COR-123's state and next action

#### Scenario: Follow-up work on a closed ticket
- **WHEN** COR-123 is complete and the prompt `COR-124: follow-up to COR-123 - deploy a replica VM in GCP` arrives
- **THEN** COR-124 is registered as a MATERIAL task and the repository is gated

#### Scenario: A dependency ticket is cited
- **WHEN** COR-126 is open and the prompt `COR-126: create it in us-central1-a. This depends on the network from COR-122, which is merged` arrives
- **THEN** COR-122 is not registered and Claude receives COR-126's state

#### Scenario: A closed ticket named as a precondition
- **WHEN** COR-126 is cancelled and the prompt `After COR-126 is merged, deploy COR-127 to GCP production` arrives
- **THEN** COR-127 is registered as a MATERIAL task and COR-126 is not reopened

#### Scenario: The owner answers a waiting task's questions
- **WHEN** COR-123 awaits approval and the owner sends a keyless reply describing the VM's zone and disk
- **THEN** no new task is created and Claude receives COR-123's state

### Requirement: Plan gate before approval can be requested
`groundwork task request-approval <KEY>` SHALL refuse unless:
- the task's OpenSpec change passes `openspec validate --strict`;
- `tasks.md` has at least one checkbox;
- `proposal.md` or `design.md` has non-empty sections Prerequisites, Risks, Missing Information, Estimate (with a number and the word confidence or uncertainty), Scope (at least one specific, repository-relative path pattern in backticks; `*`, `**`, absolute paths and `..` are refused) and Verification (at least one command in backticks).

On success it SHALL record the plan digest as the approval code and the number of tasks, and set the task to awaiting approval.

#### Scenario: Incomplete plan
- **WHEN** the plan has no Scope section
- **THEN** the command exits non-zero, names the missing section, and the task stays in planning

#### Scenario: Complete plan
- **WHEN** the plan is complete and valid
- **THEN** the command prints the approval code and the exact `/gw-approve <KEY> <code>` line for the owner

### Requirement: Owner-only approval bound to the plan
An approval SHALL be recorded only from a `UserPromptExpansion` event for the typed `/gw-approve <KEY> <code>` command, and only when the code equals the current plan digest, the plan still passes the plan check, and `tasks.md` has at least as many tasks as when approval was requested. The digest SHALL cover `proposal.md`, `design.md` and `specs/**/*.md`. A change to any of them after approval SHALL void the approval for execution until the owner approves the new digest. Ticking or annotating `tasks.md` SHALL NOT void it.

Claude SHALL be denied any tool call that invokes, schedules or sends `/gw-approve` or `/gw-cancel`: the Skill tool, a command that is not read-only, a nested `claude` session, scheduled prompts, messages to other sessions, or MCP calls. It SHALL also be denied any write to the task ledger or to those command files. Text that only names the command in a file edit, a subagent prompt or a read-only command is allowed.

#### Scenario: Approval text through an ordinary prompt
- **WHEN** a `UserPromptSubmit` prompt contains `approve COR-123 <code>`
- **THEN** no approval is recorded

#### Scenario: Stale approval code
- **WHEN** the owner types `/gw-approve COR-123 <old code>` after the plan changed
- **THEN** the expansion is blocked with a reason naming the current state and no approval is recorded

#### Scenario: Progress recorded in tasks.md
- **WHEN** Claude ticks tasks and adds notes to `tasks.md` after approval
- **THEN** the approval stays valid and in-scope edits stay allowed

#### Scenario: Claude tries to approve
- **WHEN** Claude calls the Skill tool for `gw-approve`, runs `claude -p '/gw-approve …'`, or schedules or sends a prompt containing it
- **THEN** the call is denied

### Requirement: Execution gate
While a MATERIAL task in the repository is in planning or awaiting approval:
- edit tools SHALL be allowed only inside the task's OpenSpec change directory and temporary directories;
- Bash SHALL be allowed only when every command in it is on the read-only allowlist, the OpenSpec CLI, or the Groundwork task CLI;
- mutating MCP tools SHALL be denied.

While approved (the digest unchanged):
- edits SHALL be allowed only within the approved Scope or the plan directory;
- sensitive commands SHALL be allowed only when their words equal an Approved Operation exactly (no extra arguments), and mutating MCP tools only when named there;
- non-read-only commands touching Groundwork's hooks, settings or ledger SHALL be denied.

A gate error while such a task is active SHALL deny the call.

#### Scenario: Implementation before approval
- **WHEN** Claude writes `infra/vm.json` while COR-123 awaits approval
- **THEN** the write is denied with a reason naming COR-123, its state and the next action

#### Scenario: Out-of-scope edit after approval
- **WHEN** Claude edits `README.md` and the approved Scope is `infra/goldengate/**`
- **THEN** the edit is denied

#### Scenario: Unapproved sensitive command
- **WHEN** Claude runs `gcloud compute instances delete vm-1` and no Approved Operation matches it
- **THEN** the command is denied

#### Scenario: Approved command with extra arguments
- **WHEN** the Approved Operation is `gcloud compute instances create gg-vm-1 --zone=us-central1-a` and Claude runs it with `--project=prod` added
- **THEN** the command is denied, and the reason says Approved Operations run exactly as written and changing one needs a new approval

### Requirement: Evidence capture and scope audit
After each tool call in a repository with an approved MATERIAL task, Groundwork SHALL record:
- each run of a declared verification command, with success or failure and the working-tree fingerprint. A run counts only when it ran exactly as declared and its exit status is the tool's: no extra arguments, not piped, and followed only by `&&`. Each declared entry must be one simple command;
- each foreground review subagent's parsed `REVIEW RESULT`, with the fingerprint;
- each approved sensitive operation's time.

After each Bash, Agent or MCP call, it SHALL report to Claude every changed path outside the allowed set, compared with the intake base commit. When the approval is void because the plan changed, the report SHALL say so instead of calling in-scope work unauthorized.

#### Scenario: Out-of-scope change through Bash
- **WHEN** a Bash command creates `notes.txt` outside the approved Scope
- **THEN** Claude is told that `notes.txt` is outside COR-123's scope and must be reverted

### Requirement: Evidence-gated completion
`groundwork task complete <KEY>` SHALL set a MATERIAL task to complete only when all of these hold:
- it is approved and the plan digest is unchanged;
- every task in `tasks.md` is checked, and it has at least as many tasks as at approval;
- the scope audit finds nothing;
- every declared verification command has a successful record on the current fingerprint, made after the last sensitive operation;
- the latest review on the current fingerprint reports zero MUST FIX findings.

Otherwise it SHALL exit non-zero and list each unmet condition.

#### Scenario: Missing review
- **WHEN** verification passed but no review was recorded on the current working tree
- **THEN** completion is refused and names the missing review

#### Scenario: Stale verification
- **WHEN** a file in scope changed after the verification run
- **THEN** completion is refused and names the verification command to re-run

### Requirement: Task continuity across sessions
The SessionStart snapshot SHALL list each open task in the repository's ledger, with key, tier, state, title, plan path and next action. `groundwork task list` and `groundwork task show <KEY>` SHALL render the same state from the ledger. Ledgers SHALL be separated by repository and by configuration directory.

#### Scenario: Fresh session
- **WHEN** a new session starts in the repository while COR-123 awaits approval
- **THEN** the snapshot shows COR-123, its state and the owner's approval command
