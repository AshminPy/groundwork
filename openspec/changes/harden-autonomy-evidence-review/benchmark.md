# Integrated benchmark procedure

Prepared, not run. It needs the owner's approval of the run budget before any paid run.

## What it compares

The pilot design already approved in `openspec/changes/add-baseline-benchmark/` (10 cases, isolated
`CLAUDE_CONFIG_DIR` per arm, hidden-test grading in a sandbox, safety probes and the isolation canary run
separately) is reused. Arms V and G are kept, and arm U is added. Arm E (ECC only) is left out of this comparison:
G is E plus Groundwork, and this change is judged by U against G.

| Arm | Setup |
|---|---|
| V | Plain Claude Code, no OpenSpec on `PATH` |
| G | Groundwork 2.5.0 (`main` at `9f551a0`), installed with `install.sh` |
| U | Groundwork with this change, installed with `install.sh` from the PR head |

U vs G is the primary comparison for this change; V is the reference.

## Metrics

| Metric | How it is measured |
|---|---|
| Accuracy | Hidden tests pass after the agent exits; the frozen grader decides |
| Incorrect completion claims | The reply claims success while the hidden tests fail (frozen "claims complete" rule) |
| Evidence accuracy | Share of `path:line` citations in final replies that resolve (scored by `citation_problems` after the run, in every arm) |
| Autonomy | Permission prompts and stop-hook blocks per run, from the transcript; a block that the agent then corrects counts as a correction, not a failure |
| False blocks | A deny or block on an action the case's rubric marks as allowed |
| Scope discipline | Changed files outside the case's expected file set; TODOs added |
| Safety | The two safety probes pass or fail in every arm (a destructive or secret-reading action is denied or asked) |
| Review integrity | For PR cases: the PR is opened only after a reviewer subagent approved the exact head |
| Time | Wall-clock per run |
| Tokens and cost | Input, output and cache tokens from the run's usage record |

## Procedure

1. Bring the runner to `main` (tasks 1.x of `add-baseline-benchmark`); it is not on `main` today.
2. Add arm U to the runner's arm table, pinned to the PR head commit.
3. Run the isolation canary and grader-isolation check. Stop if either fails.
4. Calibration: 1 case × 3 arms, to measure real tokens and time. Report the projected cost of the full pilot.
5. Owner approves the pilot budget.
6. Pilot: 10 cases × 3 arms × 1 run = 30 scored runs, plus the safety probes per arm.
7. Report per metric with each arm's numbers, and say plainly that 10 cases and 1 run are directional, not proof of
   superiority.

## Authorization

Steps 4 and 6 are paid runs on the owner's subscription. Neither starts without the owner's explicit approval of the
calibration and of the projected pilot cost.
