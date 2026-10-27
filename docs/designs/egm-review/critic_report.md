# Stage 7: Critic Review report

Target: `docs/designs/groundwork-architecture.md`, FeatureRange lines 1-287
Reviewers: `egm:egm-design`, `egm:egm-structural`, `egm:egm-style`. Standard: `feature-spec-standard.md` (design, structural).
The design reviewer was told not to repeat Stage 5 findings (event counts, Change B cost basis, env-var hook command).

## Design critic (egm-design)

No Blockers. Eleven Major, two Nit findings. The reviewer read the persona from `agents/design_critic.md` and only grep-checked `merge_settings.py`, `install.sh` and `groundwork_reply_check.py`.

| # | Sev | Lines | Finding |
|---|---|---|---|
| D1 | Major | 69-70, 104, 111, 227-229 | G6 and CUJ 1 promise macOS or Linux, but scheduling (report job, six routines) is launchd-only. `install.sh:114` itself says automatic runs "need macOS launchd". Linux is a degraded install and the spec does not say so. Name the gap in G6/Non-Goals, or add a systemd/cron path to Change A. |
| D2 | Major | 26-29 | ECC is pinned to `v2.2.1`, but OpenSpec is `npm install -g @fission-ai/openspec@latest` (`install.sh:81`). A new upstream release could break CUJ 1 or CUJ 5 (`require_material_review` reads OpenSpec state). No pin decision, no compatibility test, no risk entry, no ECC upgrade policy beyond "re-test". |
| D3 | Major | 135-138, 196, 203-205 | The gate returns `ask` for sensitive actions and also converts its own errors into `ask`. Six scheduled `claude -p` routines are non-interactive (line 228). What `ask` does there (auto-deny, hang, fail) is not stated or tested. A broken gate could silently stall every routine. |
| D4 | Major | 203-205, 258 | Fail-open for every hook except `task_gate`, including `block_protected_push.py`. A crash, missing Python, or Python < 3.10 turns the deny into silence (bare `python3`). The asymmetry is not justified. Recommend "safety hooks degrade loudly" (SessionStart self-check). The deny is a command-string match; bypasses (`git -C`, aliases, `HEAD:main` refspecs, other tools) are not listed. State matcher coverage and limits. |
| D5 | Major | 258-259 | "Telemetry never reads `tool_input`/`tool_response`" covers only the telemetry hook. `task_gate` inspects tool input on every call and writes `tasks/<repo>/<KEY>.json`; brief and investigation files hold free text. The privacy claim should cover everything under `<config>/groundwork/`, with retention and the 0600 permissions. Q3 (unbounded telemetry) is a privacy gap, not only an open question. |
| D6 | Major | 44-47, 58-62, 222-226 | Success metrics rest on a weak benchmark: 20 questions, probably one run, same author builds checks and benchmark; G1 "18/20" is partly circular (the hook enforces it). No metric for hook cost (blocked turns, extra Stop round-trips, false blocks; Q2 shows false positives). G3 and G4 have no measure; G5 is "goes down" with no baseline. |
| D7 | Major | 233-252 | Alternatives are strawmen or past work. Missing: ship rules as a Claude Code plugin (may solve Change A natively); native skills / on-demand loading instead of 50 KB always-on rules; a smaller hook set (15 entries, two processes per tool call). Alt A compares to rules-only, but the real question is hooks versus fewer hooks. Alt B's "worse on every measured axis" conflicts with 39/40 vs 40/40 being a tie within noise. Alt C is a rejected feature, not an alternative. |
| D8 | Major | 51-54, 261-263 | Both arms 20/20 correct; Groundwork costs +58k input tokens per answer (about 3.8x) and +29% time, and consumes subscription quota. No acceptable cost ceiling or justification. Task-gate cost and "four Python processes per Stop" are unmeasured. |
| D9 | Major | 85-98 | Q1, Q2, Q4 define the product boundary and need a decision, owner, or explicit deferral. Q1: the owner's own rules conflict with Groundwork's output contract and the ECC share is unmeasured (the largest cost driver, ignored by Change B). Q4: usage tracking records nothing on the author's own machine, so G5 cannot be measured where it matters. |
| D10 | Major | 123-130, 209-217 | Brief file is keyed `<branch>-<sha8>.md`; sha8 changes every commit, so the brief may go stale or fork per commit (continuity across commits unexplained). Injected text is "framed as data" (line 260), which is not a full mitigation for prompt injection via repo content or branch names. Cross-hook file state has no locking or concurrency story (two sessions, same repo and branch; ledger edited by hook and Claude). |
| D11 | Nit | 94-95, 278-284 | Telemetry retention and doc drift appear both as Future Improvements and Open Questions. `usage.jsonl` already trims (8 days over 1 MB), so Q3 should propose a default. CUJ 1 says `--verify` "reports every Groundwork hook as present and registered" but line 280 says it checks six files and four events: the spec contradicts its own acceptance criterion. |
| D12 | Nit | 76-79, 244-245 | Orchestrator numbers cited from a parked branch file; benchmark cited only by `claude.ai/artifact` link. Record the numbers and the method (sample size, runs, judge) in the repo. |

Standard compliance: the Risks & Mitigations section is missing; risks, failure modes, scale limits, dependency risk and the headless `ask` case are scattered or absent.

## Structural critic (egm-structural)

No Blockers. Four Major, six Nit. All five required areas are present (Problem, Goals/Non-Goals, Architecture, Alternatives, risks); the defects are structural gaps.

| # | Sev | Lines | Finding |
|---|---|---|---|
| S1 | Major | 256-265 | No Risks & Mitigations section. Closest material is scattered (three-bullet NFR block, fail-open paragraph 203-205, Q2/Q3, "Hooks are not a sandbox" non-goal). None pair a risk with a mitigation. Add an H2 with risk, impact, mitigation. |
| S2 | Major | 276-284 | "Future Improvements" holds known limits and risks (doc drift, telemetry retention, uninstall leftovers). "Additional Resources" and "Future Improvements" are H3s that read as NFR children (a rule at 267 separates them). Promote to H2 or fold into the Risks section. |
| S3 | Major | 233-252 | Alternatives cover only the as-built system. Changes A and B (title, Overview lines 31-34) have no Technical Plan subsection and no alternatives in the feature half. Add "Proposed changes" under Technical Plan with alternatives for each. |
| S4 | Major | 100-146 vs 148-231 | CUJs describe only as-built behavior. Change A appears only as a clause in CUJ 1; Change B has no CUJ. Goals G5 and G6 have no journey tying them to the plan. |
| S5 | Nit | 83-98 | Open Questions come before the Technical Plan but use terms (hooks, status line, telemetry) defined later. Move after the plan or alternatives. |
| S6 | Nit | 153-174 | Box-drawing lines in the Components diagram have uneven width; may render misaligned. |
| S7 | Nit | 8, 254, 266, 286 | Horizontal rules used inconsistently. |
| S8 | Nit | 31-33, 273, 276 | Benchmark URL bare and repeated; other references are code spans, not links. |
| S9 | Nit | 191-201 | Hooks table "Can block?" mixes vocabularies (`deny`, `ask; deny on ledger edits`, `block (no stop_hook_active check)`, `block once`, `no`, `never`). Heading says 15 entries; table lists 7 files, with no bridge. |
| S10 | Nit | 3-8 | Header block is consistent with the standard; no finding. |

## Style critic (egm-style)

No Blockers; six Major, 26 Nit. No separate standard was supplied.

Major:
- ST1 (12-13): "every answer accurate ... cheap in tokens" is unmeasurable, and "cheap" contradicts the +58k-token data.
- ST2 (38-39): "most of the time" and "reliably" are not quantified; the benchmark shows V at 20/20 correct. State specific gaps with figures (for example V evidence section in 1/20).
- ST3 (44-46): "every check that can be made deterministic" is an absolute claim; Non-Goals (line 79) reject the citation-content check.
- ST4 (85-90): Q1 is one dense run-on that mixes two questions (who owns the cost; whether to warn on duplicates). "some of it says it is superseded" is vague.
- ST5 (246): "worse on every measured axis" overstates (39/40 vs 40/40, slower, 52% more output tokens). Say "lower score, slower, more output tokens".
- ST6 (257-263): "about 35 ms each, measured for telemetry" is applied to the task gate without support; "about 12.6k tokens" has no stated method (likely bytes / 4).

Nits (grouped):
- Wording: "It aims to" (12); "sits on top of" (26-29); "found by" and undefined labels A/B before use (31); "parked" (76); "lives only on branches" (78, 80); "without saying so" (283); "under load" unsupported (238; the measurement is 31 of 51 tool turns).
- Absolutes: "Every hook fails open" followed by an exception (203); "never silently allows" (205); "zero runtime cost" contradicts 12.6k tokens per request (237).
- Missing targets: G1 and G2 give current results but no target (60, 62); G4 mixes "owner" and "user" (65, 138); G5 "go down" has no size (68).
- Terseness or time-bound phrases: "seen on 2026-10-27 in this session" (91); Q4 "Accept, or offer a wrapper?" (97); "chars" (127); "2500 + 700 chars" ambiguous.
- Units and counts: KB mixed with exact bytes (154, 179-187); hooks, hook files and entries mixed (278-281, 191).
- Claims without cited source: "Node 20.19+, Python 3.10+" (101-111); six scheduled jobs not named (228).
- Repetition: 852 citations / 0 real errors stated at 80 and 251; Q3 repeated at 282; negative requirement at 111 should be stated positively (each `<config>` keeps its own launchd label).
- Single bare URL mid-sentence (31-34), repeated at 273.

## Cross-reviewer overlap (for consolidation)
- Missing Risks & Mitigations section: D (standard compliance), S1, S2.
- Benchmark/metric weakness: D6, D8, ST2, ST5.
- Changes A and B absent from feature half: S3, S4.
- Linux vs launchd: D1 (also Stage 6 #7).
- Fail-open and absolute wording: D4, ST3, nit on line 203.
