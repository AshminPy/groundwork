# Proposal: Groundwork 3 — on-demand agent control plane

## Why

Groundwork 2.5 is slow and interrupts work:
- It loads about 50KB of rules every turn.
- It stops for approvals.
- It repeats reviews.
- Its noise audit found that task intake, the task ledger, reply checks and copilot add cost without proven value.

Context is also lost between subagents, sessions and compactions, and decisions can't be traced back to evidence.

Groundwork 3 rebuilds it as a thin control plane over Claude Code, OpenSpec, ECC, TDD and EGM. On-demand agents do the work, and deterministic hooks and scripts check it.

This change is planning only. It was revised after an EGM review (`egm-review.md`). Implementation starts only after the owner approves it. The Phase 0 platform checks can run alongside approval, with owner approval for live sessions.

## What Changes

- **Packaging:** one Claude Code plugin, `groundwork`, plus a work profile and a personal profile. The profiles hold settings a plugin can't ship. They are applied only after the owner approves a diff, and they can be reverted. For 3.x this replaces `install.sh` copy-and-merge.
- **Tier routing:**
  - Each request gets a tier from T0 (answer) to T4 (production, destructive or incident).
  - Deterministic rules set a minimum tier, and a production context found at action time raises it.
  - Follow-up prompts join the active run.
  - T0 and T1 run in the main session. T1 uses no subagents; T0 may use the read-only explorer for large searches.
- **On-demand agents:** explorer, investigator, planner, qa, egm, final-reviewer, docs, builder-general and domain builders.
  - Each tier has a fixed roster and gates.
  - Agents don't start other agents.
  - Each loop runs at most 2 rounds.
  - The owner passes the T4 gate with `gw approve` or `gw reject`.
- **Domain packs:** builders are generated from `domains/<name>/domain.toml`. Wave 1 is Terraform (GCP, AWS, Spacelift) and Kubernetes (GKE, EKS, Helm), plus builder-general for anything else.
- **Run state in files:**
  - Each run's state is JSON in one run folder, shared across worktrees.
  - Only the `gw` script writes it, under a lock.
  - Each task has its own revision number.
  - The log is append-only and hash-chained.
  - Evidence carries hashes, so stale evidence is caught.
- **Context continuity:**
  - Agents start with a packet and end with a handoff.
  - A brief survives compaction.
  - A project memory file holds the owner's preferences.
  - Runs can be resumed in a new session.
  - A run can move to another machine as an allow-listed export, which is refused if it holds anything that looks like a secret.
- **Decision records:**
  - Only a closed list of material decision kinds is recorded, in a short form.
  - Routing and approvals are recorded automatically.
  - Commits carry a `Task:` trailer.
  - `gw why` traces any file, task, decision or run back to its evidence.
- **Safety without prompts:**
  - auto mode, the sandbox and deny rules;
  - guard hooks that block when they fail;
  - per-agent write scope, checked both before and after;
  - no hook ever asks.
  
  The only prompt inside the workflow is the T4 gate. One-time setup actions and paid runs need explicit owner approval.
- **Toolchain integration:**
  - OpenSpec is the plan format.
  - Every ECC component has a recorded role (reuse, wrap or disable), and none may prompt.
  - TDD means red evidence before building and green evidence before done.
  - EGM reviewers work in a fresh context.
- **Console mod:** a status band, a run board and alerts. It also corrects agent models and can route the main session's model at stage boundaries, off by default. It enforces nothing.
- **MCP:** no servers by default. An approved catalog per profile, `/groundwork:mcp`, per-agent limits, and credentials never written to files.
- **Telemetry and eval dashboard:** local, privacy-safe records, and a self-contained HTML dashboard showing accuracy, safety, speed and cost against the 2.5.0 baseline.
- **Release gating:**
  - semver releases;
  - component versions recorded;
  - `gw doctor` checks for drift;
  - a release gate with eval and canaries;
  - rollback;
  - a learning loop that only proposes changes.
- **An early alpha** (T0/T1, guards, run state, brief) reaches the owner before the multi-agent tiers.
- **Not in scope:** removing 2.x components or specs. That is a separate cutover change, after 3.x meets or beats the 2.5.0 baseline.

## Capabilities

### New Capabilities

- `agent-orchestration`: tiers, rosters, gates, task binding, loops, tier-up and owner approval.
- `run-state`: the run folder, data formats, the `gw` script, locking, revisions, evidence and the log.
- `context-continuity`: packets, handoffs, stop-loop limits, compaction, the memory file, resume and export.
- `decision-records`: material kinds, the schema, tracing, contradictions and promotion.
- `safety-guards`: deny-only hooks, coverage, action-time tier-up, scope, fail-closed behaviour, approvals and the profile.
- `domain-packs`: packs, the general builder, generation, routing and checks.
- `model-routing`: declared models, bounded raises, downgrade gating and stage-boundary routing.
- `console-mod`: the band, the pane, alerts and the status-line fallback.
- `mcp-management`: the catalog, status, credentials and per-agent limits.
- `release-gating`: versions, the gate, paid-run approval, rollback, doctor, learning and baseline-first.
- `telemetry`: what each run and agent records, privacy and fail-open behaviour.
- `eval-dashboard`: a local page that shows each figure's source.
- `toolchain-integration`: OpenSpec, ECC, TDD and EGM roles.

### Modified Capabilities

None. The 2.x specs (including `health-dashboard`, `usage-telemetry` and `task-routing`) stay unchanged until the cutover change decides what to retire.

## Impact

- **Code:** a new plugin tree, with agents, skills, domains, hooks with their scripts and a mod, `scripts/gw`, profiles, an MCP catalog, templates, evals and an ECC inventory. The 2.x code stays in place, and named parts of it are ported (see design "Reuse").
- **Dependencies:**
  - Python 3.11 standard library only.
  - TypeScript for the mod.
  - A pinned OpenSpec CLI.
  - Claude Code 2.1.295 or later, for `onFailure`.
  - tflint, kubeconform and ansible-lint are optional, and each needs owner approval.
- **Systems:** it writes only to:
  - the plugin data folder;
  - the project's `.groundwork/`;
  - the approved profile target;
  - the configured work vault.
- **Evaluation:** gw-bench (#78) provides the baseline and the release gate.
- **Risks:** see the design. The main ones:
  - Bash writes outside an agent's scope are caught after the fact, not prevented.
  - It is unknown whether mods run in cloud sessions and with `-p`.
  - The extra agents cost tokens.
