# Spec Delta

## Purpose

Defines expert builders for each toolchain from a small domain pack, so new domains can be added without changing the router or the other agents.

## ADDED Requirements

### Requirement: A domain is defined by one folder
Each domain SHALL be one folder `domains/<name>/` with a `domain.yaml`, domain skills and eval cases. `domain.yaml` SHALL declare the file patterns it handles, the skills to preload, the deterministic checks to run, the model and effort, and any approved tools it needs.

#### Scenario: Pack is complete
- **WHEN** a domain folder lacks eval cases
- **THEN** the domain is not built and the error names the missing part

### Requirement: Builder agents are generated from the pack
`gw domain build` SHALL generate each builder agent file from its `domain.yaml`. Generated builders SHALL share one template. Hand edits to generated files SHALL be detected and refused at release.

#### Scenario: Regenerate after a change
- **WHEN** a domain's model changes in `domain.yaml` and `gw domain build` runs
- **THEN** only that builder's agent file changes

### Requirement: Routing to a builder uses the file patterns
The main session SHALL assign a task to the builder whose file patterns match the task's owned paths. A task matching no domain SHALL be blocked with a reason, not given to the wrong builder.

#### Scenario: Elastic task before the elastic pack exists
- **WHEN** a task's paths match no installed domain
- **THEN** the task is blocked with the reason "no builder for these paths"

### Requirement: The first wave is Terraform and Kubernetes
The first release SHALL include `terraform`, with GCP, AWS and Spacelift skills, and `kubernetes`, with GKE, EKS and Helm skills. Ansible and Elastic SHALL be added only after wave 1 passes its eval.

#### Scenario: Wave 1 contents
- **WHEN** the first release is listed
- **THEN** it contains exactly the terraform and kubernetes builders

### Requirement: Builders run their domain checks before done
Each builder SHALL run the checks its `domain.yaml` declares, and save their output as evidence, before reporting a task done. For Terraform these SHALL include `terraform fmt -check` and `terraform validate`.

#### Scenario: Validate fails
- **WHEN** `terraform validate` fails on a builder's change
- **THEN** the task is not done and the failure output is saved as evidence

### Requirement: Third-party check tools need approval
A domain check that needs a tool outside the base system, such as tflint, kubeconform or ansible-lint, SHALL be skipped and reported until the owner approves that tool.

#### Scenario: Unapproved linter
- **WHEN** the kubernetes pack declares kubeconform and it is not approved
- **THEN** the check is reported as "skipped: needs approval" and nothing is installed

### Requirement: Adding a domain needs no router change
Adding a domain SHALL take only a new domain folder and a rebuild. No change to the router, the hooks or the other agents SHALL be required.

#### Scenario: Add ansible
- **WHEN** `domains/ansible/` is added and built
- **THEN** ansible tasks route to builder-ansible with no other file changed
