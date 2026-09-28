# evidence-taxonomy Specification

## Purpose
Extends `evidence-policy.md`'s existing label set so genuinely indeterminate and genuinely conflicting evidence have first-class, honest labels instead of being folded into "unverified" or silently resolved into a confident answer. Strengthens the existing RCA rule to require one of these labels when the evidence chain does not support a root cause. Rule text only — no hook, no new file, no enforcement mechanism.

## ADDED Requirements

### Requirement: UNKNOWN as a first-class evidence label
The evidence policy SHALL provide an `UNKNOWN` label, distinct from `UNVERIFIED`, for a claim that cannot be determined from any available evidence source (repository, runtime, official documentation, standards, or established practice) — not merely a claim that has not yet been checked.

#### Scenario: Genuinely undeterminable fact
- **WHEN** a RESEARCH or TROUBLESHOOT task reaches a question with no authoritative source, no repository evidence, and no runtime evidence available
- **THEN** the response states `UNKNOWN` rather than a plausible-sounding answer, an `ASSUMPTION`, or `UNVERIFIED` (which implies a check was merely skipped, not that none was possible)

### Requirement: CONFLICTING EVIDENCE as a first-class evidence label
The evidence policy SHALL provide a `CONFLICTING EVIDENCE` label for a claim where two or more sources at the same or comparable priority (per `evidence-policy.md` §1) disagree and neither dominates.

#### Scenario: Two authoritative sources disagree
- **WHEN** the current repository code contradicts current official vendor documentation for the exact version in use, or two independent runtime observations disagree, and neither can be shown to be stale or wrong
- **THEN** the response states `CONFLICTING EVIDENCE`, names both sources, and does not silently pick one without saying so

### Requirement: RCA rule requires an honest label when root cause is not supported
`evidence-policy.md` §7's incident/RCA rule SHALL require a `TROUBLESHOOT`-category response to use `UNKNOWN` or `CONFLICTING EVIDENCE` (in addition to the existing "declare a hypothesis" language) when the evidence chain genuinely does not support a root-cause conclusion, rather than only softening the language around an unsupported claim.

#### Scenario: Insufficient evidence for root cause
- **WHEN** a TROUBLESHOOT investigation has a symptom (e.g. `CrashLoopBackOff`) but the available logs/events/config do not establish a causal chain
- **THEN** the response labels the state `UNKNOWN` (not a downgraded-but-still-confident guess) and names exactly what additional evidence would resolve it

#### Scenario: Two plausible causes with contradicting evidence
- **WHEN** one piece of evidence points to a resource limit and another, equally strong, points to an application bug, and nothing available adjudicates between them
- **THEN** the response labels the state `CONFLICTING EVIDENCE`, presents both, and does not pick one to sound more decisive

### Requirement: No regression to existing evidence-policy behavior
This capability SHALL be additive to `evidence-policy.md`: the existing five labels (`VERIFIED`, `UNVERIFIED`, `ASSUMPTION`, `INFERENCE`, `RUNTIME VALIDATION REQUIRED`), the evidence priority order, the DECISION record format, the validation ladder, and the completion-evidence table SHALL be unchanged.

#### Scenario: Non-regression
- **WHEN** this change is complete
- **THEN** every existing rule/hook/script file outside `evidence-policy.md` is byte-identical to its pre-change state, matching the non-regression discipline used for every prior Groundwork rule-text addition
