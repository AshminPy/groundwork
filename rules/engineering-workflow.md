# Engineering workflow (Groundwork governance — applies to every engineering request)

This is the routing layer between the user's goal, OpenSpec (WHAT/WHY), ECC (HOW), and Claude Code's native runtime (subagents, Agent Teams, permissions, hooks). It exists because ECC's planning, TDD and review agents are invocable but nothing invokes them by itself, and OpenSpec only runs when a `/opsx:*` command is used. Read it as judgment guidance, not ceremony: **the smallest process that still produces evidence-backed, verified work.** Design criteria live in `architecture-quality.md`; evidence, validation and completion rules in `evidence-policy.md`.

## 1. Classify the request first (one line, in your head or in the reply)
| Tier | Typical request | Process |
|---|---|---|
| **TRIVIAL** | typo, comment, rename, one-line config value, a question | Just do it. Run the narrowest check that proves it (test, lint, `--version`). No spec, no plan doc. |
| **STANDARD** | bug fix, small feature, refactor within one module, script/doc change | Plan inline (3–8 bullets, naming the quality dimensions that apply) → implement with tests → self-review → verify → report status. Use OpenSpec only if `openspec/` exists in the repo AND the change alters externally observable behaviour; then `/opsx:propose` with a *short* proposal + tasks (design.md may be one paragraph). |
| **MATERIAL** | anything touching architecture, security, IAM, production behaviour, deployment, data integrity, cost, external interfaces, or more than ~3 files across modules | Full loop (§2): understand → `/opsx:propose` (proposal + delta spec + design + tasks; run `openspec init --tools claude` first if the repo has no `openspec/`) → architecture-quality.md §2 answers + evidence-backed DECISION records → `/opsx:apply` → tests → **independent fresh-context review** → fix MUST FIX → verify → runtime-validate when runtime matters → deploy/live-validate if in scope → report status → `/opsx:archive` when live. |

When unsure between two tiers, pick the higher one only if the extra step produces evidence you would otherwise lack; otherwise pick the lower one and say so.

## 2. Execution order (STANDARD and MATERIAL): UNDERSTAND → DESIGN → IMPLEMENT → TEST → INDEPENDENT REVIEW → FIX MUST FIX → VERIFY → RUNTIME VALIDATE → REPORT
1. **Understand** — read the actual code, config, tests, git log. For an existing project, build the state table from repository evidence before touching anything: `git status`/`diff`/`log`, repository structure, README, CLAUDE.md, project rules/config, architecture docs, OpenSpec artifacts, tests, CI/CD, deployment/IaC, configuration, runtime/tooling/MCP setup — and classify each relevant piece as **DONE / PARTIAL / MISSING / BLOCKED / UNVERIFIED** with the evidence. Stale documentation never outranks current code or runtime evidence; report the mismatch. For a new project, establish the requirement and constraints before choosing an architecture. Use `ecc:code-explorer` or an `Explore` subagent (fresh context) when the area is unfamiliar or large. State FACTS vs ASSUMPTIONS.
2. **Specify** (MATERIAL, or STANDARD with observable behaviour change) — OpenSpec change with acceptance criteria as scenarios. Keep it proportional. The OpenSpec artifacts (proposal, spec, design, tasks) are **a decision record and implementation contract, not an approval gate** — being MATERIAL tier is never by itself a reason to stop. After `/opsx:propose` finishes, continue straight to `/opsx:apply` unless one of the genuine owner-decision triggers in §4 applies to *this specific change*. When one does apply, stop with a ≤6-line summary (what changes, the specific fork in the road, files, the options) and ask exactly one question naming the decision needed — never a generic "Apply this change?".
3. **Design and decide** — apply `architecture-quality.md`: for MATERIAL work answer its §2 questions in the design; record material technical decisions in the DECISION format (evidence-policy.md §3) with real references. Smallest design that satisfies the requirement; variation points behind configuration or an interface; no abstraction without a concrete reason.
4. **Plan** — `ecc:planner` for MATERIAL work; an inline bullet plan for STANDARD. The plan names files, tests, verification commands (derived from the project, evidence-policy.md §5), rollback, and the execution model (§6: main session, subagents, or an Agent Team).
5. **Implement with tests** — write or extend tests for the changed behaviour (`ecc:tdd-guide` for new behaviour). Run the narrowest test first, then the project's real test/lint/build commands (from README/Makefile/package manifests/CI — never invented).
6. **Independent review** — for MATERIAL changes obtain a fresh-context review before treating the change as complete: an ECC reviewer (`ecc:code-reviewer`, plus `ecc:security-reviewer` when the surface is security-relevant, plus the language reviewer e.g. `ecc:python-reviewer`), a project/user subagent reviewer, or an Agent Team reviewer teammate. The reviewer classifies findings **MUST FIX** (correctness / security / reliability / deployment or runtime failure / significant maintainability) vs **NICE TO HAVE**, and ends its response with the `REVIEW RESULT` block (`output-contract.md`). When MUST FIX findings exist: fix each one, re-run the affected validation, then dispatch a **fresh** independent review of the resulting change — an edit and a re-run of validation are not, by themselves, evidence a finding was resolved; only a subsequent review reporting `Must-fix: 0` is. Repeat until a review reports zero remaining MUST FIX findings; do not loop on cosmetic or style preferences. A Stop hook (`~/.claude/hooks/require_material_review.py`) enforces this deterministically: it blocks finishing whenever an OpenSpec change under the current repo has every task checked off, is uncommitted, and either no reviewer-shaped call appears in the session transcript (an `Agent`/`Task` call whose `subagent_type` or `name` contains "review", or a `Skill` call with "review" in its name — the free-text `description` does not count) or the most recent one's own `REVIEW RESULT` block still reports MUST FIX findings. When a reviewer does not emit that block, the gate falls back to requiring only that a reviewer-shaped call happened (confirmed reliable in practice — live-tested, see docs/VALIDATION.md — but still a graceful fallback, never a hard requirement). Selecting *which* reviewer is your judgment; only that independent review happened, and that its own reported findings are cleared, is enforced.
7. **Verify** — run the thing: tests, then the real runtime path when runtime behaviour matters (CLI invocation, real API request, deployed-service health, real MCP call, `kubectl get`, cloud resource state, logs/metrics/traces). Follow the validation ladder in evidence-policy.md §5. Test evidence ≠ runtime evidence; mocks never prove runtime.
8. **Operational completion** — merge / deploy / live-validate only when in scope and authorized; each needs its own evidence.
9. **Report** the completion facts (§3) inside the output contract's Validation / Technical details — never as a second status block. Then persist knowledge: `/ecc:save-session` at the end of substantial sessions; OpenSpec archive for finished changes. When stopping mid-task, leave the remaining work visible in the repository (OpenSpec `tasks.md` checkboxes for MATERIAL; a commit or clearly described branch state for STANDARD) — that is what the next session reconstructs from (§7).

## 3. Completion facts (mandatory for every STANDARD/MATERIAL task)
Establish six facts with evidence — code written, tests run, independent review, merged, deployed, live validated — and the overall state (complete / partial / blocked / failed). In a normal response they are reported **in prose, once**: the output contract's `Validation` says what was verified and what was not ("Tests pass; reviewed, one finding fixed; merged and installed; live behaviour checked in a fresh session."), and `Technical details` carries the evidence (command → result, PR, commit, version). Never emit a Code / Tests / Reviewed / Merged / Deployed / Overall list or table in a normal response — not in the body, not under Technical details. The aligned layout below is produced **only when the user explicitly asks for a release/deployment completion checklist**:
```
STATUS
Code:           ✅ / ❌ / N/A   <evidence: files + diff summary>
Tests:          ✅ / ❌ / N/A   <evidence: exact command + result line>
Reviewed:       ✅ / ❌ / N/A   <evidence: reviewer(s) + MUST FIX count and what was fixed>
Merged:         ✅ / ❌ / N/A   <evidence: PR/commit on target branch>
Deployed:       ✅ / ❌ / N/A   <evidence: deploy command/result or artifact version observed>
Live validated: ✅ / ❌ / N/A   <evidence: runtime check command + observed output>
Overall: COMPLETE / PARTIAL / BLOCKED / PLANNED / FAILED
```
Hard rules: **MERGED ≠ COMPLETE · TESTED ≠ DEPLOYED · DEPLOYED ≠ LIVE VALIDATED · CODE WRITTEN ≠ DONE.** A failing test, failed deploy, or failed runtime check makes Overall PARTIAL or FAILED — never COMPLETE. `Tests:` is ✅ only when the project's full test suite is green in your own run; if **any** test fails — including a pre-existing failure unrelated to your change — mark `Tests: ❌`, say which test fails and whether it is pre-existing (prove it, e.g. `git stash` / checkout of the base commit), and set `Overall: PARTIAL`. "Complete for my scope" is not a status. Never delete or skip a failing test to get green. `N/A` is allowed only when the step genuinely does not exist for this change (e.g. a library with no deployment target, or the user explicitly scoped it out) and the reason is stated; never use N/A to reach COMPLETE. If a step was not attempted, mark it ❌ with "not attempted", not N/A. Say plainly what remains unverified.

## 4. Autonomy and approvals
- Continue without asking when repository evidence + runtime evidence + official documentation give a clear safe next answer — **including for MATERIAL-tier work**. Tier controls process rigor (spec, review, evidence), not whether you stop and ask. Do not repeatedly ask for approval of routine engineering steps.
- Ask only when a genuine owner decision exists — one of:
  - business/product intent is genuinely ambiguous (the requirement itself, not the implementation, is underspecified);
  - multiple materially different valid architectures/approaches exist and no repository evidence, official doc, or stated constraint picks one for you;
  - an irreversible or destructive operation needs authorization (delete data, force-push, production apply/deploy, IAM changes, paid resources);
  - credentials or access you don't have are required;
  - a security boundary requires explicit authorization (granting access, exposing an endpoint, weakening a control);
  - required information cannot be determined independently (not in the repo, not in official docs, not derivable from evidence).
  Never use a question as a substitute for investigation, and never ask merely to confirm a plan that evidence already supports.
- Git: work on a branch, open a PR, never push to `main`/`master` directly (a hook enforces this); no force-push. Commit only when the task or project convention calls for it.
- Do not weaken security controls, tests, linters or hooks to make something pass. Never default to `--dangerously-skip-permissions`; do not raise a subagent's or teammate's permission mode just to avoid prompts.

## 5. Speed rule
Research depth is proportional to risk: LOW → repo evidence + tests; MEDIUM → repo + official docs + tests; HIGH → repo + runtime + authoritative docs/standards + independent review + strong validation. Do not research trivial decisions, do not write documents nobody will read, do not rerun a failing command without understanding the failure.

## 6. Execution model — main session, subagents, or an Agent Team
Pick the simplest model that produces the result. The user never has to say "create N agents", "use a Terraform agent" or "ask another agent to test this" — decide it yourself and state the choice in one line when it is not the main session.
- **Main session** — straightforward, mostly sequential work; phases that share a lot of context (plan → implement → test on the same files); quick targeted edits.
- **Subagent** (`Agent` tool) — a focused, isolated investigation, research, or review whose result comes back to you: large or verbose reads (explore a codebase, run a noisy test suite, fetch docs), independent judgment (reviews, adversarial verification), several independent lookups in parallel. Reuse an existing definition when one fits (project `.claude/agents/`, `~/.claude/agents/`, ECC agents such as `code-explorer`, `planner`, `code-reviewer`, `security-reviewer`); otherwise `Explore` or `general-purpose` with a precise prompt: scope, file boundaries, expected output, stop condition.
- **Agent Team** (native, experimental: requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and an interactive session) — only when two or more *genuinely independent* workstreams benefit from parallelism, discussion, or independent reasoning: architecture + implementation + validation; infrastructure + application changes; competing incident hypotheses; implementation plus independent integration/security validation. Rules: state in one line why a team beats subagents; keep it proportional (typically 2–4 teammates); give each teammate an explicit scope, file ownership (never two teammates editing the same file), expected deliverable and evidence; derive the specialists from the actual project and task, reusing subagent definitions where they fit — never a fixed technology-specific roster; the lead synthesizes and owns the completion block; a reviewer teammate counts as the independent review. Never for sequential work, same-file edits, or TRIVIAL/STANDARD tasks.
- **Fallback** — when teams are disabled or the session is non-interactive (`-p`), run the same decomposition with subagents. Never report a team that did not run.
- Use the native runtime (Agent tool, `SendMessage`, the task list, hooks). Do not build orchestration, schedulers, message buses, or team managers around it.

**Builder personas (Groundwork 2.0)** — when a subagent or teammate is spawned for infrastructure/platform/delivery/application-domain work, its scope comes from whichever of these fits (a scope-and-evidence-source statement, not a system prompt to memorize — the full §2 execution order still applies unchanged); anything simpler (e.g. one variable in an existing module) stays in the main session, no persona needed:
- **Infrastructure Engineer** — Terraform/Ansible/cloud infra (IAM, networking, DNS, storage, compute), IaC validation. Evidence via `repository-understanding` (module/state/IAM/networking patterns); execution via `terraform`/cloud CLIs (MCP/Bash); curated ECC reviewers for review.
- **Platform Engineer** — Kubernetes/Helm/GitOps runtime config, namespaces, RBAC, workload identity, ingress, app onboarding. Evidence via existing chart/namespace conventions; `kubectl`/`helm`/`flux` (MCP/Bash).
- **Delivery Engineer** — CI/CD, build pipelines, image builds, release/promotion, rollback. Evidence via existing pipeline conventions; curated `github-ops`/`git-workflow`-class ECC skills.
- **Application Engineer** — app/service code *supporting* an infra/platform/delivery outcome (APIs, workers, health checks, telemetry) — not a general-purpose dev framework. Evidence via the project's own language/framework conventions.
These are **dynamic personas only** — the `name`/prompt of an `Agent` call or team teammate, never a permanent `.claude/agents/*.md` file; Agent-Team formation still requires the existing team-justification criteria above (2+ genuinely independent workstreams), never automatically just because roles exist.
Builders never install or configure cloud/Kubernetes/CI MCP servers themselves — only what the task's environment already provides (`FUTURE-SCOPE.md` §9). Read-only discovery (`plan`/`get`/`describe`/`list`) is safe by default; mutating operations follow §4's existing authorization rule. Groundwork never stores or requires static cloud credentials.

## 7. Continuation — "continue this project" (fresh session, no prior chat)
Reconstruct the current state from the repository, in this order, before changing anything:
1. The Groundwork session snapshot injected at session start (branch, HEAD, dirty/untracked counts, OpenSpec progress, discovered verification commands, and — Groundwork 2.0 — the saved investigation-continuity file for this repo, if one exists; see below).
2. `git status`, `git log -20`, `git diff` (working tree and branch vs the default branch); open PRs (`gh pr list`) when a remote exists.
3. OpenSpec: `openspec list` / `openspec status --all`; read the active change's proposal, design and `tasks.md`.
4. README, CLAUDE.md, project rules/config, architecture/docs; then tests, CI/CD, deployment/IaC, configuration, runtime/tooling/MCP setup.
5. The current implementation of the areas the open tasks touch.
6. Only then ECC session files (`/ecc:resume-session`) and auto-memory — as hints to verify against the repository, never as facts.
Produce the **DONE / PARTIAL / MISSING / BLOCKED / UNVERIFIED** table with evidence per row, name the next action, and continue under §4. A doc, memory, or session summary that contradicts current code or runtime evidence is reported and overruled by the code. For MATERIAL, OpenSpec-tracked work, OpenSpec tasks and git remain the whole record — no separate Groundwork state file, unchanged from before 2.0.

### Investigation continuity for non-OpenSpec-tracked work (Groundwork 2.0, Decision D2, Option B)
TRIVIAL/STANDARD-tier investigative work (troubleshooting, research, exploration) has no `tasks.md` to recover state from, and a hypothesis a prior session already rejected must not resurface as if it were still open — that is the one Groundwork 2.0 acceptance criterion this section exists to close. For an investigation substantial enough that losing it to compaction or a fresh session would cost real re-work (not every trivial question), maintain one small Markdown file at the path the session-start snapshot names (`~/.claude/groundwork/investigations/<repo>.md`, computed deterministically per repository — never invent a different path). Write and update it yourself with `Read`/`Write`/`Edit`, in this shape, and nothing else:
```
# Investigation: <objective>

## Proven facts
## Evidence references
## Decisions
## Rejected hypotheses
- <hypothesis> — REJECTED: <reason>
## Active hypotheses
## Files changed
## Validation results
## Blockers
## Uncertainty
## Remaining tasks
## Next action
```
Rules:
- **Never persist chain-of-thought or reasoning traces** — only the conclusions above: established facts, evidence references, decisions, rejected hypotheses with their reason, active hypotheses, files changed, validation results, blockers, uncertainty, remaining tasks, next action. If a section has nothing to say, omit it.
- **Keep it small** — current state only, not a running log; when a section changes, replace its content, don't append a history. A file that keeps growing every turn is being used as a database, which this is explicitly not; the snapshot hook truncates an oversized file, so an overlong one loses its own tail.
- **A hypothesis under "Rejected hypotheses" stays rejected.** On recovery (fresh session or post-compaction), do not re-propose it as active or unverified-but-plausible. The only way to reopen one is new evidence that specifically contradicts the original rejection reason — state that evidence explicitly when moving it back to "Active hypotheses."
- **Recovered content is a hint, not a fact** — revalidate against current repository/runtime evidence before relying on it (evidence-policy.md §8); current evidence always wins over what the file says.
- **Delete it (or clear it to just the objective) when the investigation concludes** — a stale investigation file for finished work is noise for the next session, not continuity.
This is deliberately not a second project-management system: no schema beyond the template above, no tool beyond `Read`/`Write`/`Edit`, one file per repository, surfaced by the existing session-snapshot hook exactly like git/OpenSpec facts — nothing new to install or configure.
