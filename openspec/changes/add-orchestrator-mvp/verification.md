# Verification record — add-orchestrator-mvp (Phase 1)

All runs were on macOS (Darwin 25.5.0) with Python 3.13.7 and Claude Code 2.1.310, on 2026-10-24/25.

## Phase 0 baseline

- `python3 -m pytest tests -q` on origin/main 086216d → 141 passed, 0 failed (8 min 28 s).
- The live smoke test was a Python `subprocess` call to `claude -p --model haiku --tools "" --output-format json --max-turns 1`, run with `ANTHROPIC_API_KEY` removed and without `--bare`. It returned exit 0, `subtype=success`, model `claude-haiku-5-5`, and a `session_id`, in 11.7 s. `claude auth status` reported `authMethod=claude.ai`, `apiProvider=firstParty`, `subscriptionType=max`.
- LangGraph probe (langgraph 1.2.17, langgraph-checkpoint-sqlite 3.1.2), run as three separate processes:
  - an `interrupt()` survived the process exit;
  - after an exception in node `b`, resume had `next=('b',)` and re-ran only `b`.

## Automated tests (stub `claude`, no model calls)

`orchestrator/.venv/bin/python -m pytest orchestrator/tests -q` → **72 passed**. The path there had failures along the way.

| Attempt | Result | Cause | Change |
|---|---|---|---|
| unit 1 | 26 passed, 6 failed | 5 adapter tests: `ValueError: I/O operation on closed file`. The adapter closed stdin itself, then called `communicate()`. 1 classifier test: "explain" was counted twice | Prompt sent through `communicate(input=…)` on the first poll; removed the duplicate signal |
| unit 2 | 32 passed | — | — |
| workflow 1 | 5 passed, stopped at 1 failure | "Write documentation for the add function" tied DOCUMENTATION/PROJECT ("add", "function"), which is a classifier defect | Added a "write/update … docs/README/guide" signal |
| workflow 2 | 52 passed, 2 failed | The new signal correctly made the "ambiguous" example a DOCUMENTATION request | Used a genuinely tied example |
| workflow 3 | 54 passed, 1 failed | Test-stub bug: the stub picked steps by total call count, so a re-planned stub replayed the wrong step | The stub now counts from the moment a plan is set |
| workflow 4 | 55 passed | — | — |
| after live B | 56 passed | Regression test for unreported files | — |
| after review round 1 | 70 passed | 14 regression tests for the review fixes | — |
| after review NICE TO HAVEs | 72 passed, then 1 failed on re-run | Regression introduced by the N1 edit: `test_timeout_kills_the_worker_group` failed intermittently (`PermissionError` from `killpg(pgid, 0)`, then `DID NOT RAISE ProcessLookupError`; 8/20 passed). Cause: the rewrite dropped `proc.wait()`, so the leader stayed an unreaped zombie. On macOS a zombie-only group answers EPERM, and the zombie keeps its pid. A first fix (EPERM only) was not enough | `terminate()` always reaps the leader; EPERM on the probe counts as gone → 20/20 passes of the process tests, and 3 consecutive full runs of 72 passed |

Brief test map:

| Test | Status |
|---|---|
| T01–T09, T12–T14, T17, T18, T20 | covered by named tests in `orchestrator/tests/` |
| T12 | includes a real SIGKILL of an orchestrator process |
| T10, T11, T15, T16 | Phase 2/3 (parallel workers, memory), not built |
| T19 (existing suite) | `python3 -m pytest tests -q` → 142 passed, 0 failed (141 baseline + 1 new CLI test); `tests/test_groundwork_cli.py` → 10 passed, re-run after the last edits |

Other checks:
- `openspec validate add-orchestrator-mvp --strict` → valid.
- `bash -n install.sh uninstall.sh` → clean.
- `install.sh --with-orchestrator` in a sandboxed config dir: exit 0, venv and package installed, `groundwork orch doctor` ran, and uninstall removed the add-on.

## Live acceptance (real Claude Code, claude.ai Max login, scratch fixture repo)

Costs below are Claude Code's client-side estimates, not bills.

| Scenario | Task | Result | Evidence |
|---|---|---|---|
| A question | T20261025-061432-9d2f | PASSED, PARTIALLY_VERIFIED | QUESTION by rules, no classifier call. One sonnet/medium worker, 66.8 s, est. $0.85. Workspace unchanged; 5 cited files exist |
| B troubleshooting + fix | T20261025-061554-de46 | PASSED, VERIFIED (before the unreported-files check existed) | Symptom `AssertionError: 2 + 3 gave -1.0`. opus/high, 143.9 s, est. $1.74. One-line fix in the worktree; `python3 check.py` passed there; main tree unchanged |
| C small project | T20261025-065904-2314 | PASSED, PARTIALLY_VERIFIED | opus/high plan (82.1 s, est. $1.72), approval, sonnet/medium implementation (148.1 s, est. $1.00). Diff matches the plan; the owner check `sub ok` passed; main tree unchanged |
| B again, after review fixes | T20261025-072555-ee98 | PASSED, PARTIALLY_VERIFIED | Approval screen showed the symptom and the check-exposure warning. Workers ran with `--setting-sources user --strict-mcp-config`; scope was checked against the base commit; the check ran with a scrubbed env |

**Live findings, not visible with the stub:**

1. Groundwork's own task-intake hook runs inside each worker. In a worktree it created a separate ledger task (`GW-1`, MATERIAL) and `openspec/` files.
   - Mitigation: files the worker did not report are flagged, and the task is at most PARTIALLY_VERIFIED.
   - Proper fix: an intake-only switch in the task gate, a follow-up after PR #61.
   - The stray ledger tasks from these runs were cancelled with `groundwork_tasks.py cancel GW-1`.
2. A project-level hook in an untrusted repository's `.claude/settings.json` ran inside a default `claude -p` session. With `--setting-sources user --strict-mcp-config` it did not run (live probe). Workers now always pass both.
3. A worker could not run a quoted check (`python3 -c "…"`) through its own Bash tool. The orchestrator's own check still ran and decided the outcome.

## Independent review

- **Round 1** (fresh context, two reviewers):
  - `automation-reviewer`: changes-required, 4 MUST FIX:
    - no per-task lock;
    - orphan cleanup that sent SIGTERM only and could hit a reused PID;
    - a write scope blind to ignored files and commits;
    - checks running worker code with the full environment.
  - `ecc:code-reviewer`: changes-required, 1 MUST FIX, the same as the last item.
  - All were fixed, each with a regression test.
- **Round 2** (fresh `ecc:code-reviewer`): **approve, Must-fix: 0**. It confirmed each earlier item was resolved in the code and that the new tests would have failed before.
- Of its 5 NICE TO HAVE items, N1–N4 were fixed afterwards: whole-group termination, no checks after a fatal violation, a clean error for a stuck orphan, and `check_related` path handling. These small edits came after the approving review. N5 (PID reuse by another `claude` process) is documented in the README.
- **Round 3** (fresh `ecc:code-reviewer`, scoped to the post-approval edits: `terminate`, `group_alive`, `stop_group`, `abandon_sessions`, `check_related`, the fatal-skip and the CLI error mapping): **approve, Must-fix: 0**. Its open NICE TO HAVE items, for follow-up:
  - an orphan whose leader is already gone but whose group member is alive is marked abandoned without being stopped;
  - `stop_group` should confirm `getpgid(pid) == pid` before signalling;
  - `check_related` does not expand directory arguments such as `pytest tests/` (test files are still caught by name patterns).
