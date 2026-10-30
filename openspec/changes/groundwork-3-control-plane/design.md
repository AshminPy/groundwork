# Design: Groundwork 3 — on-demand agent control plane

Revised after the EGM review (`egm-review.md`). The review had three fresh-context reviewers (zoom-out, design critic, implementation readiness) and found 15 must-fix items, all resolved here.

## Context

Groundwork 2.5 installs by copying files and merging settings into `~/.claude`, loads about 50KB of rules every turn, and often asks for approval. Its noise audit recommended removing:

- task intake and MATERIAL tasks;
- the task ledger;
- reply-check enforcement;
- copilot;
- the legacy migration script;
- repeated rule text.

The owner wants Groundwork 3 to:

- give accurate, evidence-backed results where every decision can be explained;
- finish faster;
- show a clear console;
- make MCP easy to manage;
- pick the model and effort for the work;
- keep context across agents and sessions;
- keep memory through compaction;
- measure success with an eval dashboard;
- learn, but only through gates;

all while sitting over Claude Code, OpenSpec, ECC, TDD and EGM without duplicating them.

Owner decisions already made:

- Explorer and Investigator are added.
- Each review loop is limited to 2 rounds.
- Wave 1 builds Terraform and Kubernetes builders.
- Docs go to a dedicated work Obsidian vault.

Supplementary design pages (owner-reviewed; this document is complete without them): agent tree https://claude.ai/artifact/LFpxr9KNXq7UhF58Rk7pjN, blueprint https://claude.ai/artifact/XpsvbnAmrNRXdbPbUSnFsw, context plan https://claude.ai/artifact/FNw8y6XmGbwk8nXRzcoiis.

### Platform facts (code.claude.com, checked 2026-10-30; installed Claude Code 2.1.314)

| Fact | Source |
|---|---|
| Plugin `settings` honour only `agent` and `subagentStatusLine` | plugins reference |
| A plugin-root `CLAUDE.md` is not loaded as context | plugins reference |
| claude.ai and Cowork don't install a plugin that has `bin/` | plugins reference |
| `userConfig` with `sensitive` goes to secure storage | plugins reference |
| Plugin subagents ignore `hooks`, `mcpServers` and `permissionMode` frontmatter | sub-agents |
| An agent that omits `tools` "inherits every tool available to subagents" | sub-agents |
| Skills with `disable-model-invocation: true` can't be preloaded | sub-agents |
| `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` turns nesting off (default 3) | sub-agents |
| Each subagent starts with a fresh context and returns only a summary | sub-agents |
| Tool events from a subagent carry `agent_id` and `agent_type` | hooks |
| Plugin agents match as plugin-scoped names, e.g. `^my-plugin:reviewer$` | hooks (matcher table) |
| A failing, timed-out or invalid hook lets the action go ahead unless `"onFailure": "block"` is set (v2.1.295+); this has no effect on `Stop` or `SubagentStop` | hooks |
| A hook "ask" still prompts in auto mode | hooks / auto mode |
| SubagentStart can't block; PreToolUse on `Agent` can | hooks |
| Skills have no `version` field; `metadata` is free-form | skills |
| Agents have no `metadata` field | sub-agents field list |
| Mods: `turn.step` and `agent.spawn` can set the model; `$.store` is shared per machine, 4 MiB | mods reference |
| `agent.spawn` doesn't run when a subagent is resumed through `SendMessage` | mods reference |
| The `AbovePrompt` band renders in Terminal and Desktop, not VS Code | mods reference |
| A model switch causes an uncached turn | docs index (llms.txt) |
| Python 3.11 standard library has `tomllib` (read only) and no YAML parser | Python docs |

Phase 0 results (tasks 1.1–1.8, 2026-10-30) are in `phase0-results.md`. They confirmed D5, D7 and D8 as designed, and changed D1, D2 and D16 as noted below. Only one item stays open: whether mods run in claude.ai cloud sessions.

Originally unverified and checked in Phase 0:

- Whether mods run in cloud sessions and in `-p`.
- Whether `agent_id` stays the same from SubagentStart through PreToolUse to SubagentStop.
- Whether SubagentStart can add context.
- How SubagentStop blocking behaves, including the documented continuation cap and `stop_hook_active`.
- Whether `claude plugin test` and `claude plugin validate --strict` behave as documented.
- The exact profile settings keys.
- The hook working directory and `CLAUDE_PROJECT_DIR` inside worktree subagents.
- Whether writes to a vault outside the working directory go through auto mode and the sandbox without a prompt.

## Goals / Non-Goals

**Goals**

- Each request runs only its tier's agents, and simple work stays fast.
- Run state, decisions and handoffs live in files.
- Every block is deterministic and lives in a settings hook. The only workflow prompt is the T4 owner gate.
- Domains are added as data.
- Every release is measured and reversible.

**Non-Goals**

- Removing 2.x code or specs. That is the cutover change.
- Agent teams.
- Self-modification at run time.
- New paid services.
- State outside the owner's machine and repository.
- Messages between live sessions. The review found it unneeded: state is shared through files.

## Decisions

### D1. One plugin plus a settings profile

- **Choice:** the `groundwork` plugin, plus `profile/work.json` and `profile/personal.json`, applied by `gw profile apply` with a diff, a backup and owner approval.
- **Why:** plugins can't ship permissions, the sandbox, the default model, env or the main status line.
- **Rejected:** `install.sh` copy-and-merge, which caused the 2.x hook-path and rc-file problems.
- **Phase 0 (1.5):** `permissions.defaultMode: "auto"` takes effect only from user or managed settings. So each profile is the user `settings.json` of its own `CLAUDE_CONFIG_DIR` (work and personal), which also keeps the two apart. The confirmed keys are in `phase0-results.md` §1.5.
- **Phase 0 (1.7):** the work profile sets `sandbox.filesystem.allowWrite` to the vault path. Pre-guard limits Write and Edit for docs to the vault, because the sandbox doesn't cover the Write tool.
- **Plugin location:** the plugin lives in `plugin/` at the repository root, so 2.x stays untouched until cutover.
- **Profile config directories:** `~/.claude-gw3-work` and `~/.claude-gw3-personal`, so the owner's `~/.claude` (with 2.5) is never changed.
- **Approval:** `gw profile apply` needs `apply` typed at an interactive terminal; it refuses when stdin is not a TTY, so Claude cannot apply it. `revert` restores the backup taken before the first apply, byte for byte.
- **Found in group 2:** `claude doctor` warns that on Linux, glob patterns in `Read(...)` deny rules are not enforced by the Bash sandbox. The Read tool still honours them, and pre-guard's secret-path checks (4.3) are the main control. The sandbox `denyRead` holds only the plain path `~/.ssh`.

### D2. Safety in settings hooks; display and routing in the mod

- **Choice:** every deny and block is a command hook in `hooks/hooks.json`. The mod only draws the console and corrects models.
- **Why:** the mods reference covers only Terminal, Desktop and VS Code, so a mod failure must not weaken safety.
- **Phase 0 (1.3):** mods run with `-p` and in the interactive terminal. claude.ai cloud sessions are not tested; the hooks and status-line fallback stays.

### D3. No hook asks

- **Choice:** hooks allow, deny, block or add context.
- **Why:** a hook "ask" prompts even in auto mode.
- **Approvals outside the workflow:** one-time setup approvals (profile apply, a catalog entry, a third-party tool, a paid eval) are explicit owner actions, not hook prompts.

### D4. Flat agents

- **Choice:** every agent declares `tools` without `Agent`, the profile sets `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, and the release check fails any agent file without `tools`.
- **Why:** an omitted `tools` inherits `Agent`.

### D5. Agent identity and task binding

- **Choice:**
  - For Groundwork task agents (`^groundwork:` except explorer), `pre-dispatch` requires the Agent call's prompt to start with `run: <run-id> task: <task-id>`.
  - Explorer and any non-Groundwork subagent (built-in, or an ECC component marked reuse) need no binding. They are read-only: `pre-guard` denies any write by an agent that has no binding.
  - `agent-start` records `agent_id → (run, task, owned paths)` in `bindings.json`.
  - `pre-guard` reads `agent_type` (plugin-scoped, e.g. `groundwork:builder-terraform`) and `agent_id` to find the binding.
  - Phase 0 checks that `agent_id` stays the same across events.
- **Phase 0 (1.1):** confirmed. `agent_id` is stable across events, `agent_type` is `groundwork:<agent>`, and pre-dispatch reads the target from `tool_input.subagent_type`. No fallback is needed.

### D6. Scope is checked before and after

- **Choice:**
  - `pre-guard` denies edits and writes outside the agent's owned paths (best effort for Bash).
  - `agent-start` records a snapshot of the working tree: `git status --porcelain=v2`, plus hashes of tracked and untracked, non-ignored files.
  - `agent-stop` diffs the tree against that snapshot, so files that were already dirty are not blamed on the agent. It blocks the task on any change outside the owned paths.
  - On success, `agent-stop` writes a scope-check record for the task revision. `gw task done` refuses without a passing record, so a crashed stop hook can't skip the check.
  - Builders that run in parallel SHALL use `isolation: worktree`; otherwise builds run one at a time.
- **Also:**
  - egm and docs have no Bash;
  - final-reviewer keeps Bash to re-run tests, and any file change it makes blocks the review.
- **Why:** permission rules and parsed commands can't see files a script writes; the post-check can.

### D7. Guards fail closed

- **Choice:** `pre-guard` and `pre-dispatch` set `"onFailure": "block"`. The minimum supported Claude Code version is 2.1.295.
- **Stop checks:** `Stop` and `SubagentStop`, where `onFailure` has no effect, get a file-kept block counter keyed by session id and agent id. After 2 blocks, the task is marked blocked and the stop is allowed. They also honour `stop_hook_active`.
- **Phase 0 (1.2):** Claude Code imposed no cap in 12 consecutive blocks, so the counter is required. A main-session `Stop` can fire while a subagent still runs in the background, so stop-verify allows the stop while any bound agent hasn't reached SubagentStop.

### D7a. Agents without Bash hand off through files

- **Choice:** every agent writes its handoff with the Write tool to `handoffs/<seq>-<agent>-<task>.md`. The Decisions section uses the short form (kind, question, choice, reason, evidence). `agent-stop` validates the file and records the decisions through `gw`. This is the only path for egm and docs, which have no Bash.

### D8. Files are the record; one script writes state

- **Choice:** JSON state with a lock and atomic replace (`fcntl.flock`, then a temp file and `os.replace`), per-task revisions, and a hash-chained append-only log. Each log entry stores the sha256 of `run.json` and `tasks.json` after its operation, and `gw` compares that hash on every read, so an outside edit to either file is detected.
- **Run root:** the folder that holds `git rev-parse --git-common-dir`, so worktrees share one run folder. TOML (read with `tomllib`) for owner-edited config.
- **Phase 0 (1.6):** worktrees live at `<repo>/.claude/worktrees/agent-<id>`, and `--git-common-dir` resolves to the main `.git`. Snapshot diffs exclude `.claude/worktrees/`. Builders run git commands one per call, because the worktree isolation check refused a chained git command.
- **Why:**
  - Subagents start fresh.
  - The standard library has no YAML parser.
  - Parallel builders need writes per task that don't block each other.

### D9. Tiers and the deterministic floor

- **Choice:**
  - `prompt-route` matches the tier rules in `rules/tiers.toml` and records the minimum tier.
  - `prompt-route` writes `sessions/<session-id>/floor.json`.
  - The main session opens the run with `gw run new --tier --reason`. That command takes the highest floor written for this project in the last 10 minutes and refuses anything below it. Taking the highest is safe because a floor only ever raises the tier.
  - The guard checks for a production context when an action runs (kube context, terraform workspace, production globs from `.groundwork/project.toml`) and raises the tier.
- **Why:** this reverses the 2.0 note that "heuristic production detection by name risks false confidence". It is acceptable because rules only raise the tier, the hard denies stay independent, and the action-time context check covers wording that the prompt rules miss.
- **Testing:** false negatives and negations ("production-ready", "never touch prod") are in the routing tests and the eval.

### D10. T0 and T1 run in the main session

- **T0:** answered by the main session, with explorer only for large searches (no run, no binding, read-only), and logged in `.groundwork/sessions/<session-id>/routing.jsonl`.
- **T1:** the main session edits under the guards with a light run: `run.json` plus evidence, with no claim and no handoff.
- **Why:** starting an agent for a typo is slower and adds nothing.

### D11. General builder plus domain packs

- **Choice:** `builder-general` (sonnet, medium) takes any task that matches no installed pack. `domains/<name>/domain.toml` plus one template generates the domain builders.
- **Domain skills:** they use `user-invocable: false`, because skills with `disable-model-invocation` can't be preloaded.

### D12. Model routing

- **Choice:**
  - Agents declare `model` and `effort`.
  - The planner can raise them for one task, as a recorded decision.
  - The mod's `agent.spawn` sets the model to the declared model, or to a per-task raise recorded by the planner when one exists. The mod's `tool.call` does the same when a subagent is resumed through `SendMessage`.
  - Main-session routing through `turn.step` is off by default, and when on it changes only at stage boundaries, because a switch causes an uncached turn.
  - It is turned on only if the eval shows no accuracy loss and lower cost.

### D13. Decisions: closed list, short form

- **Recorded kinds:** routing, tier change, verdict, approval, design choice, deviation, accepted risk.
- **Short form:** agents pass five fields (kind, question, choice, reason, evidence), and `gw` fills in the rest.
- **Automatic records:** hooks and `gw` record routing and approvals.
- **Trailers:** `pre-guard` denies `git commit` under an active run without a `Task:` trailer.

### D14. Versions

- **Choice:**
  - The plugin follows semver.
  - Skills carry `metadata.gw-version`.
  - Agents are listed in `components.json`, because they have no metadata field.
  - The release check refuses a changed component that has no version bump.

### D15. MCP

- **Choice:**
  - no servers by default;
  - `mcp/catalog.toml` for each profile;
  - per-agent server limits enforced by `pre-guard` on `mcp__.*`, because plugin agents ignore `mcpServers`;
  - credentials from sensitive `userConfig` or the environment.

### D16. Toolchain roles

- **OpenSpec:** the T3/T4 plan format, with the CLI version pinned.
- **ECC:** every component is inventoried in `plugin/toolchain/ecc-inventory.toml` (Phase 0, 1.8).
  - The ECC plugin is not enabled: it would list 68 agents, 286 skills and 94 commands every turn, and its GateGuard, plan-canvas and MCP health hooks conflict with Groundwork's.
  - Ten components are ported with attribution under ECC's MIT licence. The rest are disabled.
  - No ECC hook returns ask.
- **TDD:** qa's red evidence comes before build and green evidence before done.
- **EGM:** egm and final-reviewer are the fresh-context reviewers, with one shared rubric.

### D17. Early alpha before the full plan

- **Choice:** an alpha milestone after task groups 2 to 5 delivers T0/T1 routing, the guards in auto mode, run state, the brief and the main-session verify gate (stop-verify). The owner uses it daily, while the multi-agent tiers are built.
- **Why:** the owner's main complaints, slowness and prompts, are addressed first.

## Data formats

Every JSON state file has `"format": 1`. Ids:

- run: `r-YYYYMMDD-HHMMSS-<slug>`
- task: `T<n>`
- decision: `D-<nnn>`
- review item: `R-<n>`
- evidence: `E-<task>-<n>`

`run.json`

```json
{"format":1,"id":"r-20261102-141022-eks-private","tier":"T3","min_tier":"T3","stage":"build",
 "stages":["plan","test","review","build","final-review","docs"],"goal":"Private EKS with IRSA",
 "profile":"work","created":"2026-11-02T14:10:22Z","loop_rounds":{"egm":1,"final":0},"status":"active"}
```

`tasks.json`

Statuses: `open → claimed → done | blocked`. A blocked task can go back to `open`.

```json
{"format":1,"tasks":[{"id":"T4","title":"Helm values","rev":3,"status":"claimed",
 "owner":{"agent_type":"groundwork:builder-kubernetes","agent_id":"a-…"},
 "owned_paths":["charts/app/**"],"depends_on":["T3"],"criteria":["AC-4.1","AC-4.2"],
 "evidence":["E-T4-1"],"blocked_reason":null}]}
```

`evidence/E-T4-1.json`: `{"format":1,"id":"E-T4-1","task":"T4","kind":"test|lint|plan|dry-run|red","command":"helm lint charts/app","exit":0,"output":"E-T4-1.txt","covers":{"charts/app/values.yaml":"sha256:…"},"at":"…"}`

`decisions.jsonl`: one record per line, with the fields in the decision-records spec.

`log.jsonl`: `{"format":1,"seq":17,"at":"…","actor":"…","op":"task.done","target":"T4","state":"sha256:<run.json+tasks.json>","prev":"sha256:…","hash":"sha256:…"}`

`bindings.json`: `{"format":1,"agents":{"<agent_id>":{"agent_type":"groundwork:builder-kubernetes","run":"r-…","task":"T4","owned_paths":["charts/app/**"],"snapshot":"snapshots/<agent_id>.json","started":"…"}}}`

`scope/<task>-<rev>.json`: `{"format":1,"task":"T4","rev":3,"agent_id":"…","outside":[],"result":"pass|fail","at":"…"}`

`blocks.json` (stop-check counter): `{"format":1,"counts":{"<session_id>|<agent_id or main>":2}}`

`sessions/<session-id>/floor.json`: `{"format":1,"prompt_id":"…","at":"…","min_tier":"T4","rules":["prod-env"]}`. `sessions/<session-id>/routing.jsonl`: one line per prompt `{"at","prompt_id","min_tier","rules","tier","run"}`. T0 lines have `"run": null`.

`components.json` (plugin root): `{"format":1,"agents":{"planner":"1.0.0",…},"hooks":{"pre-guard":"1.0.0",…},"mod":"1.0.0"}`

`evals/criteria.toml`: the pre-registered pass criteria, the comparison rule (no worse than the previous lower 95% bound), and `min_records = 10`, the starting minimum before the dashboard shows a figure.

`handoffs/<seq>-<agent>-<task>.md`: Markdown with exactly these `##` headings: Done, Changed files, Evidence, Decisions, Open questions, Next.

`verdict.json`: `{"format":1,"round":1,"verdict":"approve|changes","items":["…"],"decision":"D-012"}`

`review.json`: `{"format":1,"round":1,"items":[{"id":"R-1","task":"T4","text":"…","status":"open|closed"}]}`

`brief.md`: Markdown sections Goal, Tier and stage, Open tasks, Recent decisions, Open review items, Owner preferences (from `.groundwork/memory.md`).

**Packet** (SubagentStart context): plain text lines, ids and paths only, for example:

```
run       r-20261102-141022-eks-private · task T4 rev 3 · tier T3 · stage build
agent     groundwork:builder-kubernetes
criteria  AC-4.1 resources set · AC-4.2 IRSA annotation
owns      charts/app/**
depends   T3 done (E-T3-1)
decisions D-002 · D-005
review    R-1 open
previous  handoffs/07-builder-terraform-T3.md
memory    .groundwork/memory.md
handoff   write handoffs/08-builder-kubernetes-T4.md before stopping
budget    maxTurns from the agent file (80)
```

**Export bundle:** `openspec/changes/<change>/groundwork-handoff/<run-id>.json`, allow-listed fields only.

**Telemetry:** `${CLAUDE_PLUGIN_DATA}/<profile>/telemetry.jsonl`, with the fields in the telemetry spec.

`domain.toml`

```toml
name = "terraform"
version = "1.0.0"
patterns = ["**/*.tf", "**/*.tfvars", ".spacelift/**"]
skills = ["tf-core", "gcp", "aws", "spacelift"]
model = "sonnet"
effort = "medium"
checks = [["terraform", "fmt", "-check"], ["terraform", "validate"]]
optional_tools = ["tflint"]
```

`mcp/catalog.toml`

```toml
[[server]]
name = "github"
scope = "project"
auth = "env:GITHUB_TOKEN"
writes = false
agents = ["explorer", "investigator", "final-reviewer"]
```

`rules/tiers.toml`: an ordered list of rules. Each rule has `id`, `tier`, `any` (regex list), and `unless` (negation regex list).

`.groundwork/project.toml`: `prod_kube_contexts`, `prod_tf_workspaces`, `prod_globs`, `protected_globs`, `test_command`.

`$.store` index: `{"runs":[{"id":…,"project":<path hash>,"profile":…,"stage":…,"updated":…}]}`.

## Component catalog

### Agents

| Agent | Model · effort | Tools | Writes |
|---|---|---|---|
| explorer | haiku · low | Read, Grep, Glob, Bash | nothing |
| investigator | sonnet · high | Read, Grep, Glob, Bash | `evidence/` |
| planner | opus · high | Read, Grep, Glob, Write, Edit, Bash | `openspec/changes/<change>/` |
| qa | sonnet · high | Read, Grep, Glob, Write, Edit, Bash | test paths |
| egm | opus · high | Read, Grep, Glob, Write | `verdict.json` |
| builder-general | sonnet · medium | Read, Grep, Glob, Write, Edit, Bash | owned paths |
| builder-terraform | sonnet · medium | Read, Grep, Glob, Write, Edit, Bash | owned paths |
| builder-kubernetes | sonnet · medium | Read, Grep, Glob, Write, Edit, Bash | owned paths |
| final-reviewer | opus · high | Read, Grep, Glob, Bash, Write | `review.json` |
| docs | sonnet · medium | Read, Glob, Write | vault path |

These values are starting points; the eval tunes them.

### Skills

- **Commands:** run, status, handoff, mcp, profile, eval, learn, domain, approve, doctor.
- **Internal** (`user-invocable: false`): route, evidence, planning, test-design, review-rubric, git-flow, docs-template.
- **Domain:** tf-core, gcp, aws, spacelift, k8s-core, gke, eks, helm.

### Hooks

All hooks are command hooks written in Python 3.11 with the standard library only.

| Hook | Event | Matcher | onFailure |
|---|---|---|---|
| session-start | SessionStart | startup, resume, compact, clear | continue |
| prompt-route | UserPromptSubmit | — | continue |
| pre-guard | PreToolUse | `^(Bash\|Edit\|Write\|NotebookEdit\|Read\|Grep\|Glob)$\|^mcp__.*` | block |
| pre-dispatch | PreToolUse | `Agent` | block |
| post-record | PostToolUse | — | continue |
| post-failure | PostToolUseFailure | — | continue |
| denied-log | PermissionDenied | — | continue |
| agent-start | SubagentStart | `^groundwork:` | continue |
| agent-stop | SubagentStop | `^groundwork:` | n/a (block counter) |
| stop-verify | Stop | — | n/a (block counter) |
| pre-compact | PreCompact | — | continue |
| session-end | SessionEnd | — | continue |

### Mod

| Mods API | Use |
|---|---|
| `ui.render` at `AbovePrompt` | Status band |
| `ui.render` at `Pane` | Run board |
| `$.ui.toast` | Alerts |
| `$.command.register` | Board and band commands |
| `$.session.usage()` | Context use and cost |
| `agent.spawn` | Model correction |
| `tool.call` on `SendMessage` | Model correction on resume |
| `turn.step` | Stage-boundary routing, off by default |
| `$.store` | Run index |

### `gw` commands

- `run new | status | report`
- `task claim | done | block | list`
- `approve`, `reject`
- `decide`, `why`
- `remember`
- `handoff write | export | load`
- `brief`
- `profile diff | apply | revert`
- `mcp list | check | enable | disable`
- `domain new | build`
- `eval run | compare`
- `dashboard`
- `doctor`
- `learn propose`

## Reuse from 2.x and gw-bench

| New part | Reuse |
|---|---|
| pre-guard shell parsing, force-push and secret tables | `hooks/block_protected_push.py`, `hooks/groundwork_task_gate.py` (`split_segments`, secret-command tables) |
| fail-open JSONL records | `hooks/groundwork_telemetry.py` |
| brief | `hooks/groundwork_brief.py` |
| profile apply and revert | `scripts/merge_settings.py`, `scripts/unmerge_settings.py` |
| status line | `scripts/groundwork_statusline.py` |
| tier rule tests | `tests/routing_scenarios.json` |
| eval, stats and canaries | gw-bench `bench/stats.py` (`bootstrap_ci`, `compare`), `bench/canary.py`, `bench/grader_sandbox.py` |

## Testing strategy

| Layer | How it is tested |
|---|---|
| `gw` and hook scripts | Unit tests on fixtures |
| Hook sequences | A hook-replay harness that feeds recorded event JSON (SubagentStart → PreToolUse → SubagentStop …) to the hook scripts and `gw` in order. It is used for tier runs in 12.1 |
| Mod | `claude plugin test` (confirmed in Phase 0, 1.4). `claude plugin validate --strict` needs an `author` in the manifest |
| Live behaviour | The gw-bench focused eval, only with owner approval |

## Risks / Trade-offs

- **Bash writes outside scope are caught after the fact, not prevented.** Mitigated by the snapshot diff, the scope-check record, the sandbox, the state hash in the log and the hard denies.
  - Blind spots that remain: changes to git-ignored paths, files outside the repository, and effects outside the filesystem (network calls, cloud APIs). The sandbox and the hard denies cover these instead.
- **Mods may not run in the cloud or `-p`.** The design degrades to hooks plus the status line.
- **More agents mean more tokens.** The tiers, T0/T1 in the main session, and the loop limits keep this down.
- **Skill descriptions cost context every turn.** Descriptions are one line, with `paths` limits.
- **Plugin evals and monitors are experimental.** gw-bench stays the authoritative eval.
- **Two harnesses during the transition.** 3.x runs in its own profile or config directory until cutover.

## Migration Plan

1. Phase 0 checks, which can run alongside plan approval. Live checks need owner approval.
2. The 2.5.0 focused-pilot baseline (gw-bench #78 task 7.5). **Deferred by the owner on 2026-10-30.** The focus is Groundwork 3, so 12.1 and 12.3 wait for an owner decision. Until a baseline exists, no 3.x release is marked as replacing 2.x (release-gating).
3. Alpha after task groups 2 to 5: the owner uses it daily.
4. The full tiers, packs, mod, MCP, dashboard and release gate.
5. A cutover change after 3.x meets or beats the baseline.
6. Rollback: disable the plugin and revert the profile; 2.5 stays installed until cutover.

## Resolved questions (owner input welcome)

- **Main-session model routing:** off by default. It is turned on only for T1/T2 stage boundaries if the eval shows lower cost with no accuracy loss.
- **Vault:** a new dedicated work vault, e.g. `~/Obsidian/Work-Groundwork/` with `Runs/YYYY/MM/`, `Decisions/`, `Runbooks/` and `Templates/`. The path is set through `userConfig`. The owner confirms that work rules allow it, and that any vault sync is approved.
- **First MCP catalog:** empty. Add read-only servers only when a wave-1 task needs one: GitHub first, then a docs lookup, then read-only cloud or cluster inventory if the CLIs fall short. No write-capable cloud, Spacelift or Elastic servers.
- **Ansible and Elastic:** separate changes after wave 1 passes its eval. Ansible comes first, since it has offline checks. Elastic needs owner input on which checks count as evidence.
- **A 2.5.x "quiet" patch** (remove the task-gate ask prompts and the reply check) is possible as a separate small change. The owner decides.
