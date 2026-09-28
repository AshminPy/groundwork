# repository-understanding Specification

## Purpose
One shared discovery procedure, used by the builder execution roles and the existing DESIGN/IMPLEMENT/DEPLOY/AUDIT playbooks alike, so that generated infrastructure/platform/delivery code belongs in the target repository rather than merely working in theory. Extends three existing playbooks with a domain-specific discovery checklist; does not introduce a new always-loaded rule, hook, agent, or state file. Builds directly on `engineering-workflow.md` §2's existing UNDERSTAND step and `architecture-quality.md` §5's existing "project conventions win over generic vendor guidance" rule.

## ADDED Requirements

### Requirement: Proportional discovery
Repository discovery SHALL be proportional to the task's risk and scope, matching the existing evidence-policy speed rule — a narrow change (e.g. adding one variable to an existing module) SHALL NOT require a whole-repository scan; a task that introduces a new environment, cluster, or pattern SHALL include the domain-specific discovery checklist (existing module/chart/pipeline structure, naming and variable conventions, environment/workspace organization, IAM and networking patterns, state/backend patterns, CI/delivery patterns, testing conventions, and the closest analogous existing implementation).

#### Scenario: Small, narrow change
- **WHEN** the request is "add another variable to this Terraform module"
- **THEN** discovery is limited to the module and its immediate conventions, not a repository-wide scan

#### Scenario: New environment or pattern
- **WHEN** the request is "create another nonprod GKE cluster following our existing pattern"
- **THEN** discovery identifies the closest existing analogous cluster definition, its module structure, naming conventions, and environment organization before any code is generated

### Requirement: Repository pattern wins over generic knowledge
When project evidence shows an established pattern for the domain in question, that pattern SHALL be followed in preference to generic or textbook conventions, unless the pattern is demonstrably unsafe, broken, deprecated, or incompatible with the stated requirement — in which case the deviation and its reason SHALL be stated explicitly.

#### Scenario: Repository convention differs from generic best practice
- **WHEN** the repository's established convention differs from a commonly recommended generic approach, and the repository convention is safe and compatible with the requirement
- **THEN** the repository convention is followed, and the response does not silently substitute the generic approach

#### Scenario: Repository pattern is unsafe or deprecated
- **WHEN** the closest existing analogous implementation uses a pattern that is demonstrably unsafe, broken, deprecated, or incompatible with the current requirement
- **THEN** the implementation deviates from that pattern and states why, rather than blindly replicating it

### Requirement: One shared procedure, not per-role duplication
The discovery procedure and the pattern-wins rule SHALL be defined in exactly one place (this capability) and referenced, not restated, by every builder execution role and by any existing playbook that performs implementation or deployment work.

#### Scenario: Consistency check
- **WHEN** `implement.md`, `deploy.md`, and `design.md` are inspected
- **THEN** each references the same discovery checklist and pattern-wins rule rather than each defining its own variant

### Requirement: No new always-loaded content
This capability SHALL be implemented entirely within playbooks that are already read on demand per `task-routing.md`, and SHALL NOT add a new always-loaded rule file.

#### Scenario: Cost check for non-builder tasks
- **WHEN** a task is routed to a category other than IMPLEMENT, DEPLOY, or DESIGN, or is a non-infrastructure IMPLEMENT/DEPLOY/DESIGN task
- **THEN** no additional context is loaded for this capability
