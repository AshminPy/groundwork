## 1. Implementation
- [x] 1.1 `branch_state()` extracted from `git_facts()` (output of the git line unchanged)
- [x] 1.2 `worktree_facts()` and its limits; one line in `build_snapshot()`
- [x] 1.3 Docs: ARCHITECTURE, CHANGELOG

## 2. Verification
- [x] 2.1 Tests against real git repositories with a bare origin (dirty, ahead, no upstream, detached, missing directory, cap, exhausted budget, non-git)
- [x] 2.2 Six mutation checks, all caught
- [x] 2.3 Run against this repository's real worktrees (listed the two with local-only work; the six pushed ones counted)
- [x] 2.4 Full suite and `openspec validate --all --strict` against the main baseline
- [ ] 2.5 Independent fresh-context review; fix MUST FIX
