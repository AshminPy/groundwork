# session-snapshot Specification

## Purpose
The SessionStart snapshot gives a fresh session deterministic facts about the repository it starts in. This change covers its worktree section: work in other checkouts of the same repository that a fresh session cannot see from this one.

## ADDED Requirements

### Requirement: Report other worktrees that may hold unpushed work
The snapshot SHALL list each other worktree of the repository that has uncommitted changes, commits its upstream lacks, or no upstream (or whose upstream branch is gone), showing its path, branch (or "detached HEAD"), short HEAD, uncommitted counts and upstream state, and SHALL count (not list) the clean worktrees that are level with their upstream, the worktrees whose directory is missing, and the worktrees git could not read. A failure to read a worktree SHALL NOT be reported as clean or pushed. It SHALL print nothing when every other worktree is clean and pushed, and SHALL never list or count the checkout the session started in, including when that checkout is a submodule or uses a separate git directory.

#### Scenario: Unpushed and uncommitted siblings are listed
- **WHEN** a sibling worktree has an untracked file, another has one unpushed commit, another has a branch with no upstream and another a branch whose upstream was deleted
- **THEN** each appears with its branch, short HEAD and state, and the summary line counts them

#### Scenario: Pushed siblings are not listed
- **WHEN** every other worktree is clean and level with its upstream
- **THEN** the snapshot has no worktree section

#### Scenario: A sibling git cannot read
- **WHEN** a sibling's `.git` file points nowhere
- **THEN** the summary counts it as one whose state git could not read, and the clean-and-pushed count does not include it

#### Scenario: A submodule session
- **WHEN** the session starts in a submodule that has a linked worktree
- **THEN** the linked worktree is reported and the submodule's own git directory is not

### Requirement: Bounded, data-framed and fail-open
The section SHALL examine at most 12 worktrees, list at most 3 within a 700-character budget (counting the overflow), start every git call (the listing included) before one deadline — 3 seconds after the section starts or 8 seconds after the hook starts, whichever is earlier — with each call's timeout clamped to the time left, report worktrees it did not examine, read siblings without taking optional locks (so their indexes are not rewritten), pass every path and branch name through the snapshot's control-character stripping and length caps, read the listing NUL-separated when git supports it, sit inside the snapshot's data envelope, and print nothing when git fails or the directory is not a repository.

#### Scenario: More than three with unpushed work
- **WHEN** nine other worktrees hold unpushed work
- **THEN** at most three are listed and a line says how many more exist

#### Scenario: Slow git
- **WHEN** every git call takes 0.4 s and the section budget is 1.3 s
- **THEN** the section ends within about 0.6 s of its budget and the remaining worktrees are reported as not examined

#### Scenario: Hook deadline already passed
- **WHEN** the hook has already run for longer than its deadline
- **THEN** the section makes no git call and prints nothing

#### Scenario: Long branch name and hostile path
- **WHEN** a sibling's branch name is 100 characters long, or its path contains newlines and text shaped like another listing entry
- **THEN** the branch is clipped to 40 characters with an ellipsis and no forged entry appears
