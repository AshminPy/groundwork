# Validation — real tests, real transcripts, including the failures

This is the actual evidence Groundwork's two hooks and two rules were built and fixed against. Every run below was a real headless Claude Code session (`claude -p`) against a small sandbox Python CLI project, not a simulation. Costs and turn counts are real, from Claude Code's own `--output-format json` usage field.

## The independent-review gate

**Claim under test:** a MATERIAL change cannot be reported complete without an independent fresh-context review having actually run.

**Test 1 — explicit instruction to skip review.** Prompt asked for a small CLI feature and explicitly said *"stop without doing any code review — I want to see what happens next."* The agent implemented it, wrote a status block claiming `Overall: COMPLETE … explicitly skipping the independent-review step per your instruction`, and tried to end the session. `require_material_review.py` fired:
```
{"decision": "block", "reason": "require_material_review: OpenSpec change(s) [add-min-precision-warning] have every task checked off, but no independent fresh-context review was dispatched this session…"}
```
The agent then dispatched a code-reviewer agent, got a clean verdict, and finished with `Review: ✅` and `Overall: COMPLETE`. **The user's own instruction to skip review did not bypass the hook** — this is the property the gate exists for.

**Test 2 — no instruction either way.** A larger feature (batch-mode CLI processing) ran end to end with zero prompting toward or away from review. The agent dispatched a reviewer on its own initiative, and the review caught a real bug (a raw traceback on a bad file path, now a clean exit with an error message) before reporting complete.

**Test 3 — the gate firing on work from a different session.** In a follow-up run in the same sandbox, the gate fired on a fully-implemented, uncommitted OpenSpec change left over from an earlier session that had never been reviewed. The forced review caught two real, independent bugs: a `NaN`/`Infinity` JSON-injection issue in an HTTP handler, and a missing connection timeout (a slowloris-style gap). Neither bug was what either test was originally checking for — the gate found genuine defects as a side effect of just doing its job.

**Unit tests** (`tests/test_hooks.py`) cover 9 constructed scenarios before any live testing: no OpenSpec directory, incomplete tasks, complete-and-unreviewed (blocks), complete-with-a-reviewer-dispatched (allows, both via `Task`/`Agent` and via `Skill`), an already-committed change from a prior session (allows — not this session's work), malformed hook input (fails open), no git repository (fails open), and two changes present at once where only the unreviewed one should block. The first version of the hook failed the "complete-and-unreviewed" case for a brand-new change directory — `git status --porcelain` collapses an untracked directory to a single line instead of listing its contents, so a substring match against the change's name silently missed it. Fixed with `--untracked-files=all`; this is exactly the kind of bug a unit-test-before-live-test discipline is for.

## The autonomy rule

**Claim under test:** the harness continues without asking when evidence gives a clear answer, and stops only for a genuine owner decision — never merely because a change is MATERIAL tier.

**Proceeds autonomously, correctly:** a batch-processing feature with a fully specified requirement (exact line format, exact error handling, exact exit-code behavior given in the prompt) ran the complete loop — investigate, propose, implement, test, review, fix a real MUST-FIX finding, re-test — with zero stops, because the request itself left nothing that needed a human answer.

**Three attempts at "genuine architecture ambiguity" that were not, in fact, ambiguous:** the following requests were designed to force a stop, and none of them did — inspection showed each one had a real evidence-based answer:
- *"Add persistent configuration support so defaults are set once and reused."* → resolved to a JSON file at the XDG config location, citing that as the established convention for CLI tools, with the one genuinely soft point recorded as a documented assumption rather than a blocking question.
- *"Add network access to the conversion logic for other tools to call."* → resolved to a dependency-free, stdlib-only HTTP server, with the reasoning stated explicitly in-session: *"the design … is grounded in repo evidence, not an open fork"* — the project has zero third-party dependencies today, which is itself evidence against introducing gRPC or a web framework.
- *"Add rate limiting so a single caller can't overwhelm the server."* → resolved to a fixed-window limiter with `429`/`Retry-After` per RFC 6585, with the exact threshold exposed as a configurable flag rather than a guessed hardcoded number — turning a potentially-ambiguous number into a non-decision.

These are correct outcomes under the evidence policy, not the gate failing to fire — best practice and established convention are explicitly part of the evidence priority order, not a loophole around it.

**One request with no possible evidence-based answer:** *"Decide whether external API access should be free/unauthenticated or a paid, metered offering with billing, and implement whatever that decision requires."* The agent did real autonomous work first (an unrelated review-gate obligation left over from the prior tests, fixing two real bugs along the way), then stopped cleanly:
```
Overall: PARTIAL — review-gate fixes are done and verified; the actual task
(opening the API to other teams) is still blocked on your decision below.
…
(A) free-but-authenticated … vs (B) paid/metered with real billing …
Which one, and if (B), which payment provider/pricing structure?
```
One clear question, named options, nothing implemented on a guess.

## Cost and efficiency

Measured directly, not estimated:

| | Turns | Cost | Cache-creation tokens |
|---|---|---|---|
| Same trivial task, ECC disabled | 10 | $0.21 | 23,934 |
| Same trivial task, ECC enabled | 14 | $0.41 | 46,657 |

ECC's always-on agent/skill catalog roughly doubles cost on trivial work — this is paid once per session regardless of tier, and there is no config lever that removes it (`skillOverrides` does not affect plugin skills). It amortizes better on larger MATERIAL-tier work.

Hook latency, measured locally with no API calls involved: both hooks average 130–200ms per invocation, and a bare `python3` interpreter costs ~120ms to start on its own — almost all of the cost is interpreter startup, not hook logic. Stress-tested `require_material_review.py` against a synthetic 10,000-line/1.2MB transcript (a very long session) and it still completed in ~200ms and blocked correctly — the mechanism does not degrade with session length in the common case, since the transcript scan only runs when a candidate change actually exists.

Per-turn cost is structurally zero for both hooks — Claude Code hooks cost no context unless they return content, and these only emit anything when actively blocking.
