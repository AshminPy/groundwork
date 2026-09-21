# VALIDATE playbook

## Goal
Prove whether something behaves as required, using the strongest evidence available, and report PASS only for what was actually checked.

## Workflow
1. Write down the requirements being validated as checkable statements (from the spec, OpenSpec scenarios, the task, or the user).
2. Choose the strongest applicable evidence per requirement: runtime behaviour > tests > configuration > code inspection > assumption. Follow the ladder in `evidence-policy.md` §5, deriving commands from the project's own files.
3. Use judgment on scope: do not demand live production testing when the changed behaviour does not depend on live conditions; do demand the real path (real request, real cluster read, real log/metric) when it does.
4. Run the checks. Record the exact command and the result line for each.
5. Classify each requirement: PASS (proven), FAIL (proven wrong), NOT VERIFIED (could not be checked — say why).
6. Overall: PASS only if every requirement passed; PARTIAL if some passed and some are NOT VERIFIED; FAIL if any failed.

## Evidence
- One real observation per requirement. A green CI badge proves the pipeline, not the behaviour; a mock proves the mock.

## Ask Before Acting When
- The validation would change production state, needs credentials or access you lack, or the requirement itself is undefined. Otherwise validate what can be validated and mark the rest NOT VERIFIED.

## Completion Criteria
- Every requirement has a classification backed by an observation, and the overall result follows the rule in step 6.

## Output Format
```
Result: PASS / FAIL / PARTIAL / NOT VERIFIED
Verified:
- <requirement — command → observed result>
Failed:
- <actual failures only, with the observed output; omit if none>
Evidence:
- <proof supporting the result that is not already shown above>
Next: <one action: fix, re-run, or obtain the missing access>
```
