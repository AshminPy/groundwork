## Context

Phase 1 of the orchestration brief: one complete, single-worker workflow before any parallelism. Everything below is grounded in Phase 0 evidence (see proposal.md) and the Claude Code 2.1.310 CLI (`claude --help`, https://code.claude.com/docs/en/headless).

## Goals / Non-Goals

**Goals**: a request becomes a typed, persisted task; a worker runs on the subscription login with the least tools its role needs; deterministic checks — never the worker's own claim — decide the status; failures that a worker cannot fix (auth, quota, permission, timeout) stop instead of looping; a crash never repeats a side effect.

**Non-Goals (Phase 1)**: more than one concurrent worker, task decomposition, memory, evaluation fixtures, dashboard, OpenSpec artifact authoring by workers, commits/pushes/merges, any change to core hooks or the task ledger.

## Architecture

```
groundwork query "<request>"  ──►  scripts/groundwork_cli.py (pass-through)
                                     │  ~/.claude/groundwork/orchestrator/venv/bin/python -m groundwork_orchestrator
                                     ▼
 LangGraph StateGraph (thread_id = task id, SqliteSaver checkpoints.db)
   intake ─► classify ─► plan ─► approve? ─► execute ─► validate ─► finalize
                          │       (interrupt)    ▲          │
                          │                      └─ repair ◄┘  (max 2, code defects only)
   cross-cutting: store.py (state.db: tasks, transitions, operations, sessions)
                  claude_adapter.py (one `claude -p` per worker call)
                  routing.json (role → model, effort, tools)
                  events.jsonl (orchestrator telemetry)
                  groundwork_tasks.intake()/record_verification() (existing ledger, imported)
```

Task states: `CREATED → CLASSIFIED → PLANNED → [WAITING_APPROVAL] → RUNNING → VALIDATING → [REPAIRING → VALIDATING]* → PASSED | FAILED | BLOCKED | CANCELLED`. Every change is a row in `transitions` with a reason. Final evidence status is separate: `VERIFIED | PARTIALLY_VERIFIED | UNVERIFIED | FAILED | BLOCKED`.

Workflows:
| Category | Worker tools | Writes | Deterministic validation |
|---|---|---|---|
| QUESTION | Read, Grep, Glob | never | workspace unchanged; every cited path exists |
| DOCUMENTATION | Read, Grep, Glob (+Edit, Write in worktree with `--allow-write`) | approval | cited paths exist; checks; write scope |
| TROUBLESHOOTING | Read, Grep, Glob (+Edit, Write in worktree with `--allow-write`) | approval | checks run before (symptom) and after; workspace unchanged when read-only |
| PROJECT | Read, Grep, Glob, Edit, Write, Bash limited to the declared checks | always approval | checks; write scope; non-empty diff |

## Architecture-quality answers (rules/architecture-quality.md §2)

- **Likely to change**: model names and efforts per role → `routing.json`, not code. Tools per role stay in code on purpose: they are a security control, not a tuning knob. Workspace allowlist → `config.json`. Check commands → per task (`--check`).
- **Another instance/provider/model**: a new role or model is a policy entry; the adapter is the only place that knows the `claude` CLI, so a future SDK transport replaces one module.
- **Automated manual steps**: subscription preflight, worktree creation, check runs, abandoned-session reconciliation on resume.
- **Dependency unavailable**: `claude` missing/logged out/on another provider → BLOCKED before any worker; quota → BLOCKED (resumable), never an API fallback; LangGraph missing → the CLI says the add-on is not installed; core Groundwork is unaffected.
- **Observe/troubleshoot**: `groundwork orch show <id>` prints state history, sessions (pid, session id, model, effort, duration, exit code, estimated cost), operations and check output; `events.jsonl` for later dashboards.
- **Testing**: unit tests with a stub `claude` binary for every failure class; graph tests across real process restarts; live acceptance tests on the real CLI, labelled as such.
- **Deploy/rollback**: `install.sh --with-orchestrator` creates the venv and copies the package; `uninstall.sh` removes it; removing the add-on leaves core Groundwork as before.
- **Security boundary**: workspaces must be on the allowlist; read-only tools by default; writes only in a worktree after explicit approval; no `--bare`, no permission-bypass mode, `--permission-prompts none`; user hooks (task gate, protected push) stay active in workers; prompt text and repository content are framed as untrusted data, and the tool allowlist — not the prompt — is the control.
- **Scaling/cost**: one worker at a time in Phase 1; Haiku for ambiguous classification only; deterministic rules first. `total_cost_usd` is Claude Code's client-side estimate and is labelled as such.

## Decisions

DECISION            LangGraph `StateGraph` + `SqliteSaver` owns workflow state; an orchestrator-owned `operations` table makes side effects idempotent.
EVIDENCE            Probe in a scratch venv (langgraph 1.2.17, langgraph-checkpoint-sqlite 3.1.2): an `interrupt()` survived a process exit; after an exception inside node `b`, a new process resumed with `next=('b',)` and re-ran only `b`. So a node that crashes mid-way runs again on resume.
WHY                 The owner's brief names LangGraph; checkpoint/interrupt/resume would otherwise be hand-written. Owner chose the opt-in add-on (2026-10-24).
TRADEOFFS           First third-party dependency in the project (isolated in its own venv); two SQLite files.
VALIDATION METHOD   Graph tests that kill the process at each side-effect point and resume in a new process; assert one worker call and one worktree.
UNCERTAINTY         LangGraph checkpoint format across major upgrades — versions are pinned.

DECISION            Worker transport is `claude -p --output-format json` with a caller-chosen `--session-id`; repair resumes the same session with `--resume`.
EVIDENCE            `claude --help` (2.1.310) lists `--session-id`, `--resume`, `--effort low..max`, `--json-schema`, `--permission-prompts`; live call returned `session_id`, `structured_output` support, `permission_denials`, `total_cost_usd`. Headless docs: `--bare` "never reads OAuth credentials", so it is never used.
WHY                 Supported, subscription-backed, already used by routines/copilot. The Agent SDK is not needed for Phase 1.
TRADEOFFS           No streaming progress in Phase 1 (JSON result at the end).
VALIDATION METHOD   Stub-binary unit tests for each failure class; live acceptance run.
UNCERTAINTY         Exact wording of quota errors is not documented — matched by documented error categories (`rate_limit`, `billing_error`) plus common phrases; an unmatched failure is `process`, which also never triggers a code repair.

DECISION            Reuse the existing task ledger for intake only: the orchestrator calls `groundwork_tasks.intake()` once per task.
EVIDENCE            `intake()` treats a keyless prompt as "existing" while a MATERIAL task is open in the same repository (`hooks/groundwork_tasks.py`); the task gate's only switch is all-or-nothing (`GROUNDWORK_TASK_GATE=off`), which would also disable sensitive-action checks.
WHY                 No second task system; no weakening of the gate; no edit to files PR #61 changes.
TRADEOFFS           `record_verification()` is not used in Phase 1: write checks run in a worktree, whose code fingerprint differs from the ledger root's, so recording them there would be misleading evidence.
VALIDATION METHOD   Test with the real module and a temp `CLAUDE_CONFIG_DIR`; live scenarios B and C.
UNCERTAINTY         **Live finding (2026-10-25):** the intake hook also runs inside each worker session. A worktree is its own repository root with no open task, so a worker prompt classified as MATERIAL creates a separate ledger task and an OpenSpec change inside the worktree. Mitigation in Phase 1: validation reports files the worker did not account for and the task can then be at most PARTIALLY_VERIFIED. Proper fix (follow-up, after PR #61): an intake-only switch in the task gate that the orchestrator sets for workers, with every PreToolUse check unchanged.

## Risks / Trade-offs

- [!] Billing pool: Max plans include monthly API credits that also cover `claude -p` (support article, 2026-10-07 update); the CLI does not show which pool a call uses. Owner approved live use on the personal Max login.
- Hooks in `~/.claude` run in every worker (no `--bare`) — intended; it also means a slow or failing user hook slows workers.
- A worker can still read files the read tools reach inside its cwd; the cwd is the allowlisted workspace or the task's worktree.
