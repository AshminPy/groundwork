# Task routing and output contract (Groundwork — applies to every substantive request)

A small router. Detailed workflows live in `~/.claude/groundwork/playbooks/` and are read only when selected. This layer is additive: it never overrides `engineering-workflow.md`, `evidence-policy.md`, `architecture-quality.md`, the security rules, or any hook. If a playbook and one of those disagree, the existing rule wins.

## 1. Route
1. Determine the user's primary goal.
2. If material ambiguity exists (§2), ask the minimum clarification before acting; otherwise continue.
3. Select ONE primary category from §3 and read only that playbook: `~/.claude/groundwork/playbooks/<category>.md`. Do not read the others.
4. Follow its workflow, evidence requirements, completion criteria and output format.
5. If the task materially changes mid-way (a TROUBLESHOOT becomes an IMPLEMENT, a RESEARCH becomes a DESIGN), reclassify and read the new playbook.
6. Engineering categories (DESIGN, PLAN, IMPLEMENT, TROUBLESHOOT, VALIDATE, AUDIT, DEPLOY) still run inside `engineering-workflow.md`: tier classification, OpenSpec for MATERIAL work, independent review, the completion block. A TRIVIAL request (one-line answer, typo, single config value) needs no playbook.

## 2. Ask only when it matters
Same threshold as `engineering-workflow.md` §4, applied to every category. Ask before acting only when missing information could materially change correctness, architecture, implementation, safety, permissions, the target environment, a destructive action, or the requested outcome — and it cannot be determined safely from the repository, configuration, documentation, logs, tests, runtime or environment inspection. Otherwise infer from evidence, take the safest reasonable assumption, state it only if it materially matters, and continue. When you do ask: one question, naming the decision. ("Delete the environment" with several environments present → ask which. "Explain Terraform state" → answer.)

## 3. Categories (exactly one per task)
| Category | Route here when the goal is… |
|---|---|
| RESEARCH | investigate, gather evidence, find authoritative or current information, compare researched technologies |
| EXPLAIN | explain or teach something, answer a technical question ("high level" / "low level" are depth modifiers, not categories) |
| DESIGN | architecture, system or workflow design, compare architectural approaches, a technical recommendation |
| PLAN | an implementation, migration, rollout, remediation or execution plan |
| IMPLEMENT | write or change code, Terraform, Ansible, configuration, scripts, automation, repository content |
| TROUBLESHOOT | debug an error, incident, RCA, broken deployment, unexpected behaviour |
| VALIDATE | test, verify, prove correctness, acceptance or regression testing, confirm something works |
| AUDIT | review code, security, IAM, architecture, configuration or readiness against a requirement |
| DEPLOY | deploy, upgrade, migrate, roll back, or make an operational change to cloud, Kubernetes, Docker or local systems |
| DOCUMENT | README, runbook, report, summary, implementation or incident documentation, executive summary |

COMPARE → DESIGN (approaches) or RESEARCH (technologies); AUTOMATE → IMPLEMENT; REPORT findings → DOCUMENT; VERIFY → VALIDATE; DECIDE → DESIGN. Do not invent new categories.

## 4. Universal output contract
Every response follows `output-contract.md`: a plain-language main response (result first, only material findings, validation stated honestly, one next action when needed), then `Technical details` when useful evidence exists, then `Evidence & references` when the conclusion depends on sources. The playbook names the main-response headings for its category; the contract supplies the other two layers and the rules (omit empty sections, no narration, conciseness never hides risk or failed validation).
