## Why

Phase 7 of the owner's programme allows continuity work only for a reproducible gap. The gap, reproduced on this repository: `git worktree list` showed eight checkouts, two of them holding work that existed only on this machine (an uncommitted file, and a commit on a branch with no upstream). The SessionStart snapshot of a fresh session in the main checkout reported one branch, one HEAD, and `0 modified` — nothing about the others. A new session therefore could not know that unpushed work existed, and in an ephemeral environment that work is lost with the machine.

## What Changes

- The SessionStart snapshot gains one section: other worktrees of the same repository that hold work existing only on this machine (uncommitted changes, commits the upstream lacks, or no upstream), with branch, short HEAD, uncommitted counts and upstream state. Clean, fully pushed worktrees are counted, not listed. Nothing is printed when there is nothing to report.
- Bounded: at most 12 worktrees examined, at most 4 listed, a 4-second budget for the section; every git call keeps the existing 3-second timeout; any failure prints nothing.

Not in this change: any stored state, any new file, any model-written memory, any change to the investigation-continuity file, any network access. The other candidate ideas under "SmartMemory" are not needed: saved sessions and the investigation file already exist, and no other gap was reproduced.

## Capabilities

### New Capabilities
- `session-snapshot`: the SessionStart snapshot's worktree section (the existing snapshot behaviour is documented in `docs/ARCHITECTURE.md`; this change specifies only what it adds).

## Impact

`hooks/groundwork_session_snapshot.py` (one helper extracted, one function added, one line in `build_snapshot`), `tests/test_hooks.py`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`. No new dependency, no new file at runtime, no change to the hook's output schema. The snapshot stays within its existing 2,500-character cap; in the measured case (two listed, six counted) the new section was 341 characters and the whole snapshot 2,349.
