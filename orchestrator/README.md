# Groundwork orchestrator (opt-in add-on, Phase 1)

## Purpose

Turn one request into a controlled workflow. Claude Code workers do the reasoning, and deterministic checks decide the result. A worker saying "done" counts for nothing.

```bash
groundwork query "Why does check.py fail? Find the root cause and fix it." --check "python3 check.py" --allow-write
```

This is an **opt-in add-on**. Core Groundwork stays standard-library only and works the same without it.

## Architecture

```
groundwork query ─► groundwork_cli.py (pass-through) ─► orchestrator venv: python -m groundwork_orchestrator
  LangGraph (checkpoints.db): intake → classify → plan → gate → execute → validate ⇄ repair (≤2) → finalize
                                                      ▲ approval          any node ─► blocked (owner retries/cancels)
  store.py (state.db): tasks · transitions · operations (idempotency) · sessions      events.jsonl (telemetry)
  claude_adapter.py: one `claude -p` per worker, on your claude.ai subscription login
```

| Module | Job |
|---|---|
| `claude_adapter.py` | Builds the `claude -p` argv, checks the subscription login, removes API-key variables, sends the prompt on stdin, parses the JSON result, sorts failures (auth / quota / model / permission / malformed / timeout / cancelled / process), and kills the whole process group on timeout |
| `classifier.py` | Rule-based QUESTION / TROUBLESHOOTING / PROJECT / DOCUMENTATION. Asks Haiku (no tools, JSON schema) only on a tie |
| `routing.py`, `routing.json` | Picks the model and effort for each role, with a reason |
| `validation.py` | Owner checks (argv, no shell), workspace fingerprint, changed files, protected paths, cited-source existence |
| `workspace.py` | Workspace allowlist, one git worktree per write task, intake into the existing Groundwork task ledger |
| `store.py` | SQLite state. `run_op` keeps a side effect from running twice after a crash |
| `graph.py` | The workflow |
| `cli.py` | `query`, `list`, `show`, `approve`, `reject`, `resume`, `cancel`, `allow`, `doctor` |

## How it works

| Category | Worker tools | Writes | Validated by |
|---|---|---|---|
| QUESTION | Read, Grep, Glob | never | workspace unchanged; every cited file exists; each claim's quote is found at its cited lines (Evidence Engine, below) |
| DOCUMENTATION | read tools (+Edit/Write with `--allow-write`) | worktree, after approval | cited files exist; write scope |
| TROUBLESHOOTING | read tools (+Edit/Write/Bash for your checks with `--allow-write`) | worktree, after approval | checks run before (symptom) and after (fix) |
| PROJECT | read + Edit/Write + Bash for your checks | worktree, after approval | your checks; write scope; non-empty diff |

- **Writes.** They happen only in `~/.claude/groundwork/orchestrator/worktrees/<task>` on branch `gw/<task>`. The orchestrator never commits, pushes, merges or releases. You review and merge the branch yourself.
- **Repairs.** A failed check sends its real output back to the **same** worker session (`--resume`), at most twice. Login, quota, permission, model and timeout failures never trigger a repair. They block the task until you resume it.
- **Answer evidence (QUESTION).** The worker lists each claim with a verbatim quote and its file and lines. `evidence.py` checks in code:
  - the quote is at those lines;
  - provenance: the commit, the file's git hash, whether it is dirty, and when it was checked;
  - the file has not changed by the time the final status is given;
  - the right kind of source: code for code claims, docs for doc claims, and the vendor doc for the API version the repository pins;
  - a contradiction only when a located, current quote about the same setting states a different value.

  A claim that fails gets one repair turn. If it still fails, it is shown as UNVERIFIED with its reason, not as a task failure. With no independent reviewer yet, a claim whose quote was found is "quote located; support not reviewed", never "verified". The answer gets CONTRADICTED, UNVERIFIED or PARTIALLY_SUPPORTED, printed with each claim's status and an "Uncertain:" list.
- **Final status.**
  - `VERIFIED`: your checks passed on the changed code, and the diff matches what the worker reported.
  - `PARTIALLY_VERIFIED`: the deterministic checks passed, but the content itself (an answer, a document) is not machine-checked, or the diff has files the worker did not report.
  - `FAILED`, `BLOCKED` and `CANCELLED` mean what they say.

## Configuration

| Item | Where |
|---|---|
| State, worktrees, telemetry | `~/.claude/groundwork/orchestrator/` (`GROUNDWORK_ORCH_HOME` overrides) |
| Workspace allowlist | `groundwork orch allow <path>` → `config.json` |
| Model/effort per role | packaged `routing.json`; your override: `~/.claude/groundwork/orchestrator/routing.json` (validated; unknown models are rejected) |
| Worker timeout | `GROUNDWORK_ORCH_WORKER_TIMEOUT` (seconds, default 1800) |
| Telemetry off | `GROUNDWORK_ORCH_TELEMETRY=off` |

## How to run

```bash
./install.sh --with-orchestrator
```

```bash
groundwork orch doctor
```

```bash
groundwork orch allow ~/projects/my-repo
```

```bash
groundwork query "How does the session snapshot hook work?" --workspace ~/projects/my-repo
```

```bash
groundwork orch show <task-id>
```

A write task stops at `WAITING_APPROVAL` and prints the plan. Then run `groundwork orch approve <id>` or `groundwork orch reject <id>`. A `BLOCKED` task resumes with `groundwork orch resume <id>` once the cause is fixed.

Exit codes: 0 passed, 1 failed, 3 waiting for approval, 4 blocked, 5 cancelled.

## Validation

```bash
orchestrator/.venv/bin/python -m pytest orchestrator/tests -q
```

The 72 tests use a stub `claude` binary and never call a model. That includes a test that SIGKILLs a real orchestrator process mid-run. Live acceptance runs on the real CLI are recorded in `openspec/changes/add-orchestrator-mvp/`. Dev setup:

```bash
python3 -m venv orchestrator/.venv && orchestrator/.venv/bin/pip install -r orchestrator/requirements.txt pytest
```

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `BLOCKED: subscription preflight failed` | `claude auth status` is not a claude.ai login on the first-party provider. Log in with `claude` → `/login`. The orchestrator never falls back to an API key |
| `BLOCKED: worker quota` | Your plan's usage limit was reached. Wait, then `groundwork orch resume <id>` |
| `not an allowed workspace` | Run `groundwork orch allow <path>`, then resume |
| `interrupted_write` | The orchestrator died while a write worker ran. Inspect the worktree, then `groundwork orch resume <id> --release-interrupted` |
| `unauthorized_write` | A read-only worker changed a file. The task fails and is not repaired. Inspect `git status` in the workspace |
| `[!] changes match the worker's report` | Files the worker did not report, often Groundwork's own intake hook adding `openspec/` files in the worktree (see Limitations). Review before merging |
| A task looks stuck as RUNNING after a crash | `groundwork orch resume <id>`. Sessions whose orchestrator is gone are marked abandoned, and their worker process group is stopped |

## Security constraints

- Only the official `claude` CLI, with your existing login. Never `--bare` (it ignores the subscription login), never a permission-bypass mode. `--permission-prompts none` is always set. API-key and alternate-provider variables are removed from every worker.
- Your `~/.claude` hooks (task gate, protected push) run inside every worker.
- The tool list per role is a code-level control, not a prompt instruction. File and command output is framed as untrusted data.
- Workspaces must be allowlisted. Read-only by default. Protected paths (`.git/`, `.claude/`, `.github/workflows/`, `.mcp.json`) fail a task if they are changed.
- Prompts go on stdin, never argv. State files are created with mode 0600.

## Limitations (Phase 1)

- One worker at a time. No task decomposition, memory, evaluation fixtures or dashboard yet (Phases 2–4).
- [!] **Groundwork's task-intake hook runs inside each worker.** In a worktree it can create a separate ledger task and `openspec/` files. They are reported as unaccounted changes, so such a task is at most PARTIALLY_VERIFIED. The planned fix is an intake-only switch in the task gate, after the pending 2.5.0 work lands.
- A worker may be unable to run your check itself when the check has quoted arguments (`python3 -c "…"`). The allow rule or the task gate denies it in `-p`. The orchestrator still runs the check and decides. Prefer simple check commands such as `python3 check.py`.
- `total_cost_usd` is Claude Code's client-side estimate. Whether a call draws from plan limits or from a plan's monthly API credits is not visible from the CLI.
- An answer's correctness is not machine-checked. The Evidence Engine proves that each quoted line exists and fits the claim's value. It does not prove that the quote supports the claim's meaning: that needs the independent reviewer (M3). Only file sources are checked: no URLs and no command probes.
- [!] Checks run code the worker wrote, as you, before you review the diff. Secret-looking environment variables are removed, but files in your home directory (for example `~/.aws`) are readable. The approval screen says so. A real sandbox is later work.
- If a task is blocked and you edit the workspace yourself meanwhile, a read-only task will report `unauthorized_write`, because the workspace fingerprint was taken before the worker ran.
- Write tasks start from the workspace's last commit. Uncommitted changes in your workspace are not in the worktree.
- Orphan cleanup identifies a worker by `claude` in its command line. In a rare case of PID reuse by another `claude` process, `resume` refuses with "did not stop" rather than guess.

## Source references

- Claude Code headless mode (`--bare`, `--json-schema`, `--resume`, `--permission-prompts`): https://code.claude.com/docs/en/headless
- Claude Code CLI reference: https://code.claude.com/docs/en/cli-reference
- Using `claude -p` with a Claude plan: https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan
- Design, decisions and evidence: `openspec/changes/add-orchestrator-mvp/`
