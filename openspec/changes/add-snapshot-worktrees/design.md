## Context

Verified on this host (git 2.43.0): `git worktree list --porcelain` prints blocks of `worktree <path>`, `HEAD <sha>`, `branch refs/heads/<name>` (or `detached`, `bare`, `prunable`), separated by blank lines. The per-checkout facts the snapshot already reads (`status --porcelain`, `rev-list --left-right --count @{upstream}...HEAD`) work unchanged inside any worktree.

## Decisions

DECISION            Surface only worktrees that hold work existing only on this machine; count the rest.
EVIDENCE            Measured on this repository: listing all eight siblings pushed the snapshot to its 2,500-character cap and cut off the verification-command line; listing only the two with local-only work (six pushed ones counted) was 341 characters, the whole snapshot 2,349, and everything else was kept.
WHY                 The value is "this work can be lost"; a clean, fully pushed worktree's work is on the remote and findable through branches and PRs. Alternatives that lost: list everything (noise, truncation); persist a model-written list of worktrees (a second source of truth that goes stale, which the repository state does not).
TRADEOFFS           A fresh session sees nothing about pushed siblings beyond a count; a branch whose upstream was deleted counts as having no upstream (VERIFIED: `git rev-list @{upstream}...HEAD` exits 128 after the remote branch is pruned), which over-reports rather than hides.
VALIDATION METHOD   Real git repositories with a bare origin in tests (dirty, ahead, no-upstream, detached, missing directory, cap, exhausted budget), six mutation checks, a run against this repository's real worktrees.
UNCERTAINTY         Locked or slow worktrees on network filesystems: the 4-second section budget and the 3-second per-call timeout bound the cost, but this is not tested on such a filesystem (RUNTIME VALIDATION REQUIRED there).

## Architecture-quality answers

- **What changes / what is configuration?** The limits are module constants beside the existing ones; nothing is configurable because a larger listing would crowd out the other facts.
- **Dependency unavailable?** `git` missing or failing: nothing printed for the section. A deleted worktree directory: counted as missing. The rest of the snapshot is unaffected (fail-open, as before).
- **Observability?** The section is the observation; `git worktree list` is named in the line for the full picture.
- **Security boundary?** Branch names and paths are attacker-controlled in a hostile repository: they pass through the existing `clip()` (control characters stripped, per-field cap) and sit inside the existing data envelope.
- **Cost?** At most 12 worktrees x 2 git calls, time-boxed to 4 seconds in total; typically 0 to 2 worktrees exist.
