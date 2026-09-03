# Engineering workflow (harness governance — applies to every engineering request)

This is the routing layer between the user's goal, OpenSpec (WHAT/WHY), and ECC (HOW). It exists because ECC's planning, TDD and review agents are invocable but nothing invokes them by itself, and OpenSpec only runs when a `/opsx:*` command is used. Read it as judgment guidance, not ceremony: **the smallest process that still produces evidence-backed, verified work.**

## 1. Classify the request first (one line, in your head or in the reply)
| Tier | Typical request | Process |
|---|---|---|
| **TRIVIAL** | typo, comment, rename, one-line config value, a question | Just do it. Run the narrowest check that proves it (test, lint, `--version`). No spec, no plan doc. |
| **STANDARD** | bug fix, small feature, refactor within one module, script/doc change | Plan inline (3–8 bullets) → implement with tests → self-review → verify → report status. Use OpenSpec only if `openspec/` exists in the repo AND the change alters externally observable behaviour; then `/opsx:propose` with a *short* proposal + tasks (design.md may be one paragraph). |
| **MATERIAL** | anything touching architecture, security, IAM, production behaviour, deployment, data integrity, cost, external interfaces, or more than ~3 files across modules | Full loop: investigate repo → `/opsx:propose` (proposal + delta spec + design + tasks; run `openspec init --tools claude` first if the repo has no `openspec/`) → evidence-backed decisions (see evidence-policy.md) → `/opsx:apply` → tests → **independent fresh-context review** → fix MUST-FIX findings → verify → deploy/live-validate if in scope → report status → `/opsx:archive` when live. |

When unsure between two tiers, pick the higher one only if the extra step produces evidence you would otherwise lack; otherwise pick the lower one and say so.

## 2. Autonomous execution order (STANDARD and MATERIAL)
1. **Understand & investigate** — read the actual code, config, tests, git log. Use `ecc:code-explorer` (fresh context) when the area is unfamiliar or large. State FACTS vs ASSUMPTIONS.
2. **Specify** (MATERIAL, or STANDARD with observable behaviour change) — OpenSpec change with acceptance criteria as scenarios. Keep it proportional. The OpenSpec artifacts (proposal, spec, design, tasks) are **a decision record and implementation contract, not an approval gate** — being MATERIAL tier is never by itself a reason to stop. After `/opsx:propose` finishes, continue straight to `/opsx:apply` unless one of the genuine owner-decision triggers in §4 applies to *this specific change*. When one does apply, stop with a ≤6-line summary (what changes, the specific fork in the road, files, the options) and ask exactly one question naming the decision needed — never a generic "Apply this change?".
3. **Decide** — material technical decisions use the DECISION format in evidence-policy.md with real references.
4. **Plan** — `ecc:planner` for MATERIAL work; an inline bullet plan for STANDARD. The plan names files, tests, verification commands and rollback.
5. **Implement with tests** — write or extend tests for the changed behaviour (`ecc:tdd-guide` for new behaviour). Run the narrowest test first, then the project's real test/lint/build commands (from README/Makefile/CI, never invented).
6. **Independent review** — for MATERIAL changes dispatch a fresh-context reviewer (`ecc:code-reviewer`, plus `ecc:security-reviewer` when the surface is security-relevant, plus the language reviewer e.g. `ecc:python-reviewer`) before treating the change as complete. The reviewer classifies findings **MUST FIX** (correctness / security / reliability / deployment / material maintainability) vs **NICE TO HAVE**. Only MUST FIX blocks completion. Fix them, re-run tests. A Stop hook (`~/.claude/hooks/require_material_review.py`) enforces this deterministically: it blocks finishing whenever an OpenSpec change under the current repo has every task checked off and no reviewer-shaped `Task`/`Skill` call (subagent or skill name containing "review") appears anywhere in the session transcript. Selecting *which* reviewer is still your judgment call — only that some independent review happened is enforced.
7. **Verify** — run the thing: tests, then the real runtime path when runtime matters (CLI invocation, curl, kubectl get, log check). Test evidence ≠ runtime evidence.
8. **Operational completion** — merge / deploy / live-validate only when in scope and authorized; each needs its own evidence.
9. **Report** using the completion status block below. Then persist knowledge: `/ecc:save-session` at the end of substantial sessions; OpenSpec archive for finished changes.

## 3. Completion status block (mandatory for every STANDARD/MATERIAL task)
```
STATUS
Code:           ✅ / ❌ / N/A   <evidence: files + diff summary>
Tests:          ✅ / ❌ / N/A   <evidence: exact command + result line>
Merged:         ✅ / ❌ / N/A   <evidence: PR/commit on target branch>
Deployed:       ✅ / ❌ / N/A   <evidence: deploy command/result or artifact version observed>
Live validated: ✅ / ❌ / N/A   <evidence: runtime check command + observed output>
Overall: COMPLETE / PARTIAL / BLOCKED / PLANNED / FAILED
```
Hard rules: **MERGED ≠ COMPLETE · TESTED ≠ DEPLOYED · DEPLOYED ≠ LIVE VALIDATED.** A failing test, failed deploy, or failed runtime check makes Overall PARTIAL or FAILED — never COMPLETE. `Tests:` is ✅ only when the project's full test suite is green in your own run; if **any** test fails — including a pre-existing failure unrelated to your change — mark `Tests: ❌`, say which test fails and whether it is pre-existing (prove it, e.g. `git stash` / checkout of the base commit), and set `Overall: PARTIAL`. "Complete for my scope" is not a status. Never delete or skip a failing test to get green. `N/A` is allowed only when the step genuinely does not exist for this change (e.g. a library with no deployment target, or the user explicitly scoped it out) and the reason is stated; never use N/A to reach COMPLETE. If a step was not attempted, mark it ❌ with "not attempted", not N/A.

## 4. Autonomy and approvals
- Continue without asking when repository evidence + runtime evidence + official documentation give a clear safe next answer — **including for MATERIAL-tier work**. Tier controls process rigor (spec, review, evidence), not whether you stop and ask.
- Ask only when a genuine owner decision exists — one of:
  - business/product intent is genuinely ambiguous (the requirement itself, not the implementation, is underspecified);
  - multiple materially different valid architectures/approaches exist and no repository evidence, official doc, or stated constraint picks one for you;
  - an irreversible or destructive operation needs authorization (delete data, force-push, production apply/deploy, IAM changes, paid resources);
  - credentials or access you don't have are required;
  - a security boundary requires explicit authorization (granting access, exposing an endpoint, weakening a control);
  - required information cannot be determined independently (not in the repo, not in official docs, not derivable from evidence).
  Never use a question as a substitute for investigation, and never ask merely to confirm a plan that evidence already supports.
- Git: work on a branch, open a PR, never push to `main`/`master` directly (a hook enforces this). Commit only when the task or project convention calls for it.
- Do not weaken security controls, tests, linters or hooks to make something pass.

## 5. Speed rule
Research depth is proportional to risk: LOW → repo evidence + tests; MEDIUM → repo + official docs + tests; HIGH → repo + runtime + authoritative docs/standards + independent review + strong validation. Do not research trivial decisions, do not write documents nobody will read, do not rerun a failing command without understanding the failure.
