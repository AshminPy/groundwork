# TROUBLESHOOT playbook

## Goal
Find the real cause of a failure with evidence, apply or recommend the smallest safe fix, prove it, and say plainly what is still unverified.

## Workflow
1. Establish expected behaviour (spec, docs, tests, the user's statement).
2. Establish actual behaviour by reproducing with the exact failing command, request, test or deployment path; capture the real error, exit code, log or trace.
3. Gather evidence: logs, events, config, code, recent changes (`git log`), environment differences; compare a working path with the failing path side by side.
4. Separate FACT (seen in output/code/logs) from INFERENCE and HYPOTHESIS. A symptom or state (`CrashLoopBackOff`, 502, OOMKilled) is not a root cause.
5. List the plausible hypotheses; test the highest-value one first with a check that can disprove it.
6. Declare a root cause only when the evidence chain supports it (`evidence-policy.md` §7); otherwise keep it a hypothesis and say so.
7. Apply or recommend the smallest safe fix that addresses the verified cause — no stacked unrelated fixes, no retries/sleeps/suppression without a verified reason.
8. Validate: the original failing path now succeeds, related tests pass, runtime shows the expected behaviour.
9. Check for material regression risk and for siblings of the same defect (same pattern elsewhere).
10. State exactly what remains unverified.

## Evidence
- The reproduced failure and the post-fix success, both as real output. Correlation is not causation; timing plus mechanism is.

## Ask Before Acting When
- Reproduction needs credentials, access or an environment you do not have; validation would touch production; or the fix requires a destructive or architectural change. Otherwise investigate — never substitute a question for evidence you could gather.

## Completion Criteria
- Failure reproduced → cause demonstrated → minimal fix applied or recommended → original path re-run and passing → regressions checked; or an honest NOT VERIFIED / BLOCKED with the missing piece named.

## Output Format
```
Status: FIXED / ROOT CAUSE FOUND / NOT VERIFIED / BLOCKED
Root cause: <one or two lines; "hypothesis" if not proven>
Evidence:
- <the strongest supporting evidence — exact lines, not the whole log>
Fix: <what changed, or what is recommended>
Validation: <command + result proving the original path now works>
Remaining risk: <regressions, siblings, unverified parts>
Next: <one action>
```
