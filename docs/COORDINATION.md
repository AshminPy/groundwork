# Coordinating several tasks

One main session coordinates; independent tasks run in their own background sessions and worktrees. Everything here
is native Claude Code (2.1.316) plus Groundwork's existing task ledger. Groundwork adds no orchestrator.

## Roles

| Need | Native capability | Groundwork piece |
|---|---|---|
| Accept and track many tasks | The main session | Task ledger: `groundwork task list`, `show <KEY>`; state survives restarts in `~/.claude/groundwork/tasks/` |
| Classify and prioritize | The main session's judgment (tier, risk) | Intake records tier, risk and a checklist per task (`hooks/groundwork_tasks.py` intake) |
| Run independent tasks apart | `claude --bg "<brief>"`, `claude -w <name>` for its own worktree, agent view | One branch and one PR per task, reviewed by the review gate and the `review-check` workflow |
| Respect dependencies | Start a dependent task only after its dependency's result is in | `groundwork task block <KEY> "waits for GW-2"`, cleared with `--clear` when the dependency lands |
| Follow progress | `claude agents --json` (`--all` includes finished sessions), `claude logs <id>`, `claude attach <id>` | `groundwork task show <KEY>`: phase, evidence, scope warnings, notes |
| Return results and evidence | The background session's branch, commits and final report | Verification and review evidence recorded per task, bound to the content fingerprint |
| Ask a human only when needed | Claude Code's permission prompt, shown in agent view as a session waiting for input | Permission tiers in `docs/PERMISSIONS.md` |

## Procedure

1. Record each task in the main session. A ticket key or a MATERIAL request is recorded by intake; otherwise run
   `groundwork task intake "<description>"`.
2. Mark dependencies: `groundwork task block GW-3 "waits for GW-2"`.
3. For each unblocked, independent task, start a background session in its own worktree:
   `claude --bg -w gw-2 "GW-2: <brief with scope, files, acceptance criteria and verification commands>"`.
   Give one task per session, and never two sessions writing the same files.
4. Watch `claude agents --json`. A session waiting on a permission prompt needs the owner; everything else continues
   on its own.
5. When a session finishes, read its branch and report in the main session. Its PR must pass the review check like
   any other.
6. Clear dependents (`groundwork task block GW-3 --clear`) and start them.
7. Unrelated findings go to `groundwork task note <KEY> "<finding>"`, not into the current task.

## Where governed work can run

- Local sessions, background sessions and Remote Control sessions load the user's settings, hooks and permission
  rules, so every Groundwork safeguard applies.
- Claude Projects cloud threads do not load repository hooks or permission rules (code.claude.com/docs/en/claude-projects).
  Use them only for read-only research or drafting, never for changes that need the safeguards.
- `claude --bare` skips hooks, so it is never used for governed work.

## Models

Model choice stays configurable: the owner's settings and each subagent's `model` decide it, and nothing in
Groundwork fixes a coordinator or worker model. A performance-based default waits for the benchmark
(`openspec/changes/harden-autonomy-evidence-review/benchmark.md`).
