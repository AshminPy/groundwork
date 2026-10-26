# Core evidence and continuity — design

## Decision
```
DECISION            Park the separate LangGraph harness; reach the goal by extending core Groundwork.
EVIDENCE            M2 benchmark (20 read-only cases × 2 repeats, frozen grader 226a1f99…, results in PR #65
                    orchestrator/bench/results/m2-comparison.md): current Groundwork 39/40 correct, p50 47.5 s, 64,851 output
                    tokens; separate harness 40/40, p50 56.5 s, 98,332 tokens. The +1 came from routing questions that
                    the harness itself had blocked before M2. Current Groundwork = arm A, which loaded the user's ~/.claude
                    (Groundwork hooks seen firing in the canary stream).
WHY                 Same accuracy at lower time and cost; fewer moving parts; the harness's unique measured value (quote
                    checking) is small and portable. Unattended code-change runs are the only capability lost, and no
                    current task needs them.
TRADEOFFS           No durable unattended write workflow (approvals that wait, crash-resume, worktrees) until needed.
                    Gates in core are hooks plus model review, not a separate process.
VALIDATION METHOD   Each feature is measured with the core benchmark: Groundwork today vs Groundwork + feature.
UNCERTAINTY         The benchmark questions are small and easy; harder, real cases may show gaps neither arm handles.
```

## Principles
1. **Measure first.** A feature is built only after a benchmark case shows current Groundwork failing at it, and kept only if it closes the gap.
2. **Never-cases first.** Each requirement lists what must never happen. Those are written as failing tests before code.
3. **Hooks enforce; prompts suggest.** Anything that must hold on every task is a hook or a deterministic check, not rule text alone.
4. **Standard library only, small changes, one PR per feature.**

## 1. Benchmark in core (`bench/`)
- Reused from PR #64/#65: tasks in Harbor layout, held-out keys, `grade.py`, `freeze.py` (fingerprint), `regrade.py`, `compare.py`, the isolation canary.
- Arms: **G0** = Groundwork as installed; **G1** = Groundwork plus the feature under test, toggled by config. Both use `claude -p` with the user's settings, read-only tools and the read fence (`permissions.blockReadsOutsideWorkingDirectories`), and the same model and effort.
- Re-runs: only the cases a change can affect. A grader fix means a model-free re-grade.
- Never: a grader reads an arm's own status; arms are compared under different grader fingerprints; the canary is skipped.

## 2. Usage visibility
Source: the statusLine stdin JSON (Claude Code statusline docs, checked 2026-10-26):
- `session_id`, `session_name`;
- `workspace.current_dir`, `workspace.repo.*`, `model.id`;
- `cost.total_cost_usd` (cumulative, client-side list-price estimate, reset by `/clear`);
- `context_window.used_percentage`;
- `rate_limits.five_hour|seven_day.used_percentage|resets_at`. These appear only for Pro and Max, or behind a spend-limit gateway, and only after the first response.

- **Record:** at most once a minute per session, append one line to `~/.claude/groundwork/telemetry/usage.jsonl` with `ts`, `session_id`, `session_name`, `repo`, `model`, `cost_usd`, `ctx_pct`, `five_hour_pct`, `seven_day_pct` and the reset times. No prompt or answer text is stored.
- **Report:** `groundwork usage [--window 5h|7d]` lists the sessions active in the current window, ranked by the cost increase within the window, with plan usage and reset times.
- **Segment:** an optional statusLine segment, `5h 82%`, shown from a configurable threshold.
- **Facts the report states plainly:**
  - Limits are account-wide. All sessions, and claude.ai chat, draw from one 5-hour and one weekly bucket. So the report ranks contributors; it never names "the session that exceeded".
  - Cost is an estimate.
  - Headless `claude -p` sessions may not run a statusLine (UNVERIFIED), so they may be missing.
- **Never:**
  - store message content;
  - present cost as a bill;
  - claim one session exceeded the limit;
  - fail the statusLine render when the record cannot be written.

## 3. Task brief continuity
- **Brief:** `~/.claude/groundwork/briefs/<repo-key>/<task-key>.md`. The task key is the ledger task (GW-n) when one exists; otherwise the repo-level investigation file is kept as today. Sections: objective, decisions (with evidence), verified facts (with sources), rejected hypotheses (with reasons), next step. Current state only; it is not a log.
- **Checkpoint:** a UserPromptSubmit hook reads the session's latest `ctx_pct` from the usage record. At or above `brief_checkpoint_pct` (default 65, configurable), it adds one line of context: "Context is N%: update the task brief now." It fires at most once per 10 percentage points per session.
- **Reload:** the existing SessionStart snapshot (registered with no matcher, so it also runs after compaction) includes the brief for the active task, within its existing size cap and with "Rejected hypotheses" first.
- **Never:**
  - one session silently overwrites another session's brief (the brief is per task, and an edit keeps a short "last updated by session X" line);
  - a brief is loaded for a different repository;
  - the checkpoint blocks a prompt;
  - the brief is treated as fact without revalidation (the existing evidence-policy §8).

## 4. Citation check
- `evidence.locate` logic (PR #65) moves to core as a standard-library module. A checker reads `path:line[-line]` citations and any quoted text from the final answer, and reports citations whose file or line does not exist, or whose quote is not at those lines.
- **Delivery:** the check runs at Stop, using `transcript_path` (a documented common hook input) to read the final assistant message. It reports. It does not block. Whether reading the final message from the transcript is stable is UNVERIFIED: the transcript format is internal. That is checked first. If it is not stable, the fallback is an on-demand `groundwork check-citations` command.
- **Never:**
  - flag a citation as wrong when the file exists and no line or quote was given;
  - read files outside the session's working directories;
  - block the user's turn.

## 5. Decision gate
- **Built only if** benchmark cases modelled on the runner incident show current Groundwork recommending an action on an unproven premise.
- **Recommendation record:**
  - action;
  - premise;
  - status, PROVEN (the evidence) or HYPOTHESIS;
  - for a HYPOTHESIS, the cheapest test;
  - the risk of acting before that test.
- **Rule, checked deterministically on the structure:** a recommendation whose premise is HYPOTHESIS must be written as "test first: …".
- **Challenge review:** a fresh-context reviewer subagent asks three questions. What proves each premise? What else explains the symptom? What is the cheapest test? It is model judgment and improves the odds; it is not proof.
- **Never:**
  - a "do X" recommendation built on a HYPOTHESIS reaches the user without the challenge result attached;
  - the gate rewrites the user's facts.

## Verification
- `python3 -m pytest tests -q`: all existing and new tests pass. New tests are written from each never-case.
- `openspec validate core-evidence-continuity --strict`.
- Live checks:
  - **usage:** two concurrent sessions appear in `groundwork usage` with plausible numbers;
  - **brief:** a forced early compaction (`CLAUDE_CODE_AUTO_COMPACT_WINDOW=100000` in a test session) reloads the brief verbatim;
  - **citation check:** a planted wrong citation is reported;
  - **decision gate:** benchmark cases, G0 vs G1.
- An independent review per PR.
