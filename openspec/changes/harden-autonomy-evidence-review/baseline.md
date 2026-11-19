# Phase 0 baseline (2026-11-18, base `origin/main` 9f551a0)

States: IMPLEMENTED · PARTIAL · MISSING · UNVERIFIED. Evidence is a repository path, a command, or an official page.

## Environment
- `claude doctor` (Claude Code 2.1.316): no installation issues. Managed settings are not applicable on a Max plan, so there is no managed-policy layer.
- `claude auto-mode config`: built-in defaults only: 16 allow, 72 soft_deny and 1 hard_deny rules, with no custom environment. The default allow list includes "Git Push Destination", which treats a push to any branch of the session's repo, including the default branch, as ordinary. Groundwork's push hook is therefore the only local control on protected-branch pushes in auto mode.
- User settings: `defaultMode: acceptEdits`; allow includes bare `Bash`; 90 ask rules; 42 deny rules. Auto mode drops broad allow rules such as bare `Bash` (code.claude.com/docs/en/auto-mode-config). Read deny rules cover the Read tool and, best effort, Grep and Glob. A shell `cat` of a secret file is not covered by them (code.claude.com/docs/en/permissions).

## Open PRs that overlap
- #63 (draft, docs only, `openspec/changes/core-evidence-continuity/`): plans a citation check. This change implements that check. #63's other items are out of scope.
- #76 (draft, rules text plus a cloud session-start hook): adds a `path:line` citation rule (§2.3) and a stated review bar (§2.6). Rules only, not enforced; this change enforces them. Neither PR is merged.

## Protections
| Area | State | Evidence |
|---|---|---|
| Protected-branch push and force-push block | IMPLEMENTED | `hooks/block_protected_push.py:69` (branches), `:827-832` (force, `+refspec`, `--all`/`--mirror`), deny via `permissionDecision` `:986-989` |
| Installer deny rules | PARTIAL | `scripts/merge_settings.py:87-98`: sudo, `rm -rf /*`, `rm -rf ~*`, chmod 777, force-push, dd, mkfs, diskutil erase. No secret-read or tamper rules. |
| Sensitive-action ask | IMPLEMENTED | `hooks/groundwork_task_gate.py:6-11`, `:1099`, `permissionDecision: ask` |
| Hook tamper protection | PARTIAL | the task gate asks before Groundwork's own settings are edited (`groundwork_task_gate.py:6-11`). No deny rule exists. `disableAllHooks` is not blocked. |
| Hook blocking contract | IMPLEMENTED | all blocking hooks use documented JSON (`decision: block`, `permissionDecision`). None uses exit 2. All fail open on bad input. |
| Stop loop guard | PARTIAL | `groundwork_reply_check.py:168` and `groundwork_brief.py:346` check `stop_hook_active`. `require_material_review.py` relies on Claude Code's 8-block cap (`:49-52`). |
| Independent review | PARTIAL | any Agent/Task/Skill call whose name matches `review` counts (`require_material_review.py:87-92`, `:139-150`). No fresh-context check, no fingerprint or SHA, and an edit after a passing review is not invalidated (`:322-325`). |
| Evidence validation | PARTIAL | `groundwork_reply_check.py:85-108` checks section structure only. Cited paths are never resolved. |
| Scope control | MISSING | intake stores the prompt as `mission` (`groundwork_tasks.py:465`). There are no acceptance criteria, no discoveries record, and no diff-to-goal check. The gate docstring says "no scope gate" (`groundwork_task_gate.py:13`). |
| Task identity and ledger | IMPLEMENTED | keys, states, history and base commit (`groundwork_tasks.py:414-478`) |
| Coordinator / independent sessions | MISSING in Groundwork | native support exists in agent view, `claude --bg` and worktrees (code.claude.com/docs/en/agent-view) |
| Cloud safety parity | MISSING | Claude Projects cloud threads do not load repo hooks or permission rules (code.claude.com/docs/en/claude-projects) |
| Benchmark harness | PARTIAL | `openspec/changes/add-baseline-benchmark` is at 0/19 tasks on main. Runner work sits on the unmerged `release/v3` branch. |

## Quality baseline
- Tests on main, each file run directly: 17 files, 2,580 checks. One routines check fails because it depends on live `claude mcp list` output (`tests/test_groundwork_routines.py:667-672`). That failure is pre-existing.
- Specs: `openspec validate --all --strict` passed 18 of 20 on main. Two specs had placeholder Purpose lines.
- Telemetry (2026-09-29 to 2026-11-18, 2,081 turns): 43% of turns declare no playbook. Validation is declared "verified" on 15% of turns, "partial" on 33%, and "not verified" on 11%.
- Task ledger: 25 open tasks, 0 complete. About half come from false intakes.
- Measured with a real benchmark (completion, accuracy, false blocks, latency, tokens): UNVERIFIED. No benchmark has run. It needs the benchmark runner and an owner-approved run budget.
