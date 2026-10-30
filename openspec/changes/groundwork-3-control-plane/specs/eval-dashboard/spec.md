# Spec Delta

## Purpose

Shows the owner, on one local page, whether Groundwork is working: accuracy, safety, speed and cost by tier, agent, model and version, from telemetry and eval results.

## ADDED Requirements

### Requirement: A local dashboard built from files
`gw dashboard` SHALL build a self-contained local HTML page from the telemetry records and the gw-bench results. It SHALL make no network requests and need no server.

#### Scenario: Offline build
- **WHEN** `gw dashboard` runs with the network disabled
- **THEN** the page is built and opens from a local file

### Requirement: The dashboard shows the measures that decide releases
The page SHALL show pass rate with confidence intervals, safety canary results, denials by kind, loop rounds, time to done, and cost. These SHALL be broken down by tier, agent, model and version, with the 2.5.0 baseline shown for comparison.

#### Scenario: Version comparison
- **WHEN** results exist for 3.0.0 and 3.1.0
- **THEN** the page shows both side by side, with the baseline line

### Requirement: Every number shows its source
Each figure on the page SHALL name the files and the number of records it was computed from. Figures with fewer records than the pre-registered minimum SHALL be marked as not enough data.

#### Scenario: Too few runs
- **WHEN** a model has 3 records and the minimum is 10
- **THEN** its figures are marked "not enough data"

### Requirement: The page holds no sensitive content
The dashboard SHALL show only telemetry and eval fields, never prompt text, command text, file contents or credentials.

#### Scenario: Content scan
- **WHEN** the built page is scanned for the eval cases' secret canaries
- **THEN** none is found
