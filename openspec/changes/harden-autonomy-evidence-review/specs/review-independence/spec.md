## ADDED Requirements

### Requirement: Review bound to reviewed content
A review SHALL clear the MATERIAL Stop gate only when it was produced by an Agent or Task subagent call and its result contains a REVIEW RESULT block whose `Reviewed:` field equals the change fingerprint at the time of the Stop.

#### Scenario: Current review clears the gate
- **WHEN** the most recent subagent review reports `Must-fix: 0` and `Reviewed: <fingerprint>` equal to the current fingerprint
- **THEN** the Stop is allowed

#### Scenario: Code changed after review
- **WHEN** a file changes after the most recent review, so the current fingerprint differs from `Reviewed:`
- **THEN** the Stop is blocked, and the message names both fingerprints and asks for a fresh review

#### Scenario: Inline skill or self review
- **WHEN** the only review comes from a Skill call, or from the author's own reply text
- **THEN** it does not count, and the Stop is blocked
