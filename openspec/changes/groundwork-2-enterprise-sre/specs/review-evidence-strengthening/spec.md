# review-evidence-strengthening Specification

## Purpose
Strengthens `require_material_review.py`'s existing, well-tested, presence-based independent-review gate with one narrow additional check — that a review which raised MUST-FIX-shaped findings was followed by further work before the session is allowed to stop again — without building a findings-parsing/tracking system. The existing gate mechanism, its known "a call merely named '…review…' satisfies it" limitation, and its fail-open design are unchanged and not being re-litigated.

## ADDED Requirements

### Requirement: MUST-FIX-bearing review requires demonstrable follow-up work
When a reviewer-shaped call's own output (as found in the session transcript) contains a MUST-FIX-shaped marker, the Stop hook SHALL additionally require at least one further tool call (an edit, a test run, or equivalent) to have occurred after that review before allowing Stop, in addition to the existing requirement that a reviewer-shaped call occurred at all.

#### Scenario: Review with MUST FIX findings, no follow-up work
- **WHEN** a complete-and-uncommitted OpenSpec change's transcript contains a reviewer-shaped call whose output contains a MUST-FIX-shaped marker, and no tool call occurs afterward
- **THEN** the Stop hook blocks, naming that MUST FIX findings appear unresolved

#### Scenario: Review with MUST FIX findings, followed by a fix
- **WHEN** the same transcript additionally contains an Edit/Write/Bash tool call after the review
- **THEN** the Stop hook allows Stop (the gate does not verify the fix is correct — only that further work occurred, matching the existing gate's "review happened, not its quality" philosophy)

#### Scenario: Review with no MUST-FIX-shaped output
- **WHEN** a reviewer-shaped call occurred and its output contains no MUST-FIX-shaped marker
- **THEN** behavior is unchanged from the existing gate (allow, as today)

### Requirement: No regression to the existing gate
The existing 14 review-gate scenarios (allow/block by reviewer-shaped call presence, committed-vs-uncommitted change detection, malformed input, no-git fail-open, the `name`-not-`description` matching rule, the "preview" vs "review" distinction) SHALL continue to pass unchanged.

#### Scenario: Non-regression
- **WHEN** this change is complete
- **THEN** every existing `test_hooks.py` review-gate case still passes, and the hook's fail-open behavior on malformed input, missing git, or an unreadable transcript is unchanged

### Requirement: No structured findings database
This capability SHALL NOT persist review findings, their resolution status, or any structured record beyond what the existing transcript-scanning mechanism already reads at Stop time — no new file, no new schema, no workflow-tracking engine.

#### Scenario: Simplicity check
- **WHEN** the implementation is reviewed
- **THEN** it consists of an extension to the existing transcript scan in `require_material_review.py`, with no new persistent storage introduced
