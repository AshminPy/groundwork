# Spec Delta

## ADDED Requirements

### Requirement: Task-relevant integration hints at intake
When Groundwork records a new MATERIAL task whose intake signals name a catalog integration (for example GCP, AWS, Kubernetes, Terraform, GitHub or Jira), the context it adds SHALL name each such integration with:
- its display summary state;
- the age of that state.

Both SHALL be read only from the existing Integration Catalog readiness cache. When the cache is missing or has no entry for an integration, the hint SHALL say that readiness is unknown and name `groundwork integrations list` as the way to check. The hint SHALL be guidance only. Producing it SHALL NOT run a probe or install, configure or activate anything. It SHALL NOT claim that the integration will be used.

#### Scenario: A GCP task with a cached readiness
- **WHEN** `COR-123: Deploy GoldenGate VM in GCP` is recorded and the cache holds GCP as CONFIGURED, checked two hours ago
- **THEN** the added context names GCP as CONFIGURED, checked about two hours ago, as guidance

#### Scenario: No cache yet
- **WHEN** the same task is recorded and no readiness cache exists
- **THEN** the added context says GCP readiness is unknown and names `groundwork integrations list`

#### Scenario: No probe at intake
- **WHEN** any MATERIAL task is recorded
- **THEN** no `claude`, `gh`, cloud or other integration CLI subprocess runs as part of intake
