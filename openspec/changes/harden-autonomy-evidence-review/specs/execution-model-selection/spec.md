## MODIFIED Requirements

### Requirement: Review gate recognises every reviewer shape
The review gate SHALL count an independent review only when the session transcript contains an `Agent`/`Task` subagent call whose `subagent_type` or `name` contains "review". A `Skill` call whose name contains "review" runs inside the author's own conversation and SHALL NOT count as independent. The free-text `description` SHALL NOT count, because an unrelated call such as "Review existing tests before implementing" would otherwise satisfy the gate by coincidence. Which content the review covered is decided by the `review-independence` capability.

#### Scenario: Reviewer teammate
- **WHEN** the lead spawns a teammate with `name: "security-reviewer"` and no `subagent_type`
- **THEN** the review gate treats it as an independent review

#### Scenario: Inline skill review
- **WHEN** the only review in the transcript is a `Skill` call such as `ecc:orch-review`
- **THEN** the review gate still blocks a complete, uncommitted OpenSpec change

#### Scenario: "review" only in a description
- **WHEN** the only match is the word "review" inside an Agent call's `description` (for example an Explore call described as "Review existing test layout")
- **THEN** the review gate still blocks a complete, uncommitted OpenSpec change

#### Scenario: Non-reviewer teammate only
- **WHEN** the only Agent calls in the transcript are implementers or researchers with no "review" in `subagent_type` or `name`
- **THEN** the review gate still blocks a complete, uncommitted OpenSpec change
