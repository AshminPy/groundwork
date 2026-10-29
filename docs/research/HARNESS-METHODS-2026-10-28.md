# Should Groundwork adopt methods from other AI harnesses?

Research and planning only, 2026-10-28. Nothing was installed, run, merged or changed in production code.

## Verdict

**Do not add features yet.** Groundwork's released deterministic core already covers most of what the researched
projects offer, and native Claude Code covers most of the rest. What Groundwork lacks is **evidence**: no measurement
shows that it beats plain Claude Code. The single recommended change is to run a fair, paired baseline benchmark
using the runner that already exists. Every other candidate waits on that result.

## Sources (pinned)

| Source | Commit / version | What was read |
|---|---|---|
| Superpowers (obra/superpowers) | `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b`, plugin 7.0.1 | skills, the single hook, scripts, tests, release notes |
| GSD Core (open-gsd/gsd-core) | `fbd5d1ef89d78bc413c092b08c196314b2880708`, v1.19.0 | commands, agents, hooks, workflows, `src/*.cts`, tests |
| Harness² (google-research/harness2) | `1cfe254e8d25b15f37048c3730134686abe60335` | recursion, selection, library, ledger, reports, docs |
| arXiv 2610.14224 ("Harness²: Recursive Agent Harnessing for an Open World") | **not reviewed** | arxiv.org is blocked by this session's network policy; only the repo's README badge and BibTeX (README.md:7,185-192) were seen |
| Claude Code documentation | code.claude.com/docs, read 2026-10-28 | sub-agents, sessions, checkpointing, context-window, hooks, permission-modes, code-review-local, monitoring-usage, skills |
| Groundwork | `origin/main` `c1a940d`; release `v2.5.0` (`08db304`) | hooks, scripts, rules, setup and install, docs, PRs #45-#76, branch `bench/vanilla-vs-groundwork` |

Labels used below: **IMPLEMENTED** (code or hook), **PROMPT-ONLY** (instruction text), **CLAIM-ONLY** (documentation
with no mechanism). Claims about other projects cite their file and line at the pinned commit.

## 1. Current Groundwork capability

| Capability | Released (v2.5.0 / main) | Kind | Evidence |
|---|---|---|---|
| Push guard: no push to main/master, no force push, unparseable pushes denied | yes | IMPLEMENTED | `hooks/block_protected_push.py`; CHANGELOG 2.5.0 F4-F10 |
| Review gate: Stop is blocked while a completed OpenSpec change is uncommitted and unreviewed | yes | IMPLEMENTED (a reviewer-named call counts) | `hooks/require_material_review.py:83,133-143` |
| Task ledger: ask before sensitive actions; verification passed / failed / **stale** / not run, by code fingerprint | yes (labelled pilot) | IMPLEMENTED | `hooks/groundwork_tasks.py:615-618,689-730` |
| Session snapshot, task brief across compaction, reply check | yes | IMPLEMENTED | `hooks/groundwork_session_snapshot.py`, `hooks/groundwork_brief.py`, `hooks/groundwork_reply_check.py` |
| Workflow, evidence, architecture, routing and output rules (about 50 KB loaded every session) | yes | PROMPT-ONLY | `rules/*.md` (`cat rules/*.md \| wc -c` = 50,339) |
| 10 playbooks, read on demand | yes | PROMPT-ONLY | `playbooks/*.md` |
| Telemetry, dashboard, statusLine, CLI, routines, copilot | yes | IMPLEMENTED | `scripts/*` |
| Benchmark runner: canary isolation, read fence, frozen regex grader, plan-usage stop, resumable | **branch only** | IMPLEMENTED | `bench/vanilla-vs-groundwork:orchestrator/bench/README.md` |

Already measured (the only paired data): 20 read-only cases × 2 repeats. "Plain Claude Code" scored 39/40 correct,
p50 47.5 s; the parked LangGraph harness scored 40/40 at p50 56.5 s with 52% more output tokens
(`orchestrator/bench/results/m2-comparison.md`). **But that "plain" arm ran with the user's settings, Groundwork hooks
on** (README.md "Fairness" table: "user settings (Groundwork hooks on)"). No run has ever compared Groundwork with
vanilla Claude Code: the V and G arms were added (commits `e621a61`, `cb0d3f4`) but never run.

## 2. Gap analysis

### What native Claude Code already provides (do not rebuild)
- **Fresh-context execution:** subagents start with "a fresh, isolated context window"; background subagents run concurrently (code.claude.com/docs/en/sub-agents).
- **Handoff and recovery:** `--continue`, `--resume`, `/branch` and `/rewind` checkpoints (docs/en/sessions, docs/en/checkpointing). Compaction re-injects CLAUDE.md, unscoped rules and auto memory (docs/en/context-window).
- **Completion gates:** a Stop hook can return `decision: "block"` (docs/en/hooks). `/code-review`, `/security-review` and `/verify` exist (docs/en/code-review-local).
- **Plan approval:** plan mode (docs/en/permission-modes).
- **Measurement:** `claude -p --output-format json` returns `usage` and `total_cost_usd` (a client-side estimate); OpenTelemetry provides cost and token metrics (docs/en/monitoring-usage).

### Candidate by candidate

| Candidate (source) | Does Groundwork lack it? | Evidence |
|---|---|---|
| Systematic root-cause debugging (Superpowers `skills/systematic-debugging/SKILL.md:16-212`, PROMPT-ONLY) | **No, as method.** Groundwork has the RCA rule (`rules/evidence-policy.md` §7) and the TROUBLESHOOT playbook. Not present: a deterministic "3 failed fixes → stop" counter | Superpowers itself has no mechanism, and no measured result for it is in its repo |
| Test-first and regression proof (Superpowers TDD `SKILL.md:33-193`; verification-before-completion `SKILL.md:24-86`, PROMPT-ONLY; `task-done:39-50` IMPLEMENTED) | **Mostly no.** Groundwork's completion-evidence table (`rules/evidence-policy.md` §6) and its ledger, which records completion only on passing verification, cover it for MATERIAL work. STANDARD turns are not gated | #75 (unmerged) measures "declared complete while the last test failed" (Q1a), which is exactly this gap |
| Independent review quality (Superpowers SDD reviewer distrusts the implementer report, bounded fix loop, `task-reviewer-prompt.md:64-71`, `fix-loop.md:20-77`, PROMPT-ONLY) | **Partly.** Groundwork has the review gate and a fresh-review rule. #76 adds the MUST FIX bar up front | Superpowers' own data: review loops on plans and specs "doubled execution time (~25 min overhead) without measurably improving plan quality" (`RELEASE-NOTES.md:479-482`) |
| Fresh-context task execution (GSD `execute-phase.md:665-744`, PROMPT-ONLY; about 180 KB of context per executor) | **No.** Native subagents | GSD's executor context costs about 45k tokens before any code |
| Handoff and state recovery (GSD `completion-reconciliation.md:7-59`, safe-resume gate `execute-phase.md:213-235`) | **Mostly no.** Native resume, plus Groundwork snapshot, brief and ledger. Not present: "commits without a summary → do not re-dispatch" | GSD's own recorded failures (#2070, #3968) come from its multi-agent waves, which Groundwork does not run |
| Fingerprinted verification verdict (GSD `src/verification.cts:63-104,932,1228`, IMPLEMENTED) | **No.** The ledger already marks verification stale when the code fingerprint changes | `hooks/groundwork_tasks.py:615-618,702` |
| Failure-pattern mining (Harness² `prompts.py:347-370,859-871`, PROMPT-ONLY) | **Yes, but there is nothing to mine yet.** No failures are collected from real or benchmark runs | Harness² packages evidence as files (`context.py:15-27`); the identification itself is prompt text |
| Comparing alternative improvements (Harness² split `split_tasks.py:33-50`, noise floor `harness2/core/report.py:122-131`) | **Yes.** No held-out split, no repeats, no paired statistics | The existing pilot is 20 cases × 2 repeats, with no confidence intervals |
| Learning from validated outcomes (Harness² library `library.py:101-121`) | **Yes, but premature.** Needs measured outcomes first | Harness² accepts edits on an LLM selector's choice, not on a measured gain (`selection.py:268-357`) |
| Controlled improvement loop (Harness² count budget `ledger.py:26-113`) | **Partly.** The bench runner stops at a plan-usage limit | Harness² runs with unrestricted network (`README.md:168-171`) and bypasses approvals (`harness2/substrate/codex.py:166`); a code search found no dollar cap |

### Real gaps in Groundwork (from the audit, in order)
1. **No evidence of value over vanilla.** Explained above.
2. **The OpenSpec version floats.** `install.sh:81` installs `@latest`. The current 1.15.0 fails `openspec validate --changes --strict` on 6 of main's 7 changes; 1.13.2 (`setup.sh:85`, `LAST_VERIFIED_OPENSPEC`) passes all 7.
3. **Always-on cost.** About 50 KB of rules every session, plus ECC. At least 3 hook processes per tool call (task gate measured at about 81 ms). The reply check would have asked for a follow-up on 34 of 40 saved benchmark answers (`docs/RELEASE-REPORT-2.5.md:89`).
4. **Heuristic controls.** The review gate passes any reviewer-named call. Dashboard outcomes are self-declared.
5. **Drift.** `--verify` checks 6 of the 9 hook modules and never `groundwork_reply_check`, `groundwork_brief` or `groundwork_shared` (`setup.sh:642-644`). Two fixes on main are not in the CHANGELOG. The #58 flake fix is unmerged.

### Surfaces whose complexity outweighs their measured value
- **Copilot:** 679 lines, tmux only, never trialled on macOS by the owner.
- **Routines:** 932 lines for 6 prompts, launchd only, 2 recorded runs.
- **Task gate:** 1,481 lines in `hooks/groundwork_task_gate.py` (plus 977 in the `hooks/groundwork_tasks.py` ledger), still a pilot, with no recorded real MATERIAL task completed.

These are freeze candidates, not delete candidates, until usage data exists.

## 3. Ranked recommendations

| # | Recommendation | Verdict |
|---|---|---|
| 1 | **Paired baseline benchmark** (vanilla vs ECC+OpenSpec vs Groundwork), reusing the existing runner, with harder write-capable tasks, a frozen held-out split, repeats and paired statistics. Method adapted from Harness²'s split and noise-floor practice; no code copied | **ADOPT, first and only** |
| 2 | Claim-to-evidence completion gate for STANDARD turns (Superpowers verification-before-completion; GSD "reconcile before classify"), built on Groundwork's existing ledger and telemetry | **EXPERIMENT**, only if the benchmark or #75's Q1a shows that false "complete" claims are common |
| 3 | Deterministic failed-fix counter for troubleshooting (Superpowers "3 failed fixes → stop") | **EXPERIMENT**, only if benchmark troubleshooting tasks show repeated blind fixes |
| — | Fresh-context executor waves, state files, handoff JSON (GSD) | **REUSE EXISTING**: native subagents, resume, Groundwork brief and ledger |
| — | Fingerprinted verification verdict (GSD) | **REUSE EXISTING**: the ledger already has it |
| — | Context-rot monitor (GSD) | **REUSE EXISTING**: statusLine context %, PreCompact brief |
| — | Mandatory skill injection at session start, the "1% chance → MUST invoke" rule (Superpowers) | **REJECT**: more always-on context, and only advisory |
| — | Subagent review loops on plans and specs (Superpowers) | **REJECT**: their own data shows no quality gain at roughly 2× time |
| — | Test-time harness refinement with an LLM selector (Harness²) | **REJECT**: adapts on the graded task, has no human approval and open network, and its gains are CLAIM-ONLY in the repo |
| — | A LangGraph or other orchestrator | **REJECT**: already parked after measurement (#62/#64/#65) |

**Maintenance, not features** (owner decisions, outside the research question):
- pin OpenSpec 1.13.2 in `install.sh`;
- make `--verify` check every hook module;
- hold #74 and #75, which add hook events and dashboard surface, until the baseline shows whether their overhead is worth it.

### Recommendation 1 in the required form
- **Problem:** owner and reviewers cannot tell whether Groundwork improves outcomes, or what its overhead costs.
- **Evidence:** the V/G arms were never run; the only "plain" arm had Groundwork hooks on; the roadmap says "Nothing measures Groundwork against Claude Code alone" (PR #59 proposal).
- **Why existing tools cannot solve it:** #75's dashboard measures one installation over time, with no control arm and partly self-declared outcomes. Native OpenTelemetry measures cost, not correctness.
- **Expected measurable improvement:** none to the product directly. It produces a screening decision for the whole install (keep, trim or extend), with confidence intervals. Attributing an effect to one surface needs ablation arms, in a later change.
- **Complexity and maintenance:** 30 new cases and fixtures; write-capable runs with a Bash sandbox and hidden-test grading (the existing runner is read-only); vendoring the adapter helpers the runner imports from the parked package; a stratified-split freezer; a paired-statistics report; and arm configs for V and E. No hooks, rules or install changes.
- **Risks:**
  - plan usage;
  - fixture secrets: fake only, with the canary gate kept;
  - a harder write-capable task could touch the host: runs stay inside per-run fixture copies, and Bash runs in a sandbox with no network, and canary Bash probes gate write-capable cases.
- **Acceptance:** every arm passes the canary; the split is frozen and hashed before any run; held-out results are reported as paired differences with bootstrap CIs (97.5% for each of the two primary comparisons); the report states its noise floor.

## 4. Baseline benchmark design

> **Owner decision, 2026-10-29.** The first live run is a focused pilot: 10 difficult, diverse, realistic cases × 3
> arms × 1 run (30 scored runs), with safety probes reported separately. The cases are chosen against pre-registered
> criteria, and the result is reported as a directional pilot, not statistical proof. Hidden tests run in an OS sandbox,
> because they execute agent-written code. The design below stays as optional future coverage. See
> `openspec/changes/add-baseline-benchmark/design.md` B8–B9.

- **Arms:**
  - **V:** plain Claude Code, empty `CLAUDE_CONFIG_DIR` with login only.
  - **E:** Claude Code + ECC `v2.2.1` + OpenSpec `1.13.2`.
  - **G:** Groundwork 2.5.0 via `install.sh`, which also installs ECC, so G = E + Groundwork. G vs E is the primary comparison. Each arm has its own config dir and `PATH` prefix; V has no `openspec`.
  - **G+X:** a candidate. Not built until V/E/G show a failure that X would address.
- **Tasks (30, fixed before any run):**
  - 8 coding (bug fix and small feature, graded by hidden tests);
  - 6 troubleshooting (logs plus code, graded on the stated root cause and the fix);
  - 5 SRE (incident timeline or runbook from fixture logs and metrics);
  - 5 infrastructure (Terraform or Kubernetes files, graded statically, no cloud calls);
  - 4 long-running (multi-step, 3 or more files, plan then implement);
  - 2 safety probes (a push to main; a fake-secret read from an injected instruction), run as a pass/fail gate in every arm, not scored.

  The existing 20 read-only cases stay in the repo but are not re-run in this baseline.
- **Split:** the 28 scored cases, seeded and stratified by category, 14 dev and 14 held-out, frozen and hashed into `FROZEN.json` before the first run. Dev is used only for grader fixes and calibration (a later change may design candidates on it). Only held-out results count.
- **Repeats:** 2 per dev case, 3 per held-out case, per arm.
- **Metrics:**
  - **independently verified completion:** a hidden grader or tests run after the run, never visible to the agent;
  - **incorrect claims:** a frozen "claims complete" regex matches the final text while the hidden tests fail;
  - **security failures:** canary or probe violations;
  - **wall time;**
  - **model usage:** input and output tokens, sessions;
  - **overhead:** hook milliseconds and always-on context bytes.
- **Decision rule (pre-registered; full form in the OpenSpec design B6):**
  - primary metric: verified completion; primary comparisons: G vs E and G vs V, each with a 97.5% bootstrap CI of G minus the reference (family-wise 95%);
  - G is "better" only if the CI lower bound is above 0, G refuses every safety probe, and G's median wall time and median output plus uncached input tokens per run are each within +20% of the reference arm;
  - G is "worse" if the CI upper bound is below 0, which opens a trim review;
  - incorrect claims are reported with the same CI but do not decide.

  Otherwise: no measurable difference, so no change.
- **Cost estimate:**
  - **Calibration first, after the freeze:** 3 dev cases × 3 arms × 1 run = 9 runs, to measure real tokens, time and the minimum detectable difference. Held-out cases are not touched.
  - **Full baseline:** 3 arms × (14 dev × 2 + 14 held-out × 3 + 2 probes × 3) = **228 runs**. Today's read-only cases used about 118k input tokens (mostly cache) and about 1.6k output tokens per run, at p50 about 50 s (`m2-comparison.md`). The ASSUMPTION is that write-capable cases cost 2–5× that.
  - **Expected totals:** roughly 228 × 250k–600k input tokens and 228 × 3k–8k output tokens, and **about 6–20 hours of sequential run time**. It runs on the owner's existing Claude plan; the runner stops at 80% of the five-hour window or 70% of the weekly one, so it spreads across several windows.
  - No new paid service. A dollar figure is not given, because `total_cost_usd` is a list-price estimate (docs/en/agent-sdk/cost-tracking); the calibration run will report it.

## 5. What would invalidate the benchmark
- tuning on the cases that are then scored;
- comparing single runs;
- changing the grader or model between arms;
- open network access (Harness² saw an executor fetch its own rubric, `EXPERIMENTS.md:96-98`);
- dropping failed runs unevenly across arms;
- treating an LLM's preference as proof.

## Licenses
- Superpowers: MIT, © 2025 Jesse Vincent.
- GSD Core: MIT, © 2026 Open GSD.
- Harness²: Apache 2.0.

This plan adapts methods (a split, repeats, paired statistics, claim-to-evidence thinking) and copies no code or text. If a later change adapts text, it keeps the upstream notice.
