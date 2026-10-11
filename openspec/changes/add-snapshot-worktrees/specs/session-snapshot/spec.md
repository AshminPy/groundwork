# session-snapshot Specification

## Purpose
The SessionStart snapshot gives a fresh session deterministic facts about the repository it starts in. This change covers its worktree section: work in other checkouts of the same repository that a fresh session cannot see from this one.

## ADDED Requirements

### Requirement: Report other worktrees that hold work only on this machine
The snapshot SHALL list each other worktree of the repository that has uncommitted changes, commits its upstream lacks, or no upstream, showing its path, branch (or "detached HEAD"), short HEAD, uncommitted counts and upstream state, and SHALL count (not list) the clean worktrees that are fully pushed and the worktrees whose directory is missing. It SHALL print nothing when every other worktree is clean and pushed, and SHALL never list the checkout the session started in.

#### Scenario: Unpushed and uncommitted siblings are listed
- **WHEN** a sibling worktree has an untracked file, another has one unpushed commit, and another has a branch with no upstream
- **THEN** each appears with its branch, short HEAD and state, and the summary line counts them

#### Scenario: Pushed siblings are not listed
- **WHEN** every other worktree is clean and level with its upstream
- **THEN** the snapshot has no worktree section

### Requirement: Bounded, data-framed and fail-open
The section SHALL examine at most 12 worktrees and list at most 4 (counting the overflow), SHALL stop examining when its 4-second budget is exhausted (reporting how many were not examined), SHALL pass every path and branch name through the snapshot's control-character stripping and length caps, SHALL sit inside the snapshot's data envelope, and SHALL print nothing when git fails or the directory is not a repository.

#### Scenario: More than four with local-only work
- **WHEN** nine other worktrees hold unpushed work
- **THEN** four are listed and a line says how many more exist

#### Scenario: Budget exhausted
- **WHEN** the time budget is already spent
- **THEN** no worktree is examined and the summary reports them as not examined

#### Scenario: Long branch name
- **WHEN** a sibling's branch name is 100 characters long
- **THEN** it is clipped to 60 characters with an ellipsis
