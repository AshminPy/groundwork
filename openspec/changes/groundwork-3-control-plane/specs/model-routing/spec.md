# Spec Delta

## Purpose

Chooses the model and effort for each stage and agent, putting accuracy first and cost second, and keeps working when the console mod is not available.

## ADDED Requirements

### Requirement: Each agent has a fixed model and effort
Every Groundwork agent SHALL declare its model and effort. When an agent starts, the model SHALL be checked against the agent's declaration or domain pack, and a mismatch SHALL be corrected or the start denied.

#### Scenario: Wrong model at start
- **WHEN** an agent is about to start with a model other than the one its definition declares
- **THEN** it starts with the declared model, or is denied if that model is unavailable

### Requirement: Planning and review use the strongest settings
Planner, egm and final-reviewer SHALL use the strongest configured model at high effort. A lower model or effort SHALL be used only where the eval shows no loss of accuracy.

#### Scenario: Cost change without eval
- **WHEN** a release lowers final-reviewer's model without eval results showing no accuracy loss
- **THEN** the release gate fails

### Requirement: The main session's model follows the stage
Where the console mod is loaded, the model and effort for each request from the main session SHALL be chosen from the run's tier and stage. Where it is not loaded, the profile's default model SHALL be used.

#### Scenario: T1 run
- **WHEN** the main session works on a T1 run with the mod loaded
- **THEN** its requests use the lower configured model and effort for T1

#### Scenario: No mod
- **WHEN** the mod is not loaded
- **THEN** every main-session request uses the profile default, and safety is unchanged

### Requirement: Model choices are recorded
The model and effort of each agent run and each main-session stage SHALL be recorded in telemetry, so the eval can compare accuracy and cost by model.

#### Scenario: Telemetry row
- **WHEN** an agent finishes
- **THEN** its telemetry record holds the model and effort it used
