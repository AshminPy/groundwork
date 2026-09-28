# investigation-continuity Specification

## Purpose
Closes the one Groundwork 2.0 acceptance criterion confirmed fully unmet by this audit: a rejected hypothesis from an investigative (typically TRIVIAL/STANDARD-tier, non-OpenSpec-tracked) session must not resurface as active or verified after context compaction or in a fresh session. **The mechanism is decision-pending (design.md Decision D2, Option A vs Option B) — this specification states the required observable behavior, which both options must satisfy, without presupposing which is chosen.** Requirements below apply once an option is selected and implemented; none are implemented yet.

## ADDED Requirements

### Requirement: Rejected hypotheses do not resurface after recovery
Whatever mechanism is chosen, the harness SHALL NOT present a hypothesis previously and explicitly rejected in the same investigation as active, unverified-but-plausible, or verified after a context compaction or a fresh session recovering the same work.

#### Scenario: Compaction mid-investigation
- **WHEN** a TROUBLESHOOT session establishes and explicitly rejects hypothesis A (with evidence why), continues investigating hypothesis B, and then context compaction occurs
- **THEN** the post-compaction session does not re-propose hypothesis A as a live candidate; if A is mentioned again, it is stated as already-rejected with the reason

#### Scenario: Fresh-session recovery of the same investigation
- **WHEN** a fresh session is asked to continue an investigation left mid-way by a prior session that rejected one or more hypotheses
- **THEN** the fresh session's reconstruction of state names the rejected hypotheses as rejected before proposing any new direction, and does not re-test a rejected hypothesis without new evidence that specifically reopens it

### Requirement: Recovered state is revalidated against current repository/runtime before being trusted
Recovered facts, decisions, and hypothesis status SHALL be treated as hints to verify against current repository/runtime evidence, not as ground truth, consistent with the existing `evidence-policy.md` §8 principle ("repository/runtime wins over memory") extended to whatever continuity mechanism is chosen.

#### Scenario: Stale recovered fact contradicted by current evidence
- **WHEN** recovered state says a hypothesis was rejected for a reason that current repository/runtime evidence no longer supports (e.g. the rejecting condition has since changed)
- **THEN** the mismatch is reported explicitly and current evidence governs, not the stale recovered state

### Requirement: No chain-of-thought persisted
Whatever is persisted for continuity SHALL contain only conclusions, evidence references, decisions, and task/investigation state — never hidden reasoning or chain-of-thought.

#### Scenario: Content check
- **WHEN** the chosen mechanism's persisted content is inspected
- **THEN** it contains objective, established facts, rejected hypotheses with their reasons, open hypotheses, evidence references, decisions, and next action only

### Requirement: Deterministic compaction and fresh-session-recovery test coverage
The chosen mechanism SHALL be proven, not merely implemented: a deterministic test suite SHALL construct a long investigation (multiple established facts, multiple rejected hypotheses, several decisions, changed files, validation results, unresolved work), simulate compaction and a fresh-session handoff, and verify correct reconstruction of objective, completed work, remaining work, proven facts, unverified facts, rejected hypotheses (explicitly asserted as still rejected), decisions, and next action.

#### Scenario: Test suite existence and coverage
- **WHEN** this capability ships
- **THEN** a test explicitly named for the "rejected hypothesis must not become active or verified after recovery" case exists and passes, separate from and in addition to general reconstruction tests

### Requirement: No regression to the existing OpenSpec-tracked continuation model
`engineering-workflow.md` §7's existing continuation procedure and `groundwork_session_snapshot.py`'s existing deterministic snapshot behavior for MATERIAL, OpenSpec-tracked work SHALL be unchanged in their current guarantees, whichever option is chosen.

#### Scenario: Non-regression
- **WHEN** this capability ships
- **THEN** the existing continuation live-run evidence (VALIDATION.md 1.1.0) remains reproducible unchanged
