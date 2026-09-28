# builder-execution-roles Specification

## Purpose
Extends Groundwork's existing main-session/subagent/Agent-Team execution-model selection (`engineering-workflow.md` §6) with four logical, dynamically-instantiated role personas — Infrastructure Engineer, Platform Engineer, Delivery Engineer, Application Engineer — so that infrastructure/platform/delivery/application-supporting outcomes are built, not only reviewed or troubleshot, without introducing permanent per-role agent files, new task-routing categories, or new orchestration code. Composes `repository-understanding`, curated ECC agents/skills, native Claude reasoning, and task-driven MCP/CLI access; does not duplicate any of them.

## ADDED Requirements

### Requirement: Roles are dynamically instantiated personas, not permanent agent files
The four builder roles SHALL be defined as short scope/evidence-source descriptions in rule text and instantiated as the `name`/prompt of a dynamically-spawned subagent or Agent Team teammate at task time. No permanent `.claude/agents/*.md` file SHALL be created per role.

#### Scenario: Role instantiation
- **WHEN** a task is delegated to, for example, the Infrastructure Engineer role
- **THEN** the delegation is an `Agent` tool call with a `name` and task-specific prompt derived from the role's rule-text description, not an invocation of a persisted agent definition file

### Requirement: Builder roles do not introduce new task-routing categories
Infrastructure/platform/delivery/application-building requests SHALL continue to route to the existing IMPLEMENT, DEPLOY, DESIGN, or PLAN categories per `task-routing.md`, unchanged. Builder roles are an execution-model detail, not a routing category.

#### Scenario: Routing unaffected
- **WHEN** the request is "build the Terraform for this infrastructure"
- **THEN** the task routes to IMPLEMENT as it does today, and the builder-role selection happens within that category's existing workflow

### Requirement: Automatic role and execution-model selection
Groundwork SHALL select the appropriate role (if any) and execution model (main session, subagent, or Agent Team) automatically from the task's domain and independence characteristics, without requiring the user to name an agent, role, or specialist.

#### Scenario: Simple, narrow builder task
- **WHEN** the request is "add another variable to this Terraform module"
- **THEN** execution stays in the main session; no role or subagent is invoked

#### Scenario: Focused, single-domain builder task
- **WHEN** the request is "build the Terraform for this infrastructure" and no other genuinely independent workstream exists
- **THEN** a single Infrastructure Engineer subagent is used, followed by independent review

#### Scenario: Genuinely independent cross-domain task
- **WHEN** the request requires infrastructure, platform, delivery, and application changes that are genuinely independent workstreams meeting the existing Agent Team justification criteria in `engineering-workflow.md` §6
- **THEN** an Agent Team composed of the relevant builder-role personas may be used

#### Scenario: Cross-domain task without genuine independence
- **WHEN** a cross-domain task's workstreams are not genuinely independent, or Agent Teams are disabled, or the session is non-interactive
- **THEN** the same decomposition runs on subagents instead, and no team is reported

### Requirement: Application Engineer role is scoped to supporting infra/platform/delivery outcomes
The Application Engineer role SHALL be used only in service of infrastructure, platform, or delivery outcomes (e.g. health checks, telemetry, Kubernetes-aware configuration, cloud integration code), and SHALL NOT function as a general-purpose software-development role for unrelated application feature work.

#### Scenario: Scope check
- **WHEN** a request is pure application feature development with no infrastructure/platform/delivery connection
- **THEN** it is handled through the existing IMPLEMENT playbook without invoking the Application Engineer persona

### Requirement: Closed-loop build, deploy, and runtime validation
A builder-role deployment task SHALL NOT be reported deployed or complete without runtime validation; when runtime validation fails, the failure SHALL be diagnosed using the existing TROUBLESHOOT workflow's evidence-first RCA discipline, the smallest safe verified cause SHALL be fixed, and the same validation SHALL be re-run before any completion claim.

#### Scenario: Runtime validation fails after deployment
- **WHEN** a deployment's post-deploy runtime check fails
- **THEN** the response does not claim DEPLOYED or COMPLETE; the failure is diagnosed via the TROUBLESHOOT discipline, a fix is applied, and the same validation is re-run before any completion claim

### Requirement: Completion truth uses the existing evidence-policy model, not a new status system
Builder-role work SHALL use the existing completion-evidence categories (Code / Tests / Reviewed / Merged / Deployed / Live validated) and overall states (COMPLETE / PARTIAL / BLOCKED / FAILED) exactly as defined in `evidence-policy.md` §6 — no separate status vocabulary SHALL be introduced for infrastructure, platform, or delivery work.

#### Scenario: Plan passed, apply not performed
- **WHEN** a Terraform plan succeeds but no apply has been run
- **THEN** `Deployed` is reported as not yet done and `Overall` is `PARTIAL`, using the existing table — never a builder-specific status term

#### Scenario: Applied but runtime validation unavailable
- **WHEN** an apply succeeds but runtime validation cannot be performed (no access, no credentials)
- **THEN** the response states `RUNTIME VALIDATION REQUIRED` per the existing evidence-policy label and does not report COMPLETE

### Requirement: Authorization gates mutation, not discovery
Read-only discovery operations (plan/dry-run, `get`/`describe`/`list` commands) SHALL proceed without additional authorization. Nonprod mutations explicitly named in the user's request SHALL proceed under the existing `engineering-workflow.md` §4 autonomy rule. Production, IAM, data-destructive, or paid-resource-creating operations SHALL require explicit authorization before execution, consistent with the existing autonomy rule and any deterministic guard approved under the `deterministic-safety-expansion` capability.

#### Scenario: No authorization for a mutating operation
- **WHEN** a mutating operation requires authorization per the existing autonomy rule and authorization is absent
- **THEN** execution stops before the mutation, and all completed, safe evidence/work up to that point is preserved and reported

### Requirement: No new orchestration mechanism
This capability SHALL be implemented entirely as rule-text extensions to `engineering-workflow.md` §6 and a cross-reference addition to `deploy.md`. It SHALL NOT introduce a scheduler, message bus, team manager, state machine, or any other orchestration code beyond what Claude Code's native `Agent` tool and Agent Team mechanism already provide.

#### Scenario: Implementation footprint check
- **WHEN** this capability's implementation diff is reviewed
- **THEN** it touches only existing rule/playbook files and contains no new orchestration module
