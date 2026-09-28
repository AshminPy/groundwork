# deterministic-safety-expansion Specification

## Purpose
**Redesigned** (see `design.md` §M, Decision D5, revision history). The first pass proposed one vague "narrow candidate, owner decides scope." This pass's builder execution roles (`builder-execution-roles`) mean Groundwork will, if approved, genuinely execute `terraform apply`, `kubectl` mutations, and similar commands — materially strengthening the case that some deterministic guard is warranted. Redesigned into a tiered, menu-based model: read-only discovery is always safe; nonprod mutation explicitly authorized by the task's own request needs no new hook (existing autonomy rule + native permission prompts suffice); production/IAM/data-destructive operations get up to three independently-approvable, narrowly-scoped deterministic guards, each structurally mirroring `block_protected_push.py`. No implementation is authorized by this specification alone — the owner must explicitly name which, if any, of the three Tier-2 candidates to approve (`design.md` §M, D5).

## ADDED Requirements

### Requirement: Tier 0 — read-only discovery is never gated
Read-only discovery commands (e.g. `terraform plan`, `kubectl get`/`describe`, cloud-CLI `list`/`describe` operations) SHALL NOT be blocked or require authorization by any mechanism introduced under this capability.

#### Scenario: Read-only command
- **WHEN** a read-only discovery command is run
- **THEN** no guard introduced under this capability evaluates or blocks it

### Requirement: Tier 1 — explicitly authorized nonprod mutation needs no new hook
A mutating operation targeting a nonprod environment, explicitly named in the user's own request, SHALL proceed under the existing `engineering-workflow.md` §4 autonomy rule and Claude Code's native Bash permission model, without a new deterministic hook.

#### Scenario: Authorized nonprod deployment
- **WHEN** the user's request explicitly names a nonprod deployment action (e.g. "deploy this to our dev GKE cluster")
- **THEN** no guard introduced under this capability blocks it; the existing autonomy rule and native permission prompts are the only gates

### Requirement: Owner names an explicit scope before any Tier-2 implementation begins
No Tier-2 guard (Terraform-prod-guard, kubectl-prod-guard, IAM-mutation-guard) SHALL be implemented from an inferred or assumed scope. The owner SHALL explicitly approve zero, one, two, or all three candidates before implementation begins on any of them.

#### Scenario: Scope decision recorded
- **WHEN** any Tier-2 guard is implemented
- **THEN** the implementing OpenSpec change cites the owner's explicit approval of that specific candidate

### Requirement: Terraform-prod-guard (candidate 1, if approved)
If approved, a PreToolUse hook SHALL deny a `terraform apply`/`destroy` invocation that has no preceding `terraform plan`-generated plan file referenced, or that targets a workspace/state-backend matching a production-naming pattern discoverable via `repository-understanding`'s environment-organization discovery step.

#### Scenario: Apply without a plan reference, production-pattern workspace
- **WHEN** `terraform apply` is invoked with no plan file argument against a workspace whose name matches the repository's own production-naming convention
- **THEN** the guard denies the operation

#### Scenario: Apply with a plan reference against a nonprod workspace
- **WHEN** `terraform apply <plan-file>` is invoked against a workspace not matching the production-naming convention
- **THEN** the guard allows the operation

### Requirement: kubectl-prod-guard (candidate 2, if approved)
If approved, a PreToolUse hook SHALL deny mutating `kubectl` verbs (`apply`, `delete`, `patch`, `scale`, `rollout`) against a context or namespace matching a production-naming pattern discoverable via `repository-understanding`.

#### Scenario: Mutating verb against a production-pattern context
- **WHEN** `kubectl apply` (or another mutating verb) targets a context/namespace matching the production-naming convention
- **THEN** the guard denies the operation

#### Scenario: Mutating verb against a nonprod context
- **WHEN** the same verb targets a context/namespace not matching the production-naming convention
- **THEN** the guard allows the operation

### Requirement: IAM-mutation-guard (candidate 3, if approved)
If approved, a PreToolUse hook SHALL deny a short, explicit list of IAM-mutating cloud-CLI command forms (e.g. `aws iam` / `gcloud iam` / `az role` create, attach, or delete operations) outright, without a production/nonprod distinction, mirroring how the existing push guard denies force-flags outright rather than pattern-matching context.

#### Scenario: IAM mutation attempted
- **WHEN** an IAM-mutating command matching the explicit list is invoked
- **THEN** the guard denies the operation regardless of target environment

### Requirement: Structurally mirrors the existing, validated push-guard pattern
Any approved Tier-2 guard SHALL follow the same structure `block_protected_push.py` was built and validated with: a PreToolUse hook, fail-open on any internal error or malformed input, depth-limited parsing of shell wrappers/`eval`, exact/explicit pattern matching — not a broad heuristic classifier.

#### Scenario: Fail-open verified
- **WHEN** an approved guard encounters malformed input, an unparseable command, or an internal exception
- **THEN** it allows the operation (fails open) rather than blocking

### Requirement: Adversarial bypass and false-positive testing, both required
Any approved Tier-2 guard SHALL be tested against bypass attempts analogous to the push guard's own 19-case suite AND against a representative set of legitimate, safe commands that must NOT be blocked, reviewed specifically for over-blocking risk by an independent security review.

#### Scenario: Bypass test coverage
- **WHEN** an approved guard ships
- **THEN** its test suite includes bypass attempts adapted to its specific scope

#### Scenario: False-positive review
- **WHEN** an approved guard ships
- **THEN** an independent security review explicitly attempts to construct a legitimate command the guard would incorrectly block, and any such case is fixed or the guard's scope is narrowed before shipping

### Requirement: Production-detection limitation is documented, not hidden
Any approved Tier-2 guard's reliance on naming-convention-based production detection (via `repository-understanding`) SHALL be documented as a known limitation, analogous to the push guard's own documented "non-exact branch names" limitation, including the degraded-protection case for a repository with no consistent naming convention.

#### Scenario: Documentation check
- **WHEN** an approved guard ships
- **THEN** its documentation states plainly that production detection is heuristic and repository-dependent, and names the degraded case

### Requirement: Escape hatch
Any approved Tier-2 guard SHALL support a `GROUNDWORK_<HOOK_NAME>=off` environment-variable opt-out, matching the existing pattern used by the snapshot and telemetry hooks.

#### Scenario: Opt-out available
- **WHEN** the environment variable is set
- **THEN** the guard allows the operation without evaluating it, and this is documented in `docs/TROUBLESHOOTING.md`

### Requirement: No implementation without this specification's scenarios passing
No Tier-2 guard SHALL be considered complete, and no task referencing it SHALL be marked done, until its adversarial bypass and false-positive test scenarios both have evidence, matching the audit's core principle that a task is complete only when its stated acceptance criteria are demonstrated, not when code exists.

#### Scenario: Completion check
- **WHEN** `docs/VALIDATION.md` records an approved guard's evidence
- **THEN** it shows both bypass and false-positive evidence, not test-pass counts alone
