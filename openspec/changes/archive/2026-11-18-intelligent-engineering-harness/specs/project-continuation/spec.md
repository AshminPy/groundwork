## Purpose
Lets a fresh Claude Code session reconstruct an existing project's real state from repository-native evidence — git, OpenSpec, docs, tests, CI, current implementation — so "continue this project" works without the previous chat, and so a deterministic snapshot is available at every session start.

## ADDED Requirements

### Requirement: Deterministic session snapshot
A SessionStart hook SHALL emit a deterministic snapshot built only from repository state: git branch, HEAD commit, ahead/behind of upstream, counts of modified and untracked files, the most recent commits, OpenSpec active changes with task progress and whether the review gate applies, project signal files present, and verification commands discovered in the repository.

#### Scenario: Git repository with OpenSpec changes
- **WHEN** a session starts in a git repository that has `openspec/changes/<name>/tasks.md` files
- **THEN** the snapshot names each active change with `<checked>/<total>` tasks and marks a fully-checked, uncommitted change as "review gate applies"

#### Scenario: Not a git repository and no OpenSpec
- **WHEN** the working directory is neither a git repository nor contains `openspec/`
- **THEN** the hook emits nothing and exits 0

#### Scenario: Snapshot size and safety
- **WHEN** the repository is large or git is slow
- **THEN** the snapshot is capped at 2,500 characters, every git call has a ≤ 3 s timeout, no network call is made, and any error results in no output and exit 0

### Requirement: Continuation procedure reconstructs state before changing anything
When asked to continue an existing project, Claude SHALL reconstruct the current state from repository evidence in this order — snapshot, `git status`/`log`/`diff`, OpenSpec artifacts (`openspec list`/`status`), README/CLAUDE.md/docs, tests and CI, current implementation, then any ECC session file — and SHALL produce a DONE / PARTIAL / MISSING / BLOCKED / UNVERIFIED table before making changes.

#### Scenario: Continue this project
- **WHEN** the user says "continue this project" (or equivalent) in a fresh session
- **THEN** Claude presents the state table with evidence per row, names the next action, and proceeds without asking for the previous chat

#### Scenario: Documentation contradicts code
- **WHEN** a doc, session file, or memory claims a state that current code or runtime evidence contradicts
- **THEN** Claude reports the mismatch and acts on the code/runtime evidence

### Requirement: No custom persistence platform
The harness SHALL keep continuation state repository-native and reconstructable; it SHALL NOT introduce a database, daemon, vector store, or separate memory service.

#### Scenario: Continuation record
- **WHEN** work stops mid-task
- **THEN** the remaining work is visible in OpenSpec `tasks.md` (MATERIAL) or the branch/commit state (STANDARD); no Groundwork-specific state file is required
