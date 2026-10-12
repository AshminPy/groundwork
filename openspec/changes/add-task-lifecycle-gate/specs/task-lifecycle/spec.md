## ADDED Requirements

### Requirement: Deterministic task intake
Groundwork SHALL classify every submitted prompt in a git repository without a model call. A prompt that names a Jira-style key, or contains an engineering action verb and is not a question, a slash command or a system envelope, SHALL be registered as a task in the repository's task ledger. The ledger SHALL record:
- the task's key, or a generated `GW-<n>` key;
- the mission text;
- the tier (MATERIAL when cloud, infrastructure, data, security, production or deployment signals are present, otherwise STANDARD);
- the risk categories and a per-category checklist of prerequisites and open questions;
- the base commit and the paths already dirty at intake.

For a MATERIAL task it SHALL create the OpenSpec change. A prompt that names a key already in the ledger SHALL receive that task's state instead of creating a new task.

#### Scenario: Jira-style infrastructure request
- **WHEN** the prompt `COR-123: Deploy a GoldenGate VM in GCP.` is submitted in a repository
- **THEN** task `COR-123` is recorded as MATERIAL with cloud, infrastructure, data, cost and deployment risk, an OpenSpec change `cor-123-deploy-goldengate-vm-gcp` exists, and Claude receives the checklist and the steps to plan and request approval

#### Scenario: A question is not a task
- **WHEN** the prompt `how does terraform state locking work?` is submitted
- **THEN** no task is created and no context is added

#### Scenario: A known task is resumed
- **WHEN** a prompt mentions `COR-123` after it was recorded
- **THEN** no second task is created and Claude receives COR-123's state and next action

### Requirement: Plan gate before approval can be requested
`groundwork task request-approval <KEY>` SHALL refuse unless:
- the task's OpenSpec change passes `openspec validate --strict`;
- `tasks.md` has at least one checkbox;
- `proposal.md` or `design.md` has non-empty sections Prerequisites, Risks, Missing Information, Estimate (with a number and the word confidence or uncertainty), Scope (at least one specific, repository-relative path pattern in backticks; `*`, `**`, absolute paths and `..` are refused) and Verification (at least one command in backticks).

On success it SHALL record the plan digest as the approval code and set the task to awaiting approval.

#### Scenario: Incomplete plan
- **WHEN** the plan has no Scope section
- **THEN** the command exits non-zero, names the missing section, and the task stays in planning

#### Scenario: Complete plan
- **WHEN** the plan is complete and valid
- **THEN** the command prints the approval code and the exact `/gw-approve <KEY> <code>` line for the owner

### Requirement: Owner-only approval bound to the plan
An approval SHALL be recorded only from a `UserPromptExpansion` event for the typed `/gw-approve <KEY> <code>` command, and only when the code equals the current plan digest. A change to the plan after approval SHALL void the approval for execution until the owner approves the new digest. Claude SHALL be denied any tool call that invokes, schedules or sends `/gw-approve` or `/gw-cancel`, and any write to the task ledger or to those command files.

#### Scenario: Approval text through an ordinary prompt
- **WHEN** a `UserPromptSubmit` prompt contains `approve COR-123 <code>`
- **THEN** no approval is recorded

#### Scenario: Stale approval code
- **WHEN** the owner types `/gw-approve COR-123 <old code>` after the plan changed
- **THEN** the expansion is blocked with a reason naming the current state and no approval is recorded

#### Scenario: Claude tries to approve
- **WHEN** Claude calls the Skill tool for `gw-approve`, or runs a Bash command containing `gw-approve`
- **THEN** the call is denied

### Requirement: Execution gate
While a MATERIAL task in the repository is in planning or awaiting approval:
- edit tools SHALL be allowed only inside the task's OpenSpec change directory and temporary directories;
- Bash SHALL be allowed only when every command in it is on the read-only allowlist, the OpenSpec CLI, or the Groundwork task CLI;
- mutating MCP tools SHALL be denied.

While approved (the digest unchanged):
- edits SHALL be allowed only within the approved Scope or the plan directory;
- sensitive commands SHALL be allowed only when they match an Approved Operation, and mutating MCP tools only when named there;
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

### Requirement: Evidence capture and scope audit
After each tool call in a repository with an approved MATERIAL task, Groundwork SHALL record:
- each run of a declared verification command, with success or failure and the working-tree fingerprint;
- each foreground review subagent's parsed `REVIEW RESULT`, with the fingerprint;
- each approved sensitive operation's time.

After each Bash, Agent or MCP call, it SHALL report to Claude every changed path outside the allowed set, compared with the intake base commit.

#### Scenario: Out-of-scope change through Bash
- **WHEN** a Bash command creates `notes.txt` outside the approved Scope
- **THEN** Claude is told that `notes.txt` is outside COR-123's scope and must be reverted

### Requirement: Evidence-gated completion
`groundwork task complete <KEY>` SHALL set a MATERIAL task to complete only when all of these hold:
- it is approved and the plan digest is unchanged;
- every task in `tasks.md` is checked;
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
