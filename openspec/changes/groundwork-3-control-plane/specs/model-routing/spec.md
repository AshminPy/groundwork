# Spec Delta

## Purpose

Chooses the model and effort for each stage and agent, accuracy first and cost second, and keeps working when the console mod isn't available.

## ADDED Requirements

### Requirement: Each agent declares its model and effort
Every Groundwork agent SHALL declare a model and effort. When the mod is loaded, an agent that is about to start or resume with a different model SHALL be corrected to the declared model, or to a per-task raise recorded by the planner. It SHALL be denied if that model isn't available.

#### Scenario: Wrong model at start
- **WHEN** an agent is about to start with a model other than its declared one
- **THEN** it starts with the declared model

### Requirement: The planner may raise effort within bounds
The planner SHALL be able to set a higher effort, or a stronger model, for a single task, recorded as a decision with a reason. No task SHALL go below its agent's declared model or effort.

#### Scenario: Hard Terraform task
- **WHEN** the planner marks T2 as needing opus for builder-terraform
- **THEN** that builder runs T2 on opus, and the decision is recorded

### Requirement: Lowering a model needs eval evidence
A release that lowers any agent's declared model or effort SHALL fail the release gate unless the eval shows no loss of accuracy for that agent's cases.

#### Scenario: Downgrade without eval
- **WHEN** a release lowers final-reviewer from opus to sonnet with no eval results attached
- **THEN** the release gate fails

### Requirement: Main-session routing changes only at stage boundaries
Where the mod is loaded and routing is turned on, the main session's model and effort SHALL change only when the run's stage changes, not on every request. Routing SHALL be off by default. Where the mod isn't loaded, the profile's default model SHALL be used.

#### Scenario: Routing off
- **WHEN** routing is off
- **THEN** every main-session request uses the profile default

#### Scenario: Stage change
- **WHEN** routing is on and a T3 run moves from planning to build
- **THEN** the main session's model changes once, at that boundary

### Requirement: Model choices are recorded
The model and effort used by each agent run and each main-session stage SHALL be recorded in telemetry.

#### Scenario: Telemetry record
- **WHEN** an agent finishes
- **THEN** its telemetry record holds the model and effort it used
