## ADDED Requirements

### Requirement: Automatic task intake
Groundwork SHALL classify every submitted prompt in a git repository without a model call. It SHALL skip questions, slash commands and system envelopes. It SHALL record a task in the repository's task ledger when the prompt names a Jira-style key and asks for work, or when it is MATERIAL engineering work. The ledger SHALL record:
- the key, or a generated `GW-<n>` key;
- the mission text;
- the tier: MATERIAL when cloud, infrastructure, data, security, production or deployment signals are present, otherwise STANDARD;
- the risk categories and a per-category intake checklist;
- the base commit.

For a MATERIAL task, Groundwork SHALL create the native OpenSpec change and tell Claude to plan and implement it the native way.

The ticket a prompt is for SHALL be:
- the first key not yet in the ledger that starts the prompt or heads a clause;
- otherwise the first open key. An open STANDARD task SHALL become MATERIAL, with its own OpenSpec change, when the prompt carries MATERIAL signals and an action verb;
- otherwise a closed key that starts the prompt or heads a clause, which starts a fresh task only when the prompt asks for work. The old record is kept;
- otherwise the first new key anywhere;
- otherwise the first key.

A keyless prompt while a MATERIAL task is open SHALL be treated as more of that task. STANDARD work without a key SHALL NOT be recorded.

#### Scenario: Jira-style infrastructure request
- **WHEN** the prompt `COR-123: Deploy a GoldenGate VM in GCP.` is submitted in a repository
- **THEN** task `COR-123` is recorded as MATERIAL with cloud, infrastructure, data, cost and deployment risk, the OpenSpec change `cor-123-deploy-goldengate-vm-gcp` exists, and Claude is told to plan it with `/opsx:propose` and implement it with `/opsx:apply`

#### Scenario: A question is not a task
- **WHEN** the prompt `how does terraform state locking work?` is submitted
- **THEN** no task is created and no context is added

#### Scenario: A known task is resumed
- **WHEN** a prompt mentions `COR-123` while it is open
- **THEN** no second task is created and Claude receives COR-123's phase, progress, evidence and next action

#### Scenario: The owner revises a task without a key
- **WHEN** COR-123 is open and the owner sends a keyless message changing the machine type
- **THEN** no new task is created and Claude receives COR-123's state

### Requirement: Native OpenSpec is the plan
Groundwork SHALL read the task's OpenSpec change as it is on every check, and SHALL NOT keep a separate copy of the plan. It SHALL take:
- progress from the `tasks.md` checkboxes;
- the verification commands from a `## Verification` section in `design.md`, `proposal.md` or `tasks.md`. Each command is one simple command in backticks.

It SHALL derive the phase:
- planning: no change or no tasks;
- implementing: unchecked tasks remain;
- verifying: all tasks checked;
- archived: the change is under `openspec/changes/archive/`.

Revising any artifact SHALL never void evidence or require approval. A change archived natively SHALL still be found.

#### Scenario: The plan is revised mid-implementation
- **WHEN** the owner changes the design and adds a task after a verification passed
- **THEN** the verification still counts, the task list shows the new task, and the phase is implementing

#### Scenario: An archived change
- **WHEN** the change has been moved to `openspec/changes/archive/<date>-<name>/`
- **THEN** `groundwork task show` reads the archived artifacts

### Requirement: Ordinary work flows; sensitive actions need authorization
Groundwork SHALL NOT prompt for or block ordinary development. That covers edits, builds, tests, commits, ordinary pushes, deletes inside the working directory, read-only cloud and cluster commands, and OpenSpec commands.

Groundwork SHALL return Claude Code's `ask` permission decision, in every repository and directory, for:
- cloud, cluster, Terraform and Helm mutations;
- database clients and remote execution;
- data-sending HTTP requests;
- recursive deletes of, or outside, the working directory;
- forced or deleting pushes, `git reset --hard`, `git clean -f`, branch force-delete, stash drop, and discarding uncommitted changes;
- credential access, by command or by file;
- elevated privileges;
- commands it cannot check, including PowerShell;
- edits to Claude Code settings or Groundwork's hooks.

It SHALL check commands inside wrappers, nested shells, scripts, command substitutions and here-documents. A file tool writing the task ledger SHALL be denied. `GROUNDWORK_TASK_GATE=off` in the hook environment SHALL turn the hook off.

#### Scenario: Ordinary implementation
- **WHEN** a MATERIAL task is open and Claude edits code, runs the tests and commits
- **THEN** no prompt is shown

#### Scenario: Cloud mutation
- **WHEN** Claude runs `gcloud compute instances create gg-vm-1`
- **THEN** the user's permission prompt is shown, with a reason naming a gcloud mutation

#### Scenario: Destructive Git
- **WHEN** Claude runs `git push --force origin feature`
- **THEN** the user's permission prompt is shown

### Requirement: Evidence capture
Groundwork SHALL record:
- each foreground run of a declared verification command, with its outcome and a fingerprint of the code. The fingerprint SHALL exclude `openspec/` and generated caches;
- the result of each foreground review subagent: its `REVIEW RESULT` verdict and MUST FIX count;
- each sensitive operation that ran.

A verification SHALL count only when run exactly as declared: not piped, without extra arguments, followed only by `&&`. The latest run on the current fingerprint after the last sensitive operation SHALL decide whether it passed.

#### Scenario: Piped verification
- **WHEN** Claude runs the declared verification piped into `tail`
- **THEN** it is not recorded and Claude is told to run it as declared

#### Scenario: Code change after verification
- **WHEN** code changes after a passing verification
- **THEN** the verification is stale until it runs again

### Requirement: Evidence-based completion
`groundwork task complete <KEY>` SHALL complete a MATERIAL task only when:
- every task in `tasks.md` is checked;
- at least one valid verification is declared;
- every declared verification passed on the current code after the last sensitive operation;
- the latest parsed review on the current code reports zero MUST FIX.

It SHALL list what is missing otherwise. A STANDARD task SHALL complete on request. After a successful native archive of the change (`openspec archive`, or the `/opsx:archive` move), Groundwork SHALL attempt completion and report the result.

#### Scenario: Missing review
- **WHEN** completion is requested with every verification passed but no review
- **THEN** it is refused and the missing review is named

#### Scenario: Native archive with evidence in place
- **WHEN** every task is checked, the verification passed and the review approved, and the change is archived with `/opsx:archive`
- **THEN** the task is complete

### Requirement: Task continuity
Open tasks SHALL survive new sessions. The SessionStart snapshot SHALL list each open task as its key, phase, progress, evidence and next action. `groundwork task list|show` SHALL show the same. The ledger SHALL live under `$CLAUDE_CONFIG_DIR/groundwork/tasks/<repo>-<hash>/`, outside the repository, so projects and config directories never share tasks.

#### Scenario: Fresh session
- **WHEN** a new session starts in a repository with an open task
- **THEN** the snapshot shows the task's phase, progress, evidence and next action

#### Scenario: Two repositories
- **WHEN** the same key is used in two repositories
- **THEN** each repository has its own ledger record
