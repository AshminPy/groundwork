## Why

Groundwork governs one interactive Claude Code session well, but it cannot take a request, run it through a controlled workflow on its own, check the result with real commands and report a status that can be trusted. The owner asked for a local orchestration harness (Phase 1 of the "deterministic multi-agent orchestration" brief, 2026-10-24): a request goes in, a typed workflow runs `claude -p` workers on the existing subscription login, deterministic checks decide the outcome, and recoverable failures get a bounded repair.

Phase 0 discovery (2026-10-24, on origin/main 086216d):
- `claude -p` started from Python works on the claude.ai Max login (Claude Code 2.1.310, `claude-haiku-5-5`, 11.7 s, no API key, no `--bare`).
- Existing pieces to reuse: the deterministic classifier and task ledger (`hooks/groundwork_tasks.py`), the task gate and protected-push hooks (they already apply inside `claude -p` children), the least-privilege worker flags from `scripts/groundwork_routines.py`, and the `groundwork` CLI pass-through pattern.
- Missing: workflow state, session tracking, structured worker results, failure classification, a validate-and-repair loop.
- The draft vision roadmap (PR #59) lists a custom runtime, a database and third-party dependencies as non-goals. The owner decided (2026-10-24) to build the orchestrator as an **opt-in add-on** with its own virtual environment, leaving core Groundwork stdlib-only and unchanged.

## What Changes

- New opt-in package `orchestrator/` (`groundwork_orchestrator`), installed only by `install.sh --with-orchestrator` into its own venv with pinned `langgraph` and `langgraph-checkpoint-sqlite`.
- `groundwork query "<request>"` submits a task; `groundwork orch list|show|approve|reject|resume` operates on it. Both are pure pass-throughs, like `groundwork task`.
- A LangGraph workflow owns state: intake → classify → plan → approval (only for writes) → execute → validate → bounded repair (max 2) → finalize. Checkpoints in SQLite; resumable after a crash.
- Four categories: QUESTION, TROUBLESHOOTING, PROJECT, DOCUMENTATION. Deterministic rules first; a Haiku call with `--json-schema` only for ambiguous requests; output that fails schema validation blocks the task.
- A `claude -p` adapter: argv lists, prompt on stdin, API-key variables removed, subscription preflight, chosen session id, JSON result parsing, auth/quota/model/permission/malformed/timeout classification, process-group termination.
- Model and effort routing from a JSON policy file, each choice recorded with its reason.
- Deterministic validation: owner-declared check commands, read-only workspace integrity (no file changed), write-scope check for writes, cited-source existence for answers. Final status VERIFIED / PARTIALLY_VERIFIED / UNVERIFIED / FAILED / BLOCKED.
- Side effects are idempotent across resume: every worker call and worktree creation is an operation with a durable id; a finished operation is never repeated, an interrupted write blocks the task instead of running twice.
- Writes happen only in an isolated git worktree on a `gw/<task>` branch, only after `groundwork orch approve`. The orchestrator never commits, pushes, merges or releases.

## Capabilities

### New Capabilities
- `orchestrator`: request intake, classification, workflow state, worker execution, validation, repair and recovery for the opt-in local orchestrator.

### Modified Capabilities
- (none — core hooks, rules and the task ledger are unchanged; `groundwork_cli.py` gains two pass-through subcommands and `install.sh` an opt-in flag)

## Impact

- New: `orchestrator/` (package, policy file, pinned requirements, tests, README).
- Changed: `scripts/groundwork_cli.py` (pass-through), `install.sh` / `uninstall.sh` (opt-in install and removal), `tests/test_groundwork_cli.py`, `.gitignore`, `CHANGELOG.md`.
- Not touched, to avoid conflicts with PR #61 (2.5.0 security work): `hooks/groundwork_task_gate.py`, `hooks/groundwork_tasks.py`, `hooks/block_protected_push.py`, `scripts/groundwork_routines.py`, `scripts/merge_settings.py`.
- Out of scope for Phase 1 (later phases): parallel workers, task decomposition, memory, evaluation fixtures, dashboard.
