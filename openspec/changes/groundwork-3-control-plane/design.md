# Design: Groundwork 3 — on-demand agent control plane

## Context

Groundwork 2.5 installs by copying files and merging settings into `~/.claude`. It loads about 50KB of rules every turn and asks for approval often. The 2.5 noise audit recommended removing:

- task intake and MATERIAL tasks;
- the task ledger;
- reply-check enforcement;
- copilot;
- the legacy migration script;
- repeated rule text.

The owner wants Groundwork 3 to:

- give accurate, evidence-backed results where every decision can be explained;
- finish work faster;
- show a clear console;
- make MCP easy to manage;
- pick the model and effort for each request;
- keep context across agents and sessions;
- keep memory through compaction;
- measure results with an eval dashboard;
- learn, but only with gates.

It must sit over Claude Code, OpenSpec, ECC, TDD and EGM without copying them.

Three owner-reviewed design pages hold the full detail behind this document:

- Agent tree: https://claude.ai/artifact/LFpxr9KNXq7UhF58Rk7pjN
- Blueprint: https://claude.ai/artifact/XpsvbnAmrNRXdbPbUSnFsw
- Context plan: https://claude.ai/artifact/FNw8y6XmGbwk8nXRzcoiis

Owner decisions already made:

- Explorer and Investigator are added.
- Each review loop is limited to 2 rounds.
- Wave 1 is Terraform and Kubernetes.
- Docs go to a dedicated work Obsidian vault.

Platform facts below were checked on 2026-10-30 against the code.claude.com pages for the plugins reference, sub-agents, skills, hooks and mods reference.

## Goals / Non-Goals

**Goals**

- Each request runs only the agents its tier needs.
- Run state, decisions and handoffs live in files, so nothing is lost between agents, compactions or sessions.
- Every block is deterministic and lives in a settings hook. No approval prompts except the T4 owner gate.
- Domains are added as data, not code.
- Every release is measured against the eval and can be rolled back.

**Non-Goals**

- Removing 2.x code or specs. That is a separate cutover change.
- Agent teams. They are experimental and not available in `-p`.
- Self-modifying behaviour at run time.
- Any new paid service.
- Hosting state anywhere other than the owner's machine or repository.

## Decisions

### D1. Ship as one plugin plus a settings profile

- **Choice:** one plugin `groundwork`, plus `profile/work.json` and `profile/personal.json`, applied with `gw profile apply`.
- **Why:**
  - Plugin `settings` honour only `agent` and `subagentStatusLine` (plugins reference). Permissions, the sandbox, auto mode, the default model, environment variables and the main status line can't come from a plugin.
  - A `CLAUDE.md` at the plugin root is not loaded as context (plugins reference).
- **Alternative rejected:** keep `install.sh` copy-and-merge. It caused the 2.x `~/.claude` hook-path and rc-file problems.

### D2. Safety in settings hooks; display and routing in the mod

- **Choice:** every deny and block lives in `hooks/hooks.json` command hooks. The mod only draws the interface and picks models.
- **Why:** settings hooks run on every surface. The mods reference lists terminal, Desktop and VS Code, and says nothing about cloud sessions or `-p`. A mod failure must not weaken safety.

### D3. No hook asks the user

- **Choice:** guards return allow, deny with a reason, or context.
- **Why:** a hook "ask" forces a prompt even in auto mode, and approval stops were the owner's main complaint about 2.5. The T4 owner gate is a stage in the workflow, not a permission prompt.

### D4. Flat agents, with the main session as orchestrator

- **Choice:** set `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, which the sub-agents doc says turns nesting off, and give no agent the `Agent` tool.
- **Why:** a single orchestrator is visible to the owner and to the hooks. Nesting hides detail. TaskBuilder is merged into Planner, because OpenSpec already writes `tasks.md`.

### D5. Per-agent write scope from hook input

- **Choice:** `pre-guard` reads `agent_type` and the task's owned paths.
- **Why:** the hooks reference says tool events from a subagent carry `agent_id` and `agent_type`.
- **Open:** confirm the exact `agent_type` value for a plugin agent, such as `groundwork:builder-terraform` (Phase 0).

### D6. Files are the record; one script writes state

- **Choice:** the run folder plus the `gw` script (Python standard library) with revision checks and evidence hashes.
- **Why:** each subagent starts with a fresh context and returns only a summary (sub-agents doc). Native tasks don't hold shared run state across agents, and model-written YAML drifts.

### D7. Model routing in two layers

- **Agent level:** each agent's frontmatter sets `model` and `effort` (sub-agents doc). The mod's `agent.spawn` can enforce the model.
- **Main session:** the mod's `turn.step` sets the model and effort for each request (mods reference).
- **Fallback:** the profile's default model.
- **Correction:** an earlier claim in this conversation, that no mechanism could change the main model for each request, was wrong. Settings hooks can't; mods can.
- **Risk:** switching models within a session may reduce prompt-cache reuse. The eval measures cost before routing is turned on.

### D8. Domain packs generate builders

- **Choice:** `domains/<name>/domain.yaml` → `gw domain build` → `agents/builder-<name>.md`.
- **Why:** agent files must be `.md` files (plugins reference), and generating them keeps every builder on one template.
- **Domain skills:** limited with `paths`. Whether a hidden skill (`disable-model-invocation: true`) can still be preloaded through an agent's `skills:` list is checked in Phase 0.

### D9. Skills are versioned through the plugin

- **Choice:** the plugin `version` follows semver. Each component records its own version in `metadata` (for example `gw-version`, `eval-set`).
- **Why:** the skills doc lists no `version` field; `metadata` is free-form and not acted on. The plugin `version` pins users to a release (plugins reference).

### D10. MCP is least-privilege and catalogue-driven

- **Choice:**
  - no servers ship enabled;
  - `mcp/catalog.yaml` lists approved servers for each profile;
  - credentials come from `userConfig` marked `sensitive`, which the plugins reference says goes to secure storage, or from the environment.

### D11. No `bin/` folder

- **Choice:** skills call `${CLAUDE_PLUGIN_ROOT}/scripts/gw`.
- **Why:** the plugins reference says claude.ai and Cowork don't install a plugin that has `bin/`.

### D12. The learning loop proposes only

- **Choice:** `/groundwork:learn` writes a candidate OpenSpec change. It ships only through the release gate.
- **Why:** owner constraints: no unapproved changes to installed Groundwork, and gated self-improvement.

## Component catalog

### Agents

| Agent | Model · effort | Tools | Writes |
|---|---|---|---|
| explorer | haiku · low | Read, Grep, Glob, Bash | nothing |
| investigator | sonnet · high | Read, Grep, Glob, Bash | `evidence/` |
| planner | opus · high | Read, Grep, Glob, Write, Edit, Bash | `openspec/changes/` |
| qa | sonnet · high | Read, Grep, Glob, Write, Edit, Bash | `tests/` |
| egm | opus · high | Read, Grep, Glob, Write | `verdict.md` |
| builder-terraform | sonnet · medium | Read, Grep, Glob, Write, Edit, Bash | owned task paths |
| builder-kubernetes | sonnet · medium | Read, Grep, Glob, Write, Edit, Bash | owned task paths |
| final-reviewer | opus · high | Read, Grep, Glob, Bash, Write | `review.md` |
| docs | sonnet · medium | Read, Write | vault path |

Models and effort are starting values; the eval tunes them.

### Skills

- **Commands:** run, status, handoff, mcp, profile, eval, learn, domain.
- **Internal** (`user-invocable: false`): route, evidence, planning, test-design, review-rubric, git-flow, docs-template.
- **Domain:** tf-core, gcp, aws, spacelift; k8s-core, gke, eks, helm.

### Hooks

All are command hooks written in Python (standard library).

| Hook | Event | Purpose |
|---|---|---|
| session-start | SessionStart (startup, resume, compact, clear) | Restore the brief and run status. Install nothing |
| prompt-route | UserPromptSubmit | Apply the deterministic tier rules and record the decision |
| pre-guard | PreToolUse (Bash, Edit, Write, NotebookEdit) | Hard denies and per-agent scope. Fails closed |
| pre-dispatch | PreToolUse (Agent) | Stage gates |
| post-record | PostToolUse | Telemetry, evidence capture and hashes |
| post-failure | PostToolUseFailure | Failure patterns |
| denied-log | PermissionDenied | Record auto-mode denials separately |
| agent-start | SubagentStart | Build the context packet |
| agent-stop | SubagentStop | Stop check and handoff check. Blocks |
| stop-verify | Stop | No "done" while tasks are open without evidence |
| pre-compact | PreCompact | Write the brief. Never blocks |
| session-end | SessionEnd | Close telemetry and list memory candidates |

Not used on purpose:

- PermissionRequest, Notification, InstructionsLoaded, ConfigChange, FileChanged;
- the Worktree hooks;
- PreModelSwitch and PostModelSwitch;
- Elicitation;
- TaskCreated and TaskCompleted;
- TeammateIdle.

### Mod

| Mods API | Use |
|---|---|
| `turn.step` | Model and effort for each request |
| `agent.spawn` | Enforce the agent's model |
| `ui.render` at `AbovePrompt` | Status band |
| `ui.render` at `Pane` | Run board |
| `$.ui.toast` | Alerts |
| `$.command.register` | Board and band commands |
| `$.session.usage()` | Context use and cost |
| `$.store` | Shared run index on this machine, 4 MiB limit |

### `gw` script

- `run new | status | report`
- `task claim | done | block | list`
- `decide`, `why`
- `handoff write | export | load`
- `brief`
- `profile diff | apply | revert`
- `mcp list | check | enable | disable`
- `domain new | build`
- `eval run | compare`
- `learn propose`

## Risks / Trade-offs

- **Mods may not run in cloud sessions or `-p`.** Mitigated by D2: everything degrades to the hooks plus the status line.
- **Prompt-cache cost from switching models.** Measured before routing is enabled. Off by default until it is proven.
- **More agents mean more tokens and more handoffs.** The tiers keep simple tasks small, and files carry the context.
- **Enabled skill descriptions cost context every turn.** Keep descriptions to one line, use `paths` limits, and prefer preloading into agents.
- **Plugin evals and monitors are experimental.** gw-bench stays the authoritative eval.
- **Hidden-skill preloading, plugin-agent `hooks` and `mcpServers`, and the exact profile keys are unverified.** Phase 0 spikes check each one. The design falls back to central hooks and visible, path-limited skills.
- **Two harnesses during the transition.** 3.x runs in a separate profile or config directory until cutover, so 2.5 stays untouched.

## Migration Plan

1. **Baseline.** Run the 2.5.0 focused pilot from #78, once the owner approves.
2. **Phase 0 spikes.** Verify each unverified platform behaviour.
3. **Build in phases** (see tasks), each measured against the baseline.
4. **Cutover change.** Retire the 2.x components and specs only after a 3.x release meets or beats the baseline.
5. **Rollback.** Disable the plugin and revert the profile; 2.5 stays installed until the cutover.

## Open Questions

- Should model routing for each request be on by default after the cache-cost eval, or stay opt-in?
- What is the exact Obsidian work vault path? It is set at install through `userConfig`.
- Which MCP servers go in the first work catalog?
- When should the Ansible and Elastic packs start, after wave 1's eval?
