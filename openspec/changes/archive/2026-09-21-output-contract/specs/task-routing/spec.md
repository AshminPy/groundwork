## MODIFIED Requirements

### Requirement: Playbook structure and output contract
Every playbook SHALL contain the sections Goal, Workflow, Evidence, Ask Before Acting When, Completion Criteria, Output Format, and SHALL stay small; every response SHALL follow the global three-layer output contract in `rules/output-contract.md` — a plain-language main response first, `Technical details` only when useful technical evidence exists, `Evidence & references` only when the conclusion depends on sources — omitting empty sections, translating evidence into understandable language, never implying verification that did not happen, and never printing routing debug lines unless asked.

#### Scenario: Structural check
- **WHEN** the test suite runs
- **THEN** each of the ten playbooks exists, has the six sections, is within the size cap, names its main-response headings, and inherits the layers by reference rather than restating them; `rules/output-contract.md` exists, is within its size cap, and contains the three layers and the omit-empty, honest-validation and no-debug-lines rules

#### Scenario: Representative outputs
- **WHEN** fresh sessions answer representative IMPLEMENT, TROUBLESHOOT, AUDIT, VALIDATE, RESEARCH and EXPLAIN prompts
- **THEN** each answer leads with the result, uses the category's main headings, prints no `Routing:`/`Playbook:` lines and no empty "none" sections, and places commands, errors and traceability under `Technical details` rather than in the main text
