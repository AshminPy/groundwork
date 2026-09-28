# review-evidence-strengthening Specification

## Purpose
**Redesigned** (see `design.md` §M, Decision D3, revision history). Strengthens `require_material_review.py`'s existing, well-tested, presence-based independent-review gate so that a MUST-FIX-bearing review actually demonstrates the finding was addressed and affected validation was re-run — not merely that some tool call happened afterward. Introduces a small, structured `REVIEW RESULT` block (the same pattern already proven by the existing `Harness metadata` block) and reuses `groundwork_telemetry.py`'s already-tested test-command classification regex, rather than building a findings-parsing/tracking system or persistent storage. The existing gate's presence-based check, its known "a call merely named '…review…' satisfies it" limitation, and its fail-open design are unchanged and not being re-litigated.

## ADDED Requirements

### Requirement: Reviewers are asked to emit a structured REVIEW RESULT block
`output-contract.md` SHALL define a short, structured `REVIEW RESULT` block (fenced, label-shaped, mirroring the existing `Harness metadata` block's format) that a reviewer-shaped call is asked to emit at the end of its response, containing at minimum a verdict (`approve` or `changes-required`) and a MUST-FIX count.

#### Scenario: Reviewer emits the block
- **WHEN** a reviewer-shaped call (ECC reviewer, subagent, or teammate) completes its review
- **THEN** its response ends with a `REVIEW RESULT` block stating its verdict and MUST-FIX count

### Requirement: Absent or zero-MUST-FIX block behaves exactly as the existing gate
When no `REVIEW RESULT` block is found, or the block reports zero MUST-FIX findings, the Stop hook's behavior SHALL be unchanged from the existing presence-based gate — a reviewer-shaped call having occurred is sufficient.

#### Scenario: Clean review
- **WHEN** a reviewer-shaped call occurred and either no structured block is present or the block reports `Must-fix: 0`
- **THEN** the Stop hook allows Stop, exactly as the existing gate does today

### Requirement: MUST-FIX findings require a subsequent edit and a subsequent validation re-run before Stop
When a `REVIEW RESULT` block reports `Must-fix: N` where N > 0, the Stop hook SHALL additionally require, before allowing Stop: at least one file-editing tool call (Edit/Write/MultiEdit) observed in the transcript after the review, AND at least one test/validation-shaped Bash command (reusing `groundwork_telemetry.py`'s existing `TEST_CMD` classification regex) observed in the transcript after the review.

#### Scenario: MUST-FIX findings, no follow-up at all
- **WHEN** a review reports `Must-fix: 2` and no tool call occurs afterward
- **THEN** the Stop hook blocks, naming that MUST FIX findings appear unresolved

#### Scenario: MUST-FIX findings, edit only, no validation re-run
- **WHEN** a review reports `Must-fix: 1`, an Edit call follows, but no test/validation-shaped command is observed afterward
- **THEN** the Stop hook still blocks — an edit alone does not satisfy the requirement, closing the gap the first-pass design left open

#### Scenario: MUST-FIX findings, edit and validation re-run
- **WHEN** a review reports `Must-fix: 1`, followed by an Edit call and a test/validation-shaped Bash command
- **THEN** the Stop hook allows Stop

### Requirement: No structured findings database or persistent storage
This capability SHALL NOT persist review findings, their resolution status, or any structured record beyond what the existing transcript-scanning mechanism already reads at Stop time — no new file, no new schema, no workflow-tracking engine. The MUST-FIX count and verdict are read fresh from the transcript on each Stop evaluation, exactly like the existing gate's reviewer-shaped-call check.

#### Scenario: Simplicity check
- **WHEN** the implementation is reviewed
- **THEN** it consists of one addition to `output-contract.md` (the block format) and an extension to the existing transcript scan in `require_material_review.py` that reuses `groundwork_telemetry.py`'s existing `TEST_CMD` regex, with no new persistent storage introduced

### Requirement: Independence and diff-identity are structural, not separately tracked
Reviewer independence SHALL be relied upon as a structural property of the `Agent`/`Task` subagent or teammate spawn mechanism (fresh context by construction), and the identity of the reviewed diff SHALL be relied upon as an implicit property of the existing gate's precondition (a complete, uncommitted OpenSpec change). Neither SHALL require new explicit tracking (e.g. diff hashing).

#### Scenario: No new tracking mechanism
- **WHEN** the implementation is reviewed
- **THEN** it introduces no diff-hash comparison, no review-session identity tracking, and no mechanism beyond what already exists to establish that the review was independent and addressed the current change

### Requirement: No regression to the existing gate
The existing 14 review-gate scenarios (allow/block by reviewer-shaped call presence, committed-vs-uncommitted change detection, malformed input, no-git fail-open, the `name`-not-`description` matching rule, the "preview" vs "review" distinction) SHALL continue to pass unchanged.

#### Scenario: Non-regression
- **WHEN** this change is complete
- **THEN** every existing `test_hooks.py` review-gate case still passes, and the hook's fail-open behavior on malformed input, missing git, or an unreadable transcript is unchanged
