## Why

The goal: accurate, evidence-backed and consistent results on every task given to Claude Code, plus autonomous runs. A separate LangGraph harness was built and measured against it (PR #62, #64, #65; design at d37a190 in this PR's history). On the M2 benchmark, current Groundwork without the harness compared like this:

| | Current Groundwork | Separate harness |
|---|---|---|
| Correct answers | 39/40 | 40/40 |
| Median time per question | 47.5 s | 56.5 s |
| Output tokens | 64,851 | 98,332 |

The harness also brought its own failure modes: a routing block, and an intake-hook conflict. Its one measured unique benefit, mechanical quote checking, is about 200 lines of standard-library code.

The owner's real failures are not covered by either:
- Unproven leaps in recommendations. For example, "pin back to 0.14.0" was recommended without evidence that 0.15.0 caused the problem.
- Context lost as sessions grow, with no clean sharing between sessions.
- No answer to "which session used up the plan limit?".

## What Changes

The separate harness is parked: its PRs are closed and its branches kept. Core Groundwork gains five small, standard-library-only additions, each built test-first and measured:

1. **Benchmark in core.** The M1/M2 harness, reduced to "Groundwork today vs Groundwork + feature", with a frozen grader and the isolation canary.
2. **Usage visibility.** The statusLine records per-session usage. `groundwork usage` ranks the sessions in the current window. An early-warning segment shows plan usage.
3. **Task brief continuity.** One brief per task. A checkpoint prompt fires at about 65% context. The existing session-start snapshot reloads the brief after compaction and in new sessions.
4. **Citation check.** File and line citations in an answer are checked against the quoted text, reusing the M2 logic.
5. **Decision gate.** Each recommendation states its premise as PROVEN or HYPOTHESIS. A "do X" never rests on a HYPOTHESIS. A fresh-context challenge review runs before a recommendation is final. It is built only if the benchmark shows current Groundwork making the leap.

## Capabilities

### New Capabilities
- `core-evidence-continuity`: usage visibility, task brief continuity, citation check, decision gate, and the benchmark that measures them.

### Modified Capabilities
- `groundwork-statusline`: adds a usage record and a plan-usage segment. Existing output is unchanged unless enabled.

## Impact

- Code: hooks and scripts under `hooks/` and `scripts/`, plus `bench/`. Standard library only, as core requires.
- Parked: `orchestrator/` stays out of `main`. The PR #62, #64 and #65 branches are kept for possible unattended code-change runs later.
- Order: after PR #61 (2.5.0). These changes are planned for the next version.
