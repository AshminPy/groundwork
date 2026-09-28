# deterministic-safety-expansion Specification

## Purpose
**Decision-pending (design.md Decision D5).** The requesting brief asks Groundwork 2.0 to strengthen deterministic safety beyond Git for destructive cloud/IaC/production/IAM operations; Groundwork's own prior, evidence-driven conclusion (`docs/FUTURE-SCOPE.md` §10) explicitly defers this pending a real task demonstrating the advisory rule is insufficient, and no such task has occurred yet. This specification states requirements that apply **only if the owner approves a scope for this capability** (design.md §G, D5) — it does not authorize building anything, and the default recommendation in design.md is to approve nothing broader than a narrow, evidence-matched candidate, or to defer entirely.

## ADDED Requirements

### Requirement: Scope is explicitly named by the owner before any implementation
No implementation of this capability SHALL begin from an inferred or assumed scope. The owner SHALL name one of: no Phase 6 work; a narrow IaC-apply-without-plan guard; or a specific, explicitly enumerated list of destructive cloud-CLI patterns.

#### Scenario: Scope decision recorded
- **WHEN** this capability is implemented
- **THEN** the implementing OpenSpec change's proposal cites the owner's explicit scope decision, not an inference from this document

### Requirement: Structurally mirrors the existing, validated push-guard pattern
If implemented, the new deterministic guard SHALL follow the same structure that `block_protected_push.py` was built and validated with: a PreToolUse hook, fail-open on any internal error or malformed input, depth-limited parsing of shell wrappers/`eval`, exact pattern matching against a named, documented, narrow set of commands — not a broad heuristic classifier.

#### Scenario: Fail-open verified
- **WHEN** the hook encounters malformed input, an unparseable command, or an internal exception
- **THEN** it allows the operation (fails open) rather than blocking, matching every existing Groundwork PreToolUse/Stop hook

### Requirement: Adversarial bypass testing
If implemented, the guard SHALL be tested against the same class of bypasses the push guard was adversarially tested against in its own development (nested shells, `eval`, nested wrapper commands), reproduced and fixed before shipping.

#### Scenario: Bypass test coverage
- **WHEN** this capability ships
- **THEN** its test suite includes bypass attempts analogous to the 19 push-guard test cases, adapted to the approved scope

### Requirement: False-positive testing — this capability's distinguishing requirement
If implemented, the guard SHALL additionally be tested against a representative set of legitimate, safe commands that must NOT be blocked, reviewed specifically for over-blocking risk — a requirement the push guard's own original development did not need to carry as heavily, because "any git push to a protected branch" has almost no legitimate exception, whereas cloud/IaC commands frequently do (a `terraform apply` in a sandboxed dev account is routine; the same command in production is not).

#### Scenario: False-positive review
- **WHEN** this capability ships
- **THEN** a security-reviewer's independent review explicitly attempts to construct a legitimate command the guard would incorrectly block, and any such case is fixed or the guard's scope is narrowed before shipping

### Requirement: Escape hatch
If implemented, the guard SHALL support a `GROUNDWORK_<HOOK_NAME>=off` environment-variable opt-out, matching the existing pattern used by the snapshot and telemetry hooks.

#### Scenario: Opt-out available
- **WHEN** the environment variable is set
- **THEN** the guard allows the operation without evaluating it, and this is documented in `docs/TROUBLESHOOTING.md`

### Requirement: No implementation without this specification's scenarios passing
This capability SHALL NOT be considered complete, and no task referencing it SHALL be marked done, until the adversarial bypass and false-positive test scenarios above both have evidence, matching the audit's core principle that a task is complete only when its stated acceptance criteria are demonstrated, not when code exists.

#### Scenario: Completion check
- **WHEN** `docs/VALIDATION.md` records this capability's evidence
- **THEN** it shows both bypass and false-positive evidence, not test-pass counts alone
