# task-routing Specification

## Purpose
Routes every substantive request to exactly one task playbook, loads only that playbook, asks for clarification only when missing information is material, and shapes the user-facing answer with a category-specific, narration-free output contract — without changing any existing Groundwork rule, hook or safety control.

## Requirements

### Requirement: One primary category per task
The harness SHALL classify each substantive request into exactly one of RESEARCH, EXPLAIN, DESIGN, PLAN, IMPLEMENT, TROUBLESHOOT, VALIDATE, AUDIT, DEPLOY, DOCUMENT, and SHALL map COMPARE/DECIDE/AUTOMATE/REPORT/VERIFY into those categories rather than creating new ones.

#### Scenario: Representative requests
- **WHEN** the request is "Explain Kubernetes readiness probes" / "Research current readiness probe best practices" / "Design readiness probes for our API" / "Pods started restarting after adding probes" / "Add readiness probes to this Helm chart" / "Verify our readiness probes are correct" / "Review this IAM policy for security issues" / "Deploy this application to our dev GKE cluster" / "Create a migration plan for these AWS accounts" / "Write a runbook for this process"
- **THEN** the selected categories are EXPLAIN / RESEARCH / DESIGN / TROUBLESHOOT / IMPLEMENT / VALIDATE / AUDIT / DEPLOY / PLAN / DOCUMENT respectively

### Requirement: Only the selected playbook is loaded
Playbooks SHALL live outside the auto-loaded rules directory and SHALL be read only after selection; the router SHALL NOT embed playbook contents.

#### Scenario: Install layout
- **WHEN** Groundwork is installed
- **THEN** `task-routing.md` is under `~/.claude/rules/groundwork/` and the ten playbooks are under `~/.claude/groundwork/playbooks/`, and no playbook is under `~/.claude/rules/`

### Requirement: Material-ambiguity clarification only
The harness SHALL ask before acting only when missing information could materially change correctness, architecture, implementation, safety, permissions, the target environment, a destructive action, or the requested outcome and cannot be determined from available evidence; otherwise it SHALL proceed on the safest reasonable assumption.

#### Scenario: Destructive action with ambiguous target
- **WHEN** the request is "Delete the environment" and more than one environment exists
- **THEN** the harness asks which environment before any destructive step

#### Scenario: Non-material request
- **WHEN** the request is "Explain Terraform state"
- **THEN** the harness answers without asking a clarifying question

### Requirement: Playbook structure and output contract
Every playbook SHALL contain the sections Goal, Workflow, Evidence, Ask Before Acting When, Completion Criteria, Output Format, and SHALL stay small; every response SHALL follow the global three-layer output contract in `rules/output-contract.md` — a plain-language main response first, `Technical details` only when useful technical evidence exists, `Evidence & references` only when the conclusion depends on sources — omitting empty sections, translating evidence into understandable language, never implying verification that did not happen, and never printing routing debug lines unless asked.

#### Scenario: Structural check
- **WHEN** the test suite runs
- **THEN** each of the ten playbooks exists, has the six sections, is within the size cap, names its main-response headings, and inherits the layers by reference rather than restating them; `rules/output-contract.md` exists, is within its size cap, and contains the three layers and the omit-empty, honest-validation and no-debug-lines rules

#### Scenario: Representative outputs
- **WHEN** fresh sessions answer representative IMPLEMENT, TROUBLESHOOT, AUDIT, VALIDATE, RESEARCH and EXPLAIN prompts
- **THEN** each answer leads with the result, uses the category's main headings, prints no `Routing:`/`Playbook:` lines and no empty "none" sections, and places commands, errors and traceability under `Technical details` rather than in the main text

### Requirement: Non-regression of existing Groundwork controls
The routing layer SHALL be additive: existing rules, hooks, settings merge and completion semantics SHALL be byte-identical before and after, and the rule text SHALL state that an existing Groundwork rule wins over a playbook on conflict.

#### Scenario: Critical files unchanged
- **WHEN** the change is complete
- **THEN** the SHA-256 of `rules/engineering-workflow.md`, `rules/evidence-policy.md`, `rules/architecture-quality.md`, the three hooks and the three settings scripts equals the pre-change baseline, and the existing 92 hook tests still pass
