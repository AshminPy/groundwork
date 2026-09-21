# AUDIT playbook

## Goal
Judge whether an implementation, configuration, policy or design safely meets a stated requirement, reporting only findings that matter and passing valid work without inventing objections.

## Workflow
1. Determine the requirement being evaluated (security, least privilege, correctness, reliability, readiness, a standard) and the scope under review.
2. Inspect the actual artefact and its evidence: code, IAM bindings, manifests, Terraform, tests, runtime state. Read what you judge; do not audit from a summary.
3. Compare actual behaviour against the requirement; for security and IAM, reason about blast radius, privilege escalation paths, secrets exposure, and destructive capability, not style.
4. Classify only material findings: MUST FIX when it affects correctness, security, reliability, deployment or the stated goal; NICE TO HAVE when useful but not blocking. Skip theoretical or cosmetic points unless they create realistic risk.
5. Reproduce a finding when it is cheap (a command, a policy simulation, a test) and cite the exact location.
6. Return PASS when the work safely meets the requirement. Do not search for reasons to reject valid work.

## Evidence
- File:line or resource identifiers for every finding; the requirement text or standard the finding violates; reproduction output where obtained.

## Ask Before Acting When
- The requirement or acceptable risk level is undefined and the verdict depends on it. Otherwise audit against the evident requirement and state the assumption.

## Completion Criteria
- A verdict with every MUST FIX finding evidenced and located; NICE TO HAVE items listed without blocking; sections with nothing material are omitted, not padded.

## Output Format
Main response headings: **Result** (pass / pass with issues / fail / not verified) · **MUST FIX** (omit if none) · **NICE TO HAVE** (only when valuable) · **Evidence summary**.
Technical details carries locations (file:line / resource) and reproduction output per finding.
Then, per `output-contract.md`: `Technical details` and `Evidence & references` when they add something.
