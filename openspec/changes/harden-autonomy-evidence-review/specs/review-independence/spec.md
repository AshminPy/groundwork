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

### Requirement: Pull requests carry a current independent review
A non-draft `gh pr create` SHALL be denied until the most recent reviewer subagent in the session reported `Must-fix: 0` and named, as `Reviewed:`, the content fingerprint of the commit being published. A pull request check SHALL fail while the PR description does not record such an approval of the current head.

#### Scenario: PR without a review
- **WHEN** `gh pr create` runs and no reviewer subagent reviewed the commit
- **THEN** the command is denied, and the reason gives the commit fingerprint and how to get the review

#### Scenario: Draft PR
- **WHEN** `gh pr create --draft` runs before any review
- **THEN** it is allowed, and the PR check skips drafts

#### Scenario: Push after approval
- **WHEN** a code change is pushed to a PR after the recorded review
- **THEN** the PR check fails as changed after the review until a fresh review is recorded
