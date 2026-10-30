# Proposal: Groundwork 3 — on-demand agent control plane

## Why

Groundwork 2.5 is slow and interrupts progress. It loads about 50KB of rules every turn, stops for approvals, and repeats reviews. Its noise audit found task intake, the task ledger, reply checks and copilot add cost without proven value. Context also gets lost between subagents, sessions and compactions, and decisions are not traceable to evidence. Groundwork 3 rebuilds it as a thin control plane over Claude Code, OpenSpec, ECC, TDD and EGM. Small on-demand agents do the work; deterministic hooks and scripts check it.

This change is planning only. It adds no code. Implementation starts only after the owner approves this plan and the focused 2.5.0 pilot has produced a baseline (#78, task 7.5).

## What Changes

- **New packaging:** Groundwork ships as one Claude Code plugin named `groundwork`. Settings a plugin cannot ship (permissions, sandbox, default model, environment, status line) move to a separate settings profile. The profile is applied only after the owner approves the diff, with work and personal profiles kept apart. This replaces the copy-and-merge `install.sh` for 3.x.
- **Routing by tier:** the main session sorts each request into one of five tiers, T0 (answer) to T4 (production, destructive or incident). Fixed rules run first and T4 always wins. The tier and the rule that matched are recorded.
- **On-demand agents:** explorer, investigator, planner, qa, egm, final-reviewer, docs, plus domain builders. Each has one job, a fixed model and effort, a limited tool list, and a stop check. Agents do not start other agents.
- **Domain packs:** builders are generated from `domains/<name>/domain.yaml`. Wave 1 is Terraform (with GCP, AWS and Spacelift skills) and Kubernetes (with GKE, EKS and Helm skills). Ansible and Elastic come later. A new domain needs one folder and its eval cases, and no change to router code.
- **Run state in files:** each request gets a run folder with `run.yaml`, `tasks.yaml`, `decisions.jsonl`, `handoffs/`, `evidence/` and `review.md`. Only the `gw` script changes run state. Evidence carries hashes, and every write checks the run revision.
- **Context continuity:** agents start with a context packet built from files and return a structured handoff. A brief survives compaction. Runs can resume in a new session, or move between machines through an exported bundle with secrets redacted.
- **Decision records:** every material decision records its question, options, choice, reason, evidence, assumptions, confidence and approver. `gw why` traces a file, task or decision back to its evidence.
- **Safety without prompts:** auto mode, the sandbox, deny rules, and `PreToolUse`/`SubagentStop`/`Stop` hooks that allow, deny or add context. No hook asks the user. The only human gate is T4 approval.
- **Console mod:** a status band and a run-board pane, plus model and effort routing for each request (`turn.step`) and a model check when an agent starts (`agent.spawn`). The mod only displays and routes. All safety stays in settings hooks.
- **MCP management:** no servers are on by default. An owner-approved catalog lists the allowed servers, and `/groundwork:mcp` manages them. Tokens come only from secure `userConfig` storage or the environment.
- **Release gating:** semver plugin versions with component versions in `metadata`. A release needs validation, tests and safety canaries to pass, an eval no worse than the last release, and owner approval.
- **Not in scope:** removing 2.x components and specs. That is a separate cutover change, made after the Groundwork 3 eval beats or matches the 2.5.0 baseline.

## Capabilities

### New Capabilities

- `agent-orchestration`: tier routing, the agent roster, stage gates, review loops and escalation.
- `run-state`: the run folder, the `gw` state script, task ownership, revisions and evidence integrity.
- `context-continuity`: agent context packets, handoffs, compaction recovery and moving context between sessions and machines.
- `decision-records`: the decision schema, how decisions are written, tracing back and promotion into durable docs.
- `safety-guards`: deny-only guard hooks, per-agent write scope, the settings profile and the T4 approval gate.
- `domain-packs`: the domain registry, builder generation, domain skills and adding domains.
- `model-routing`: model and effort choice for each stage and agent, and fallbacks when the mod is not loaded.
- `console-mod`: the status band, the run-board pane, alerts and the shared session index.
- `mcp-management`: the approved MCP catalog, server control and handling of credentials.
- `release-gating`: versioning, the eval gate, rollback and the gated learning loop.

### Modified Capabilities

None. The 2.x specs stay unchanged until the cutover change.

## Impact

- **Code:** a new plugin tree with agents, skills, domains, hooks with scripts and a mod, `scripts/gw`, a profile, an MCP catalog, templates and evals. The 2.x code is left alone.
- **Dependencies:**
  - Python standard library only, for hooks and `gw`.
  - TypeScript for the mod.
  - OpenSpec CLI: already used, and to be pinned.
  - tflint, kubeconform and ansible-lint are optional, and each needs owner approval before it is installed.
- **Systems:** writes only to the plugin's data, the project's `.groundwork/` and the approved profile target. The Obsidian work vault is written only at the configured path.
- **Evaluation:** gw-bench (#78) is the baseline and the release gate.
- **Risks:**
  - Some platform behaviours are still unverified: whether mods run in cloud sessions and in `-p` runs, whether hidden skills can be preloaded, whether plugin agents honour their own `hooks`/`mcpServers` frontmatter, the exact profile setting keys, and what `agent_type` holds for plugin agents. Phase 0 spikes verify each one before it is relied on.
  - Plugin evals and monitors are experimental.
