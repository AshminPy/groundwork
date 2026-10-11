## Why

Phase 7 of the owner's programme allows continuity work only for a reproducible gap. The gap, reproduced on this repository: `git worktree list` showed eight checkouts, two of them holding work that existed only on this machine (an uncommitted file, and a commit on a branch with no upstream). The SessionStart snapshot of a fresh session in the main checkout reported one branch, one HEAD, and `0 modified` — nothing about the others. A new session therefore could not know that unpushed work existed, and in an ephemeral environment that work is lost with the machine.

## What Changes

- The SessionStart snapshot gains one section: other worktrees of the same repository with uncommitted changes, commits the upstream lacks, or no upstream (work not known to be on a remote), with branch, short HEAD, uncommitted counts and upstream state. Clean, fully pushed worktrees are counted, not listed; worktrees with a missing directory and worktrees git could not read are counted too (a failure is never reported as clean). Nothing is printed when there is nothing to report.
- Bounded: at most 12 worktrees examined (one `git status -b` each), at most 3 listed, at most 700 characters, and one deadline for the whole section — 3 seconds from its start or 8 seconds from the start of the hook (the shipped hook timeout is 10 s), checked before every git call, with each call's timeout clamped to the time left. Siblings are read with `GIT_OPTIONAL_LOCKS=0` so the hook does not rewrite their indexes. Any failure prints nothing.

Not in this change: any stored state, any new file, any model-written memory, any change to the investigation-continuity file, any network access. The other candidate ideas under "SmartMemory" are not needed: saved sessions and the investigation file already exist, and no other gap was reproduced.

## Capabilities

### New Capabilities
- `session-snapshot`: the SessionStart snapshot's worktree section (the existing snapshot behaviour is documented in `docs/ARCHITECTURE.md`; this change specifies only what it adds).

## Impact

`hooks/groundwork_session_snapshot.py` (one helper extracted, the section added, one line in `build_snapshot`, `git()` gains a timeout/env/`errors=replace`), `tests/test_hooks.py`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`. No new dependency, no new file at runtime, no change to the hook's output schema. The snapshot stays within its existing 2,500-character cap; in the measured case (two listed, six counted) the new section was about 340 characters and the whole snapshot about 2,400.
