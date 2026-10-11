# Autoship: a bounded autonomous loop, built from what already exists

**Verdict: no new code is needed.** Claude Code's `/goal`, `claude -p`, `--max-budget-usd` and `timeout`, together with
Groundwork's existing review gate, push guard and evidence rules, already provide the loop UNDERSTAND → PLAN → IMPLEMENT →
TEST → REVIEW → FIX → REVALIDATE → REPORT with bounds. This page is the recipe and the evidence. It adds a fixture
generator for reproducing it and nothing that runs by itself.

## What provides each part

| Part of the loop | Provided by | Kind |
|---|---|---|
| Acceptance criteria that can be tested | the OpenSpec change (`specs/**` scenarios, `tasks.md`) plus the test command | Groundwork convention |
| Keep going until done | `/goal <condition>`: a session-scoped Stop hook; a small model judges the condition from the transcript after every turn ([docs](https://code.claude.com/docs/en/goal)) | native |
| Run unattended | `claude -p "/goal …"` runs the loop to completion in one call; Ctrl-C stops it ([docs](https://code.claude.com/docs/en/goal)) | native |
| Independent review | the `Agent` tool with a reviewer subagent; Groundwork's Stop hook `require_material_review.py` requires a review when a fully ticked OpenSpec change is uncommitted, and after a MUST FIX only a fresh review reporting `Must-fix: 0` clears it | Groundwork |
| Green tests are not runtime proof | the completion rules in `rules/evidence-policy.md` §6; the goal condition below makes the final message say what was not verified | Groundwork |
| Branch protection, no auto-merge | `block_protected_push.py` stays active; the condition says nothing is committed, pushed or deployed | Groundwork |

## The bounds, and which are hard

| Bound | Hard? | Source |
|---|---|---|
| `--max-budget-usd N` | yes, but it can be overshot (run C below spent USD 0.109 against 0.05; the check appears to happen between turns: INFERENCE) | `claude --help` (2.1.296): "Maximum dollar amount to spend on API calls (only works with --print)" |
| `timeout SECONDS claude -p …` | yes (the process is killed) | coreutils |
| A Stop hook can block at most 8 times in a row without a tool call in between | yes | [hooks guide](https://code.claude.com/docs/en/hooks-guide) ("Stop hook hits the block cap") |
| The loop stops when the model makes no tool call for several turns, or a turn fails on an error you must fix (authentication, no credit, context overflow, model unavailable) | yes | [`/goal` docs](https://code.claude.com/docs/en/goal) |
| Permission allow-list (`--allowedTools`), not a permission bypass | yes | native; nothing in this recipe uses `--dangerously-skip-permissions` |
| "stop after 20 turns" and "same test fails after 3 attempts → BLOCKED", written into the condition | **no**: judged by the model from the conversation | [`/goal` docs](https://code.claude.com/docs/en/goal): "the evaluator judges it from the conversation" |

The evaluator "doesn't run commands or read files independently", so the condition must be something the model's own
output demonstrates (a test summary line in the transcript, a reviewer's `REVIEW RESULT`).

## Recipe

```bash
python3 docs/examples/autoship/make_fixture.py /tmp/autoship-demo          # a disposable repo; add --wrong-test for the BLOCKED case
cd /tmp/autoship-demo
timeout 1800 claude -p "$(cat GOAL.txt)" \
  --allowedTools "Read" "Glob" "Grep" "Edit" "Write" "Agent" \
                 "Bash(python3 -m pytest:*)" "Bash(python3 -m durations_cli:*)" \
                 "Bash(git status:*)" "Bash(git diff:*)" "Bash(git log:*)" "Bash(ls:*)" \
  --max-budget-usd 4 --output-format stream-json --verbose < /dev/null > run.jsonl
```

`GOAL.txt` is the condition: finish when all tasks are ticked, the tests print a passing summary, a fresh reviewer's last
`REVIEW RESULT` says `Must-fix: 0`, `tests/` is unmodified and nothing is committed; or stop as BLOCKED with the exact failing
output in `BLOCKED.md`. For your own work replace the task, the test command and the allow-list, and keep the shape.

## What was observed

Claude Code 2.1.296, model `claude-sonnet-5-5`, 2026-10-11, on a disposable fixture (this page's generator), all runs with the
allow-list above. Costs are what the CLI reported. A and A′ used a slightly shorter condition than `GOAL.txt` (they had the "same
test still fails after 3 attempts → BLOCKED" clause but not the "a failing test contradicts the spec" branch); B used the
`GOAL.txt` shape. The shape is the same.

| Run | Condition | Outcome (observed in the stream-json log) |
|---|---|---|
| A′ — full loop | tasks ticked + tests + clean fresh review, baseline run first | Baseline `13 failed, 3 passed`. First implementation: `4 failed, 12 passed` (the model had made the space between tokens mandatory). Fixed: `16 passed`. First independent review `changes-required`, `Must-fix: 1` (the character `ſ` passed the case-insensitive pattern, then raised `KeyError`, so the CLI exited 1 instead of 2). Fixed: `16 passed`. Fresh second review `approve`, `Must-fix: 0`. `tests/` untouched, nothing committed. Final message: `Complete`, with what was tested and what was not. 28 tool calls, 2 reviewer calls, USD 0.67. |
| A — same, without the baseline step | as A′ without "run the suite first" | The model never ran the suite before changing code, so no failing run appears in that transcript. Its first review found 2 must-fix items, it fixed them, a fresh review approved. USD 0.70. Reported because it shows the baseline step has to be asked for. |
| B — blocked path (`--wrong-test`) | A′ plus "stop as BLOCKED" | One test expected `2d == 172801`. After implementing: `1 failed, 15 passed`. The model did not edit the test. It wrote `BLOCKED.md` with the exact failing output and the requirement that contradicts it, left the tasks unticked, ran no review, and its final message began "BLOCKED. The goal is not met, and I am not claiming success." `tests/` untouched. USD 0.31. |
| C — hard budget | A′ with `--max-budget-usd 0.05` | Stopped after 2 turns with `error_max_budget_usd` ("Reached maximum budget ($0.05)"), exit code 1, having spent USD 0.109. |

Also observed:

- The reviewer ran as a background agent; `/goal` skipped its evaluation until the reviewer finished, as the docs describe.
- In A and A′, 7 and 4 tool calls were refused because the allow-list was narrower than what the model tried (for example
  `sed -i`, compound commands). The model adapted and nothing was bypassed; the refusals cost turns.
- Every Stop hook response in A, A′ and B (the Stop hooks configured in this environment, Groundwork's included) reported exit
  code 0 and outcome `success`; none blocked a stop. In these runs the model ticked the tasks only after the review, so
  Groundwork's review gate was not what forced the review. That gate's blocking behaviour was not exercised here.

## What this does not show

- One fixture, one model, a task of about USD 0.3 to 0.7. Larger tasks were not run.
- The test failure in A′ is real but small, and the baseline failure is seeded by the fixture.
- The soft bounds (turn count, three attempts) were followed in B and not otherwise stressed; a model that ignores them is
  stopped only by the hard bounds.
- The loop ends at a local, uncommitted change. It does not merge, deploy or validate anything at runtime; that stays a human
  or separately authorised step.
- Only Linux, only `-p` mode. The interactive `/goal` was not run.
- Passing tests and a clean review are evidence for those checks only (`rules/evidence-policy.md` §6).
