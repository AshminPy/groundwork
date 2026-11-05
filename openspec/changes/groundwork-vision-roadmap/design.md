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
- The order fixes when work **merges**, not when it may start. M2 development can run during the M1 pilot, the R9 baseline and E. Only M2's merge waits on the relevant pilot findings (D10).

### D2. M1 security release criteria: severity and evidence
- **Release blocker.** A finding blocks 2.5.0 when either of these holds:
  1. it is **verified exploitable**: reproduced at runtime against the code being released; or
  2. it is **MEDIUM or higher**, confirmed by all three verification lenses, with medium or higher confidence.

  Every release blocker is fixed before the release. Each fix comes with a regression test built from the report's proof of concept.
- **Not a blocker.** Any other finding is either fixed in the release because it sits in code the release already changes (product-critical), or deferred with a written justification.
- A non-blocker that is reproduced during M1 work becomes a blocker.
- The source for every column below is the Claude Security report of 2026-10-12. "Reproduced" means a runtime reproduction already recorded for that finding.

| Finding | Severity / confidence / panel | Reproduced | Class | Disposition |
|---|---|---|---|---|
| F1 routines grant `Bash(git *)` while reading untrusted content | MEDIUM / medium / 3 of 3 | no | Blocker (rule 2) | Fix: narrow to the git subcommands each routine uses |
| F2 `news` adds WebFetch/WebSearch to `Bash(git *)` under `dontAsk` | MEDIUM / medium / 3 of 3 | no | Blocker (rule 2) | Fix with F1 |
| F3 `news` combines unrestricted Read with web content | MEDIUM / low / 3 of 3 | no | Not blocker: low confidence | Fix with F2 (same grant list) |
| F4 push guard misses newline and tight `;` chains | LOW / high / 3 of 3 | yes | Blocker (rule 1) | Fix |
| F5 push guard misses `-lc`, `-ec` | LOW / high / 3 of 3 | yes | Blocker (rule 1) | Fix |
| F6 push guard misses `-uf`, `-fu` | LOW / high / 3 of 3 | yes | Blocker (rule 1) | Fix |
| F7 task gate: `[[` hides later commands | LOW / medium / 2 of 3 | yes | Blocker (rule 1) | Fix |
| F8 task gate: carriage return as a comment boundary | LOW / medium / 2 of 3 | yes | Blocker (rule 1) | Fix |
| F9 quadratic regex on `tasks.md` in the snapshot | LOW / medium / 2 of 3 | no | Not blocker | Fix when ready, otherwise defer to the next release. Justification: availability only (a slower session start in a repository that carries a hostile `tasks.md`); no confidentiality or integrity impact. |
| F10 push guard ignores `git -C` and in-command `cd` | LOW / medium / 3 of 3 | no | Not blocker | Fix with F4–F6 (same parser) |
| F11 task gate loses a computed `cd` into the config directory | LOW / medium / 3 of 3 | no | Not blocker | Fix with F7 and F8 (same parser) |
| F12 bare credential directories not treated as credential access | LOW / medium / 3 of 3 | yes | Blocker (rule 1) | Fix |
| F13 settings rewrite drops the 0600 mode | LOW / medium / 3 of 3 | yes | Blocker (rule 1) | Fix |
| F14 `jira_eod` read/write boundary is prompt-only | LOW / low / 3 of 3 | no | Not blocker | **Deferred** (justification below) |

- **F14 justification:**
  - It is low severity and low confidence, and it was not reproduced.
  - The write path it concerns is the routine's intended function.
  - Narrowing it needs per-tool MCP permission rules for the Atlassian server, which this plan has not verified.
  - It only matters on installs where `jira_eod` has Atlassian access configured.
  - It is recorded as a known limitation in the routines documentation, and revisited when that routine next changes or if it is reproduced.
- **Product-critical, non-blocking in M1:**
  - the `routines schedule` time bug;
  - archiving finished changes, including the two main-spec Purpose sections that `validate --specs --strict` needs first;
  - the `docs/FUTURE-SCOPE.md` refresh.
- **How each fix is made:** the smallest change in place. The push guard and the task gate keep separate parsers, because merging them would refactor a released, enforced control during a release; the duplication is a recorded trade-off. Narrowed routines are re-run live through the existing path. `add-groundwork-copilot` stays open, since its remaining tasks are deferred features.

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
- **Maximum cost, stated before authorization:**
  - Every run is capped with `claude -p --max-budget-usd`. The flag is present in the installed CLI, 2.1.296.
  - The only measured cost is a trivial task: $0.21 without ECC and $0.41 with it (`docs/VALIDATION.md`). The caps are ceilings set well above that, not predictions.
  - The baseline is 18 task runs (3 tasks, 3 arms, 2 runs each), 6 short fresh-session resume runs (MATERIAL task, 3 arms × 2) and 1 dry run.

  | Run | Cap | Count | Maximum |
  |---|---|---|---|
  | STANDARD task | $1.50 | 6 | $9.00 |
  | TROUBLESHOOT task | $3.00 | 6 | $18.00 |
  | MATERIAL task | $6.00 | 6 | $36.00 |
  | Resume check | $0.75 | 6 | $4.50 |
  | Dry run (STANDARD, one arm) | $1.50 | 1 | $1.50 |
  | **Total** | | **25** | **$69.00** |

  - A run that hits its cap is recorded as capped. That is a result too, and it is never silently re-run.
  - UNVERIFIED: whether the CLI stops exactly at the cap or after the turn that crosses it. If it is the latter, the overshoot is at most one turn per run, and the observed total is reported.
  - On a subscription login, the dollar figure is the CLI's computed equivalent and the runs use plan limits. How the cap applies there is UNVERIFIED.
  - The owner authorizes the $69.00 maximum before the dry run. A later re-run is authorized separately, with its own stated maximum.
- **Delivery:** a short runbook and a small script under `tests/eval/`. No framework, and no runs in CI.

### D8. ECC: make it an optional integration (DECISION record)

```
DECISION            Groundwork stops depending on ECC. A failed or skipped ECC install no longer
                    aborts install.sh or fails --verify. Existing installs keep ECC. The rules name
                    native subagents and review commands first and ECC agents only "when
                    installed". The default for new installs (ECC on or off) stays UNDECIDED until
                    the R9 baseline compares Groundwork with and without ECC; the owner then picks
                    it. Groundwork's task gate hard-blocks --no-verify with or without ECC, which
                    keeps today's enforced control. For installs without ECC, "investigate before
                    edit" becomes advisory. ECC is not modified.
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
                    everyone who does not. Whether "does not" should be the default is a question
                    for the comparative evidence, not for this record.
TRADEOFFS           Users without ECC lose the language-specific reviewer checklists (native
                    reviewers are general) and GateGuard's hard "investigate first" stop (now
                    advisory). That downgrade from enforced to advisory is a control change; the
                    owner approves it together with the ECC default. A hard deny is a new kind of
                    decision for the task gate, which otherwise only asks.
VALIDATION METHOD   The acceptance criteria below, plus the R9 baseline arms with and without ECC.
UNCERTAINTY         Cost data is n=1 on a trivial task (the R9 baseline replaces it). Hook latency
                    is not measured. Whether anyone uses /ecc:* commands is NOT VERIFIED. The
                    install-abort path is INFERENCE.
```

**`--no-verify` policy:**
- Today ECC's block-no-verify hook enforces a hard block, and `docs/ARCHITECTURE.md` lists it as Enforced.
- This plan keeps a hard block: Groundwork's task gate denies the bypass forms, so the control holds whether or not ECC is installed. This needs a `task-lifecycle` spec delta, written in E once that capability is in the main specs.
- Replacing the block with `ask` would weaken an enforced control. That makes it a **security-policy change**, which needs three things before it could happen:
  1. explicit owner approval;
  2. its own spec delta;
  3. its own validation: tests for every bypass form, and a live check that the prompt appears.

  It is not part of this plan.

**Migration:**
- **Upgrade:** never uninstalls or disables ECC. `hook_profile` is kept when ECC is present.
- **New installs:**
  - `setup.sh` asks once, offering the default the owner picks after the R9 baseline, and records the answer in `config.json`.
  - `--non-interactive` keeps the current machine's state.
  - `groundwork update` passes the detected state through.
- **Other changes:**
  - `rules/engineering-workflow.md` gets native-first wording.
  - The ARCHITECTURE enforced-controls table, README and `tests/test_setup.py` are updated.
- **Spec order:** archive `groundwork-2-enterprise-sre` first, so `ecc-capability-policy` is in the main specs. Then write E's MODIFIED delta against it.

**Acceptance criteria:**
1. A clean install with ECC declined completes. `--verify` passes. The full test suite passes.
2. In a fixture repository without ECC, a MATERIAL change reaches completion. Its independent review comes from a native subagent that emits `REVIEW RESULT`, and the review gate accepts it.
3. With and without ECC, `git commit --no-verify`, `git commit -n` and `git push --no-verify` are denied, and `git commit -m msg` is not.
4. Upgrading a machine that has ECC leaves ECC installed and enabled, with `hook_profile` unchanged.
5. No rule line names an ECC agent without a native alternative.
6. The R9 baseline reports always-on tokens and cost with and without ECC.

**Risks:**
- [Review quality drops for Python-heavy work without ECC] → The native reviewer prompt names the language. The R9 review-effectiveness measure checks this. The owner can keep ECC.
- [Edits happen without investigation once GateGuard is gone] → The rules, snapshot and review gate remain, and the R9 "plan before first edit" measure watches for it.
- [The baseline favours keeping ECC on by default] → The default is decided from that evidence. Only the default changes; the work is the same.

### D9. Roles and review
- Claude implements and supplies evidence.
- A fresh-context reviewer subagent is the in-harness gate for each MATERIAL change. It must emit `REVIEW RESULT`, and Must-fix must reach 0.
- At each milestone gate, the owner relays the PR, diff and evidence to ChatGPT/Codex for architecture and independent review.
- The owner alone approves merge, tag, publish and any production action.
- Claude never self-approves and never reviews its own change as the only reviewer.

### D10. Work classes, the pilot, and M2 during the pilot
- **Release-critical** work blocks only its own milestone's release:
  - M0: the version checks in D11;
  - M1: the D2 release blockers, a green full suite, clean install plus 2.4.0 upgrade plus rollback, live COR-123 acceptance, a fresh-context review at Must-fix 0, the owner macOS smoke test, and owner approval;
  - E, M2 and M3: the same release gate plus their own acceptance criteria.
- **Product-critical** work is needed for the vision and planned in its milestone. If it is not ready, it moves to the next release with a note, without holding up an unrelated release. This covers:
  - the non-blocking findings in D2, the schedule bug and the M1 housekeeping;
  - the R9 evaluation;
  - E;
  - M2;
  - M3's statusLine segment and intake hints.
- **Optional** work never blocks a milestone: the dashboard's clipped labels and unsorted rows. Dark mode stays a non-goal.
- **The pilot:**
  - It starts when 2.5.0 is published and has no fixed duration.
  - Findings are logged as they occur in the 2.5.0 release report: unneeded prompts, intake misclassifications and resume failures.
  - It blocks nothing except M2's merge.
- **M2 during the pilot:**
  - M2 development may start once 2.5.0 is published, on its own branch off `main`.
  - **Before M2 merges:** every logged pilot finding that touches intake, the ledger, the gate or completion is fixed or explicitly deferred with a reason. At least one real MATERIAL task must have gone from intake to completion or cancellation on 2.5.0, so that pilot findings exist to check.
  - If M2 code collides with a pilot fix, the fix lands on `main` first and M2 merges `main` in.

### D11. M0 stays minimal and keeps version behaviour
- **Scope:** the 2.4.0 CHANGELOG section and `docs/RELEASE-REPORT-2.4.md` from tag `v2.4.0`, and removal of the already-released macOS entry from Unreleased. Nothing else; the spec Purpose fixes move to M1 housekeeping.
- **Why version behaviour is at stake:** two pieces of code take the first `## x.y.z` CHANGELOG heading as the version, and `## Unreleased` does not match it.
  - `install.sh:192` writes the installed `VERSION` file from it.
  - `scripts/groundwork_update.py:180-186` reads it, and lines 345–347 refuse an update whose fetched CHANGELOG top version does not match the release.
- **Checks:**
  1. `grep -m1 -oE '^## [0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md` prints `## 2.4.0`, the same command `install.sh` uses. The value is unchanged from today.
  2. `_top_changelog_version` from `groundwork_update.py` returns 2.4.0 for the reconciled file.
  3. Every released section, from `## 2.4.0` to the end, is byte-identical to the tag.
  4. `## Unreleased` stays first and holds only post-2.4.0 entries.
  5. `python3 tests/test_groundwork_update.py` and the full suite pass.
- **Effect on the next release:** M1 adds `## 2.5.0` above the 2.4.0 section, which keeps the update check consistent.

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
  - E keeps `--no-verify` hard-blocked. Any move to `ask` is a separate, owner-approved security-policy change (D8).
- **Scaling and cost:** ledger reads are per repository and small. `next` is O(tasks²) at most, for tens of tasks. E removes about 40K tokens per session for users without ECC. R9 runs are capped per run, so the baseline costs at most $69.00 (D7). The actual cost is UNVERIFIED until it is run and reported.

## Testing and real-world validation strategy

| Milestone | Unit / integration | Live / real-world |
|---|---|---|
| M0 | The D11 version checks; diff against the `v2.4.0` tag; `tests/test_groundwork_update.py` and the full suite | — |
| M1 | One regression test per finding (from the report's proof of concept); full suite `python3 -m pytest tests -q --ignore=tests/mutation`; no mutation suite exists for the gate or push guard; regression tests stand in | Clean install, 2.4.0 → 2.5.0 upgrade, rollback in sandbox config dirs. Live COR-123 acceptance with real `claude -p` and a fake `gcloud`. Re-run each narrowed routine. Owner macOS smoke test. Owner pilot, with no fixed duration (D10). |
| R9 | Script dry run on one task, within its cap | 3 tasks × 3 arms × 2 runs plus 6 resume runs, each capped (D7) |
| E | `test_setup.py` updates; `--no-verify` gate tests | Clean install without ECC; upgrade with ECC; MATERIAL fixture reaching completion with a native reviewer |
| M2 | Parser, readiness, cycle and order tests; multi-key intake tests | Live two-ticket run: both recorded, `next` recommends the prerequisite, fresh-session resume |
| M3 | statusLine segment tests; no-subprocess assertion; intake hint tests | Live statusLine render timing; COR-123 intake shows the GCP hint; optional dashboard screenshot check (does not block the release) |

Unit tests prove logic only. Each milestone is reported as complete only with its live evidence. Anything that cannot be run is labelled RUNTIME VALIDATION REQUIRED.

## Safety and rollback

- Milestone releases are reversible with `groundwork rollback`, which is tested in every release.
- New task behaviour is read-only or guidance. E adds no `ask`. It adds one hard block, `--no-verify`, which keeps today's ECC-enforced control. `GROUNDWORK_TASK_GATE=off` switches the gate off.
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
| R9 baseline | 1.5–3 d | low | New script and fixtures; run cost capped at $69.00 (D7) |
| E | 1.5–3 d | medium | Install, setup and merge changes, tests, two live installs |
| M2 | 4–8 d | low–medium | Intake classifier changes have needed several review rounds before |
| M3 | 3–5 d | low–medium | statusLine and intake changes are small; live timing and screenshots add time |
| R9 re-run | 0.5–1 d | medium | Reuses the baseline script |
| **Total** | **13.75–26.5 d** | low–medium | The pilot runs alongside later work and adds no fixed delay (D10) |

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

1. **M1 release criteria:** approve the D2 rule. Its effect is that F1, F2, F4–F8, F12 and F13 block 2.5.0, F3, F9, F10 and F11 are fixed when ready, and F14 is deferred with the stated justification.
2. **ECC default for new installs:** decided **after** the R9 baseline, from its evidence. Approving this plan now commits only to making ECC optional and keeping existing installs as they are.
3. **Where E sits:** after the M1 release and the R9 baseline (recommended), or folded into M3 to keep the original M2-then-M3 order.
4. **R9 baseline spend:** authorize a maximum of $69.00, enforced per run with `--max-budget-usd` (D7), before the dry run.
5. **M0 method:** a docs-only PR that copies the 2.4.0 CHANGELOG section and release report from the tag and passes the D11 version checks. This avoids the release-branch merge that was blocked earlier.
6. **`--no-verify` (only if raised later):** the plan keeps the hard block. Changing it to `ask` would need a separate, explicit approval (D8).

## Open Questions

- The exact read-only git subcommands each routine needs. They are found by reading each routine's prompt in M1; this does not change the approach.
- The staleness threshold for showing cache age in the intake hint. It reuses the statusLine's documented threshold unless that proves unsuitable.
