# M1 benchmark pilot

Compares plain Claude Code (arm A) with the Groundwork orchestrator from PR #62 (arm B) on 12 read-only cases. Design: `openspec/changes/meta-harness-architecture/design.md` §8 (PR #63).

> This is an **initial pilot, not statistical proof**. With 12 cases × 2 repeats, a difference of one or two cases is noise.

## Run

```bash
cd orchestrator && .venv/bin/python -m bench.run --runs-dir /tmp/groundwork-bench
```

```bash
cd orchestrator && .venv/bin/python -m bench.canary
```

The runner checks the subscription login, runs the isolation canary, and then runs each case × repeat × arm in a fresh copy of the fixture. It writes `results.jsonl`, `report.md` and per-run `final.txt` / `stream.jsonl` under `--runs-dir/<run-id>/`. A re-run with the same `--run-id` continues where it stopped. It stops early at 80% five-hour or 70% seven-day plan usage, read from Claude Code's own `rate_limit_event`.

## Fairness

| Item | Arm A | Arm B |
|---|---|---|
| Request text | `tasks/<case>/instruction.md`, unchanged | the same text, as `groundwork query` |
| Model, effort | sonnet, medium | sonnet, medium (PR #62 `routing.json` answer/document roles; the report lists the models actually used) |
| Tools | Read, Grep, Glob | Read, Grep, Glob |
| Settings | user settings (Groundwork hooks on) + read fence | the same, from PR #62's adapter |
| Environment | API-key variables removed | the same function |

## Safety

- Nothing in the fixture is executed, and arm B is never given a check or write permission. Any approval or blocked pause is rejected or cancelled.
- **Read fence:** `--settings '{"permissions":{"blockReadsOutsideWorkingDirectories":true}}'` on every call in both arms. The file tools refuse every path outside the run's workspace.
- **Canary (hard gate):** six probes per arm (Read, Grep, Glob on a fake key in `~/groundwork-bench-keys/` and a fake secret beside the workspace). If one is not refused, or a fake value leaks, nothing runs.
- Answer keys live in `bench/keys/`, outside every run workspace, and are read only by the grader after a run.
- The two prompt-injection cases point at a fake token inside the fixture (`.canary/token.txt`), never at a real secret.

## Grading

`grade.py` reads only the arm's final visible text and the fixture. It never reads the harness's own status. For arm B, the visible text is the result text plus its sources and unknowns. Every rule is a regex or a file lookup:
- required facts and forbidden statements;
- invented environment-variable names;
- citations that resolve to a real file and line;
- citations within 2 lines of the key lines;
- uncertainty wording, used to count wrong answers stated with no hedge;
- leaks of the fake secrets.

`tests/test_bench.py` proves that every oracle answer passes and every deliberately wrong answer fails.

## Limits

- One small fictional fixture. Questions are short, so this says little about large repositories.
- Regex graders can miss a correct answer phrased in an unexpected way. Wrong verdicts are listed per case for a manual check.
- Arm B uses `--output-format json`, so the report has no tool-call trace for it. Its outside-read attempts are not counted, though the fence still blocks them.
- Usage is measured in tokens. Claude Code's cost field is a list-price estimate, not a bill, and is not reported.
