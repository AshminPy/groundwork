# Spec Delta

## Purpose

Defines expert builders for each toolchain from a small domain pack, with a general builder for everything else, so new domains can be added without changing the router or other agents.

## ADDED Requirements

### Requirement: A domain is defined by one folder
Each domain SHALL be one folder `domains/<name>/` holding a `domain.toml`, the domain skills and the eval cases. `domain.toml` SHALL declare the file patterns, the skills to preload, the checks to run, the model and effort, the component version, and any approved tools it needs.

#### Scenario: Incomplete pack
- **WHEN** a domain folder lacks eval cases
- **THEN** the domain is not built, and the error names the missing part

### Requirement: Builders come from one template
`gw domain build` SHALL generate each builder agent file from its `domain.toml` and one shared template. Running it twice with no changes SHALL produce identical files.

#### Scenario: Regenerate after a change
- **WHEN** one domain's model changes and `gw domain build` runs
- **THEN** only that builder's agent file changes

### Requirement: Domain skills preload into their builder
Domain skills SHALL be preloaded into their builder and SHALL be marked `user-invocable: false`. They SHALL NOT set `disable-model-invocation: true`, because skills that set it can't be preloaded.

#### Scenario: Skill flags
- **WHEN** the release check reads a domain skill's frontmatter
- **THEN** it has `user-invocable: false` and not `disable-model-invocation: true`

### Requirement: Tasks route to the matching builder or the general builder
A task SHALL go to the builder whose file patterns match its owned paths. A task matching no installed domain SHALL go to `builder-general`. A task matching a domain that isn't installed SHALL be blocked with a reason.

#### Scenario: Python fix
- **WHEN** a T2 task owns only `scripts/*.py`
- **THEN** it goes to builder-general

#### Scenario: Pack not installed
- **WHEN** a task's paths match the planned elastic patterns and the elastic pack isn't installed
- **THEN** the task is blocked with the reason "no elastic builder installed"

### Requirement: The first wave is Terraform and Kubernetes
The first release SHALL include `builder-general`, `terraform` with GCP, AWS and Spacelift skills, and `kubernetes` with GKE, EKS and Helm skills. Ansible and Elastic SHALL be added only after wave 1 passes its eval.

#### Scenario: Wave 1 contents
- **WHEN** the first release's builders are listed
- **THEN** they are exactly builder-general, builder-terraform and builder-kubernetes

### Requirement: Builders run their domain checks before done
A builder SHALL run the checks its pack declares, and save their output as evidence, before its task can be marked done. For Terraform these SHALL include `terraform fmt -check` and `terraform validate`. builder-general SHALL run the project's test command.

#### Scenario: Validate fails
- **WHEN** `terraform validate` fails on a builder's change
- **THEN** the task is not done, and the failure output is saved as evidence

### Requirement: Third-party check tools need approval
A check that needs a tool outside the base system, such as tflint, kubeconform or ansible-lint, SHALL be skipped and reported until the owner approves that tool.

#### Scenario: Unapproved linter
- **WHEN** the kubernetes pack declares kubeconform and it isn't approved
- **THEN** the check is reported as "skipped: needs approval", and nothing is installed

### Requirement: Adding a domain needs no router change
Adding a domain SHALL need only a new domain folder and a rebuild. No change to the router, the hooks or other agents SHALL be required.

#### Scenario: Add a test domain
- **WHEN** a dummy domain folder is added and built in a test
- **THEN** its tasks route to the new builder, and no other tracked file changes
