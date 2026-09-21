# IMPLEMENT playbook

## Goal
Make the smallest safe change that delivers the requested behaviour, prove it with the project's own validation, and report completion truthfully.

## Workflow
1. Understand the requested outcome; classify the tier per `engineering-workflow.md` §1 (TRIVIAL / STANDARD / MATERIAL) and follow that section's process — OpenSpec, DECISION records and independent review for MATERIAL work are not optional.
2. Inspect the existing implementation, tests, configuration and conventions before writing anything.
3. Identify the smallest safe change; preserve existing working behaviour; put foreseeable variation points behind configuration or an interface (`architecture-quality.md` §3); no unrelated refactoring.
4. Implement only what is required, with tests for the changed behaviour.
5. Run the narrowest relevant check first, then the project's real test/lint/build commands (`evidence-policy.md` §5 — from README, Makefile, manifests or CI, never invented).
6. Investigate a failure before changing more code; never weaken tests, linters or hooks to get green.
7. Confirm the requested behaviour on the real path when runtime matters.
8. Report with the completion block.

## Evidence
- Exact command + result line for every validation claim; a diff summary for the change; runtime evidence for runtime behaviour. Mocks never prove runtime.

## Ask Before Acting When
- The requested behaviour is ambiguous in a way that changes what gets built, the target (file, service, environment) cannot be determined, or the change is destructive/irreversible. Otherwise choose the safest reading, state it in one line, and implement.

## Completion Criteria
- Requested behaviour confirmed, project validation green (or the failure named), review done for MATERIAL work, completion block filled with evidence. A pre-existing failing test still makes `Tests: ❌` and `Overall: PARTIAL`.

## Output Format
```
Status: COMPLETE / PARTIAL / BLOCKED / FAILED   (= Overall of the completion block)
Changed:
- <meaningful changes only — no per-edit narration>
Validation:
  Code / Tests / Reviewed / Merged / Deployed / Live validated — ✅/❌/N/A each with its evidence (engineering-workflow.md §3)
Remaining:
- <only when not COMPLETE: what is left, what blocks it>
```
