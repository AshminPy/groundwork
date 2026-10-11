## 1. Implementation
- [x] 1.1 `branch_state()` extracted from `git_facts()` (output of the git line unchanged)
- [x] 1.2 `worktree_facts()` and its limits; one line in `build_snapshot()`
- [x] 1.3 Docs: ARCHITECTURE, CHANGELOG

## 2. Verification
- [x] 2.1 Tests against real git repositories with a bare origin (dirty, ahead, no upstream, detached, missing, locked-and-missing, unreadable and not-examined siblings, caps, exhausted and clamped budget, non-git, bare repository, `--separate-git-dir`, submodule session and submodule owner checkout, a git that rejects `worktree list -z` and one that rejects `--absolute-git-dir` (both simulated with a shim; the version that introduced either option was not verified), a non-UTF-8 path, an empty `.git` directory, a hostile path, section isolation)
- [x] 2.2 Mutation checks: 28 mutants, each removing one safety or bounding clause of the worktree section (`tests/mutation/mutate_snapshot_worktrees.py`); all 28 caught by the tests
- [x] 2.3 Run against this repository's real worktrees (listed the two with local-only work; the six pushed ones counted)
- [x] 2.4 Full suite and `openspec validate --all --strict` against the main baseline
- [x] 2.5 Independent fresh-context review (3 MUST FIX: unbounded budget, failures shown as clean, submodule listing itself); all fixed
- [x] 2.6 Confirmation review (1 MUST FIX: a `--separate-git-dir` session counted its own checkout as unreadable; nice-to-haves: submodule owner checkout, non-UTF-8 paths, left-clipped paths); all fixed
- [x] 2.7 Fresh confirmation review of the fixes from 2.6 (1 MUST FIX: the section could push the verification commands and the closing instruction out of the 2,500-character cap; fixed by building it last with only the room left. Nice-to-haves fixed: empty `.git` directory under a `:` path, deadline-killed call counted as unreadable, forged entry without `-z`, prune advice, overflow line outside the budget. Not changed: left-clipped branch names, linked worktree of a separate-git-dir repository; both documented)
- [ ] 2.8 Fresh confirmation review of the fixes from 2.7
