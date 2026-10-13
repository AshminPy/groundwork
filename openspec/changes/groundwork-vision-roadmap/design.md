# Design

## Context

See `proposal.md` (Why) for motivation. This section covers only the state that shapes the approach. Everything here comes from records that already exist: OpenSpec changes, release reports, `docs/VALIDATION.md`, the Claude Security report of 2026-10-12, telemetry, and the installed ECC. Nothing was re-tested for this plan, apart from running `openspec validate`.

### Where each requirement stands

| Req | Exists (evidence) | Runtime-verified | Material gap |
|---|---|---|---|
| R1 intake and management | M1 intake, risk checklist, ledger, `groundwork task` (`hooks/groundwork_tasks.py`; merged, unreleased) | 3 live `claude -p` runs (`add-task-lifecycle-gate` task 2.4) | No estimate, dependencies or prioritisation. One task per prompt. Not released. |
| R2 native OpenSpec | Tiers (`rules/engineering-workflow.md` §1–2). M1 creates the change and re-reads it on every check | VALIDATION 1.0.0 gate tests; M1 2.4 (plan revision, sync, archive) | Two main specs fail `validate --strict` (`health-dashboard`, `onboarding`: Purpose placeholder). Finished changes are not archived. |
| R3 execution and delegation | 10 playbooks; §6 and §6a; Integration Catalog | Routing 12/12 (VALIDATION 1.2.0) | Selection is advisory. Agent Teams: RUNTIME VALIDATION REQUIRED. Integrations are not tied to the task. |
| R4 evidence and quality | `evidence-policy.md`; review gate; M1 evidence-based completion | VALIDATION Phase 12; M1 2.4 | Labels and the ladder are advisory (accepted: rules, not code). |
| R5 safe autonomy | Push guard; M1 `ask`; §4 | M1 2.4 (four cloud `ask` prompts) | Bypasses F4–F8, F10–F12. F13 loosens settings to 0644. Routines get broad grants (F1–F3). |
| R6 continuity | Snapshot (git, OpenSpec, investigation file, worktrees, tasks); ledger | VALIDATION Phase 5; RR-2.4 §3; M1 2.4 | Task state unreleased. Quadratic regex in the snapshot (F9). |
| R7 integrations and DX | Catalog, statusLine, CLI, telemetry, dashboard, Copilot, Routines | RR-2.2/2.3/2.4 | statusLine shows no task or review state. `routines schedule` does not save the time. Dashboard labels clipped, rows unsorted. |
| R8 practical workflows | Playbooks, personas, repository-understanding checklist | Terraform, Helm/Flux and GitHub Actions fixtures (VALIDATION Phase 12) | No real non-production apply: RUNTIME VALIDATION REQUIRED (no target environment). Not addressed here. |
| R9 measurable improvement | Telemetry; ECC on/off cost table | NOT VERIFIED | No comparison against Claude Code alone. |

NOT VERIFIED, and not re-checked for this plan:
- Groundwork behaviour under `bypassPermissions`.
- Copilot on macOS (Copilot task 2.8).
- Jira posting from routines.
- Which ECC sub-hooks run under `hook_profile=standard` and which only under `strict`.
- Hook latency of ECC's hooks.

### ECC facts used by Decision 8

**How Groundwork depends on ECC:**
- No hook or script imports ECC.
- `require_material_review.py` accepts any reviewer whose `subagent_type` or `name` contains "review".
- `install.sh` runs under `set -euo pipefail` (line 24) and installs ECC unguarded (lines 71–72). A failed ECC install therefore aborts the whole install. This is INFERENCE from `set -e`; it was not run.
- `setup.sh --verify` counts a missing ECC as a failure (lines 664 and 690–691).
- `docs/ARCHITECTURE.md` lists two controls as **Enforced** that only ECC hooks enforce: "investigate before edit" (GateGuard) and "no `--no-verify`" (block-no-verify).

**What ECC costs:**
- `claude plugin details ecc@ecc` (2.2.1) reports 380 skills and commands, 68 agents and hooks on 7 events, at about **40,639 always-on tokens**.
- The same trivial task cost $0.21 and 10 turns with ECC disabled, and $0.41 and 14 turns with it enabled (`docs/VALIDATION.md` "Cost and efficiency"; one task, n=1).
- This planning session logged many GateGuard denials of ordinary actions: 60 "before the first Bash command" and 122 "destructive command detected" entries. Duplicate logging is possible.

**How much of ECC is used** (telemetry: 263 records from 3 sessions; every agent call came from one of them):
- 50 reviewer-agent records: code 19, security 16, python 15.
- 0 uses of `planner`, `tdd-guide` and `code-explorer`.
- 0 `Skill` calls. 0 ECC MCP calls.
- Whether anyone typed `/ecc:*` commands is NOT VERIFIED; telemetry does not capture them.

**What the earlier decisions found:**
- Upstream has no supported way to install a subset of ECC. `skillOverrides` skips plugin skills (`groundwork-2-enterprise-sre/design.md` §A.8).
- Decision D4 there chose the full install and ruled out forking or vendoring.

## Goals / Non-Goals

**Goals:**
- Deliver the target flow below with the fewest new parts. Each milestone closes a gap shown in the table above.
- Keep native OpenSpec as the only plan. Keep the ledger as identity, state and evidence only.
- Make every new behaviour read-only or guidance, except the M1 security fixes. Each new behaviour must be reversible through an existing kill switch, setting or `groundwork rollback`.
- Measure the R9 outcomes instead of asserting them.

**Non-Goals:**
- Replacing or forking Claude Code, OpenSpec or ECC.
- A custom multi-agent runtime, scheduler or message bus.
- A project-management app, Jira field sync or any database.
- New permanent agents. New approval gates for ordinary work.
- New paid services or third-party dependencies.
- A real non-production cloud apply (R8 gap). It needs a target environment the owner has not provided.
- Copilot command execution (`add-groundwork-copilot` tasks 3.1 and 3.2). It stays deferred.
- Dashboard dark mode and other cosmetic work.

## Target flow: `COR-123: Deploy GoldenGate VM in GCP`

| Step | Who does it | Exists now | Delivered by |
|---|---|---|---|
| 1. Recognise and track | Task gate intake records COR-123 as MATERIAL (cloud, infrastructure, data, cost, deployment) and creates the OpenSpec change | Merged | M1 release |
| 2. Inspect repo patterns | Claude, guided by the rules and the IMPLEMENT/PLAN playbooks | Advisory | M2 adds the intake ask |
| 3. Research prerequisites | Claude. Intake checklist: project, region, sizing, licence, replication | Merged | M2 puts prerequisites first in `tasks.md` |
| 4. Ask only what blocks | §4 autonomy rule; `groundwork task block` | Merged | — |
| 5. Estimate and break down | Claude writes `## Planning` and native `tasks.md` | Breakdown only | M2 |
| 6. OpenSpec plan | `/opsx:propose` (native) | Yes | — |
| 7. Select skills, agents, tools | Routing, §6/§6a; catalog readiness for GCP and Terraform | Advisory | M3 intake hint |
| 8. Implement in scope | Claude. `gcloud compute instances create` triggers the native permission prompt | Merged | M1 release (with bypass fixes) |
| 9. Verify | Commands under `## Verification`, recorded with a code fingerprint | Merged | — |
| 10. Independent review | Fresh-context reviewer subagent (Stop gate); ChatGPT/Codex at milestone gates | Yes | E makes it ECC-independent |
| 11. Report | Output contract | Yes | — |
| 12. Resume later | Snapshot and ledger; statusLine | Merged | M1 release; M3 statusLine |
| 13. Complete and archive | Evidence-based completion on native archive | Merged | M1 release |
| Several tasks | "COR-201 … COR-202 …" → two tasks; `groundwork task next` | No | M2 |

## Component responsibilities

| Component | Owns | Does not own |
|---|---|---|
| Claude Code | Reasoning, execution, native permissions, subagents, built-in review commands | Groundwork policy |
| OpenSpec (native) | The plan: proposal, specs, design, tasks, `## Verification`, `## Planning`, archive | Task state or evidence |
| Rules (5, always loaded) | Policy: tiers, evidence, autonomy, routing, output | Task-specific detail (playbooks hold that) |
| Playbooks (10, on demand) | Per-category workflow | — |
| Task gate and ledger | Intake, `ask` for sensitive actions, evidence, completion, readiness and order (M2) | Plan content |
| Review gate, push guard | Independent review before MATERIAL completion; no direct or forced push to protected branches | — |
| Snapshot | Fresh-session facts, including tasks and next task | Decisions (OpenSpec holds them) |
| Integration Catalog | Readiness facts and guidance | Activating anything |
| statusLine | Glanceable state from stdin, telemetry, cache and ledger | Probes, network |
| Telemetry and dashboard | Observed usage; R9 data | Judging quality |
| ECC (optional after E) | Specialist agents and skills when installed | Any Groundwork control |
| Owner | Priorities, approvals, merges, releases, production | — |
| ChatGPT/Codex | Architecture and independent review at milestone gates | Implementation |

## Decisions

### D1. Milestone order: M0, M1, R9 baseline, E, M2, M3, R9 re-run
- **Why:**
  - The owner set M1 as the immediate priority.
  - M0 is a hard prerequisite: the install and update code read the version from the top CHANGELOG heading, and `main` still carries a wrong 2.4.0 section.
  - Taking the R9 baseline right after M1 gives fresh, current evidence for E, which today rests on one trivial-task measurement.
  - E comes before M2 because it is small and independent, and it lowers the per-session cost of everything after it.
- **Alternative:** fold E into M3, keeping the owner's original M2-then-M3 sequence. This is an owner decision (see Owner decisions).
- Each milestone is its own release, with its own CHANGELOG entry, release report and owner approval. This roadmap change stays the plan of record across those releases.

### D2. M1 scope: ship as merged, plus security fixes and one routines bug
- **Fix in M1:**
  - F7, F8, F11, F12: task-gate bypasses. These are in the M1 feature itself. F7, F8 and F12 were reproduced.
  - F4, F5, F6, F10: push-guard bypasses. F4–F6 were reproduced.
  - F13: settings mode. Reproduced.
  - F1–F3: routines' broad `Bash(git *)` and the `news` routine's web plus Read grant. Medium severity.
  - F9: quadratic snapshot regex.
  - The `routines schedule` time bug. The 2.4.0 macOS upgrade note tells users to run that command.
- **Defer F14** (`jira_eod` MCP grant). It has low confidence, and narrowing it depends on per-tool MCP grants that have not been checked. It is recorded as a known limitation.
- **Each fix:**
  - Make the smallest change in place, plus a regression test built from the report's proof of concept.
  - The push guard and the task gate keep separate parsers. Merging them would refactor a released, enforced control during a release. The duplication is recorded as a trade-off.
  - Routine grants are narrowed to the git subcommands each routine's prompt actually uses. Each routine is then re-run live through the existing path.
- **Housekeeping:**
  - Archive `add-task-lifecycle-gate` (and the other finished changes) after the release is validated.
  - Write Purpose sections for `health-dashboard` and `onboarding`.
  - Refresh `docs/FUTURE-SCOPE.md` §7 and §14, which M1 made stale.
  - `add-groundwork-copilot` stays open: its remaining tasks are deferred features.

### D3. Planning facts live in the OpenSpec plan, in one `## Planning` section
- The estimate, `Depends on` and priority are read like `## Verification` (spec: `task-planning`).
- **Why:**
  - The M1 requirement already says Groundwork keeps no separate copy of the plan.
  - R6 says to use native artifacts and git.
  - One section is editable by the owner and survives sessions through git.
- **Alternatives rejected:**
  - Ledger fields set through a CLI: this creates a second plan store.
  - Jira fields: needs a fetch, credentials and an MCP dependency.
  - Separate `## Estimate` and `## Dependencies` sections: more parsing for no gain.
- STANDARD tasks have no OpenSpec change, so they carry no estimate. That matches their size.

### D4. Deterministic order; risk is not a sort key
- The six keys in the spec use only facts Groundwork holds.
- **Why risk is not a sort key:** it already decides authorization and validation depth. Doing high-risk work first (de-risking) and last (quick wins) are both defensible orders, so the owner's `Priority:` states intent explicitly instead.
- Claude may still argue for a different order in conversation. The command shows the reasons, so the recommendation is transparent and never enforced.

### D5. statusLine: a fifth data class, RECORDED
- M1's ledger is now a durable, authoritative source for task state and the latest review. That makes "review state UNAVAILABLE" in the statusLine spec out of date. The spec delta modifies the data-source contract.
- The statusLine shows the review as recorded. It never recomputes the code fingerprint, which would be an unbounded scan, so it never claims the review is current.

### D6. Integration hints at intake come from the existing cache
- Intake already detects GCP, AWS, Kubernetes, Terraform and Jira signals. A small static map links those signals to catalog integration names.
- Readiness comes from `integrations/cache.json` only. No probe runs in a hook, and the catalog's guidance-not-enforcement rule holds.
- **Rejected:** probing at intake. It adds latency and network access to every MATERIAL prompt.

### D7. R9 evaluation: small, repeatable and honest
- **Tasks:** three reference tasks on the existing fixture approach used for M1 live acceptance:
  - STANDARD: a seeded bug with a failing test;
  - MATERIAL: a COR-123-style Terraform VM change against a fake `gcloud`;
  - TROUBLESHOOT: a seeded failure with logs.
- **Arms:** plain Claude Code (empty config dir); Groundwork with ECC; Groundwork without ECC (baseline only). Same model, same prompts. `claude -p --output-format json`, 2 runs per task per arm.
- **Measured, from the JSON and transcripts:**
  - cost, tokens and turns;
  - questions asked;
  - plan before the first code edit;
  - verification run;
  - independent review;
  - sensitive commands run without a prompt;
  - claims that do not match the evidence;
  - fresh-session resume giving the correct next action.
- **Reporting:** the sample is small and model output varies, so results are reported as observed values with n and spread, never as significance.
- **Delivery:** a short runbook and a small script under `tests/eval/`. No framework, and no runs in CI.

### D8. ECC: make it an optional integration (DECISION record)

```
DECISION            Groundwork stops depending on ECC. New installs ask whether to install it
                    (recommended default: no). Existing installs keep it. A failed or skipped ECC
                    install no longer aborts install.sh or fails --verify. The rules name native
                    subagents and review commands first and ECC agents only "when installed".
                    The --no-verify block moves into the existing task gate (native `ask`).
                    "Investigate before edit" becomes advisory rule guidance. ECC is not modified.
EVIDENCE            Context § "ECC facts used by Decision 8": install.sh:24,71-72; setup.sh:664,690-691;
                    docs/ARCHITECTURE.md enforced-controls table; `claude plugin details ecc@ecc`
                    (~40,639 always-on tokens); docs/VALIDATION.md cost table ($0.21 vs $0.41);
                    telemetry usage counts; groundwork-2-enterprise-sre/design.md §A.8 and D4.
WHY                 Unique, material value: (1) the only enforcement of two controls; (2) language-
                    specific reviewer prompts (python-reviewer in 15 records). Duplicates native:
                    general reviewers (native subagent + reviewer prompt, /code-review,
                    /security-review), planner/explorer (Plan, Explore), session save/resume
                    (snapshot, ledger, investigation file, auto memory), cost/context monitors
                    (/cost, /context). Overhead: ~40.6K always-on tokens, about 2x trivial-task cost,
                    install fragility, frequent fact-forcing denials of routine actions (against R5).
                    Alternatives:
                    - Keep full (status quo): zero work, but keeps every overhead above.
                    - Selective subset: no upstream mechanism; would need vendoring, which D4 forbids.
                    - Remove from users' machines: destructive to their environment, and drops
                      value for users who rely on it.
                    Optional keeps ECC's value for those who choose it and removes the cost for
                    everyone else.
TRADEOFFS           Users without ECC lose the language-specific reviewer checklists (native
                    reviewers are general) and GateGuard's hard "investigate first" stop (now
                    advisory). The --no-verify control becomes `ask` rather than a hard block.
VALIDATION METHOD   The acceptance criteria below, plus the R9 baseline arms with and without ECC.
UNCERTAINTY         Cost data is n=1 on a trivial task (the R9 baseline replaces it). Hook latency
                    is not measured. Whether anyone uses /ecc:* commands is NOT VERIFIED. The
                    install-abort path is INFERENCE.
```

**Migration:**
- **Upgrade:** never uninstalls or disables ECC. `hook_profile` is kept when ECC is present.
- **New installs:**
  - `setup.sh` asks once and records the answer in `config.json`.
  - `--non-interactive` keeps the current machine's state.
  - `groundwork update` passes the detected state through.
- **Other changes:**
  - `rules/engineering-workflow.md` gets native-first wording.
  - The ARCHITECTURE enforced-controls table, README and `tests/test_setup.py` are updated.
- **Spec order:** archive `groundwork-2-enterprise-sre` first, so `ecc-capability-policy` is in the main specs. Then write E's MODIFIED delta against it.

**Acceptance criteria:**
1. A clean install with ECC declined completes. `--verify` passes. The full test suite passes.
2. In a fixture repository without ECC, a MATERIAL change reaches completion. Its independent review comes from a native subagent that emits `REVIEW RESULT`, and the review gate accepts it.
3. Without ECC, `git commit --no-verify`, `git commit -n` and `git push --no-verify` raise the native permission prompt.
4. Upgrading a machine that has ECC leaves ECC installed and enabled, with `hook_profile` unchanged.
5. No rule line names an ECC agent without a native alternative.
6. The R9 baseline reports always-on tokens and cost with and without ECC.

**Risks:**
- [Review quality drops for Python-heavy work without ECC] → The native reviewer prompt names the language. The R9 review-effectiveness measure checks this. The owner can keep ECC.
- [Edits happen without investigation once GateGuard is gone] → The rules, snapshot and review gate remain, and the R9 "plan before first edit" measure watches for it.
- [Owner prefers keeping ECC by default] → Decide at approval. Only the default changes; the work is the same.

### D9. Roles and review
- Claude implements and supplies evidence.
- A fresh-context reviewer subagent is the in-harness gate for each MATERIAL change. It must emit `REVIEW RESULT`, and Must-fix must reach 0.
- At each milestone gate, the owner relays the PR, diff and evidence to ChatGPT/Codex for architecture and independent review.
- The owner alone approves merge, tag, publish and any production action.
- Claude never self-approves and never reviews its own change as the only reviewer.

## Answers to architecture-quality §2

- **Likely to change:**
  - the ordering keys (D4);
  - the `## Planning` line formats;
  - the signal-to-integration map;
  - the R9 tasks.
  These live in one place each, as small tables in code or docs, not spread logic. The ECC default is configuration in `config.json`, not code.
- **Another provider, model or tenant:** a new integration is a catalog entry plus one map entry. A new model is an R9 run parameter. Ledgers are already separated per repository and per config directory (work and personal).
- **Automation:** the R9 runs are scripted. The release checks reuse existing commands. The pilot data comes from the ledger and telemetry, not manual logs.
- **Dependency failure:**
  - OpenSpec CLI missing → planning facts read from files still work; the change is not created, and intake says so (existing behaviour).
  - Cache missing → the hint says readiness is unknown.
  - Ledger unreadable → the statusLine omits the segment and `groundwork task` errors clearly.
  - ECC missing → no effect after E.
- **Observability:** `groundwork task list|show|next`, the snapshot, the statusLine, telemetry, the dashboard and release reports.
- **Testing:** unit tests per behaviour, the full suite, live `claude -p` acceptance in sandbox config directories with a fake `gcloud`, an owner macOS smoke test, and the owner pilot.
- **Deploy and rollback:** the release process, then `groundwork update`. Rollback is `groundwork rollback`. Kill switch: `GROUNDWORK_TASK_GATE=off`. The statusLine `task` section can be hidden.
- **Security boundary:**
  - Hooks run locally with no network access.
  - The ledger lives outside repositories, and file tools cannot write it.
  - No credentials are stored.
  - M1 narrows routine grants.
  - E keeps `--no-verify` behind `ask`.
- **Scaling and cost:** ledger reads are per repository and small. `next` is O(tasks²) at most, for tens of tasks. E removes about 40K tokens per session for users without ECC. R9 runs cost API usage: a few dozen runs per evaluation. That cost is UNVERIFIED until the baseline is run and reported.

## Testing and real-world validation strategy

| Milestone | Unit / integration | Live / real-world |
|---|---|---|
| M0 | `openspec validate --specs --strict`; diff against the `v2.4.0` tag | — |
| M1 | One regression test per finding (from the report's proof of concept); full suite `python3 -m pytest tests -q --ignore=tests/mutation`; no mutation suite exists for the gate or push guard; regression tests stand in | Clean install, 2.4.0 → 2.5.0 upgrade, rollback in sandbox config dirs. Live COR-123 acceptance with real `claude -p` and a fake `gcloud`. Re-run each narrowed routine. Owner macOS smoke test. Two-week owner pilot. |
| R9 | Script dry run on one task | 3 tasks × 3 arms × 2 runs |
| E | `test_setup.py` updates; `--no-verify` gate tests | Clean install without ECC; upgrade with ECC; MATERIAL fixture reaching completion with a native reviewer |
| M2 | Parser, readiness, cycle and order tests; multi-key intake tests | Live two-ticket run: both recorded, `next` recommends the prerequisite, fresh-session resume |
| M3 | statusLine segment tests; no-subprocess assertion; intake hint tests | Live statusLine render timing; COR-123 intake shows the GCP hint; dashboard screenshot check |

Unit tests prove logic only. Each milestone is reported as complete only with its live evidence. Anything that cannot be run is labelled RUNTIME VALIDATION REQUIRED.

## Safety and rollback

- Milestone releases are reversible with `groundwork rollback`, which is tested in every release.
- New task behaviour is read-only or guidance. The only new `ask` is `--no-verify` (E). `GROUNDWORK_TASK_GATE=off` switches the gate off.
- Security fixes only tighten controls. Each one has a regression test, so a later change cannot silently reopen it.
- No real cloud mutation happens during validation; a fake `gcloud` is used. No production access.
- E never removes ECC from a machine.
- The owner approves every merge, tag, publish and deployment.

## Effort estimates

These are estimates, not commitments. They count working days of implementation and validation. They exclude owner review waits, ChatGPT/Codex review turnaround and the pilot's calendar time.

| Item | Estimate | Confidence | Basis |
|---|---|---|---|
| M0 | 0.25–0.5 d | high | Docs copied from the tag |
| M1 | 3–6 d | medium | The task-gate change needed 4 reviews (2 sent it back); Copilot needed 10 rounds and 42 MUST FIX. The 2.4.0 release validation took about 1–2 d. |
| R9 baseline | 1.5–3 d | low | New script and fixtures; run time and cost not yet measured |
| E | 1.5–3 d | medium | Install, setup and merge changes, tests, two live installs |
| M2 | 4–8 d | low–medium | Intake classifier changes have needed several review rounds before |
| M3 | 3–5 d | low–medium | statusLine and intake changes are small; live timing and screenshots add time |
| R9 re-run | 0.5–1 d | medium | Reuses the baseline script |
| **Total** | **13.75–26.5 d** | low–medium | Plus a two-week pilot after M1 |

## Risks / Trade-offs

- [Hardening breaks ordinary commands, so the gate asks too often] → Every fix gets a false-positive test using ordinary commands. The pilot counts unneeded prompts.
- [The `## Planning` format is ignored or mistyped] → Lines that cannot be parsed are reported. The intake guidance shows the exact format. The plan stays valid without it.
- [`next` looks authoritative] → It always prints its reasons and calls itself a recommendation. The owner's `Priority:` overrides it.
- [Multi-key intake records noise] → Only keys that head their own clause and ask for work count. `groundwork task cancel` drops a wrong one.
- [R9 numbers are over-read] → Report n and spread, and label results as observed.
- [Archiving old changes surfaces spec conflicts] → Archive one change at a time and run `validate --specs --strict` after each. Git history is the rollback.
- [Parser duplication between the push guard and the gate stays] → Accepted for now. Consolidation can be revisited when either parser next changes materially.

## Migration Plan

1. M0 lands as a docs-only PR to `main`.
2. Each later milestone goes through the same steps:
   1. a branch and an OpenSpec-tracked implementation;
   2. tests and live validation;
   3. a fresh-context review to Must-fix 0;
   4. a ChatGPT/Codex review at the gate;
   5. owner approval, then the release;
   6. `groundwork update` for users.
3. Rollback is `groundwork rollback` to the previous release.
4. This change is archived after M3 ships and the R9 re-run is reported. If the owner stops after any milestone, the unshipped milestones' deltas and tasks move to a follow-up change before archiving, so the main specs never claim behaviour that has not shipped.

## Owner decisions

1. **M1 security scope:** fix F1–F13 in 2.5.0, deferring F14 (recommended), or ship M1 with only the task-gate fixes.
2. **ECC:** make it optional with the default "no" for new installs (recommended), make it optional with the default "yes", or keep the full install as today.
3. **Where E sits:** after the M1 release and R9 baseline (recommended), or folded into M3 to keep the original M2-then-M3 order.
4. **Pilot overlap:** start M2 during the two-week M1 pilot and merge it only after the pilot findings are triaged (recommended), or wait for the pilot to finish.
5. **R9 cost:** about 18 headless runs for the baseline use API usage on the owner's account. Approve before the first run.
6. **M0 method:** a docs-only PR that copies the 2.4.0 CHANGELOG section and release report from the tag. This avoids the release-branch merge that was blocked earlier.

## Open Questions

- The exact read-only git subcommands each routine needs. They are found by reading each routine's prompt in M1; this does not change the approach.
- The staleness threshold for showing cache age in the intake hint. It reuses the statusLine's documented threshold unless that proves unsuitable.
