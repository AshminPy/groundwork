# Phase 0 results (tasks 1.1–1.8)

Run on 2026-10-30 with Claude Code 2.1.314 on Linux, owner-approved.

Each live probe ran `claude` with:
- a fresh `CLAUDE_CONFIG_DIR` and `HOME`;
- the minimal environment allow-list from gw-bench `arms.py`;
- a throwaway probe plugin;
- `--model haiku`.

The probes ran in 11 sessions: 8 `-p` runs and 1 interactive tmux session for checks 1.1–1.6, and 2 more short `-p` runs to repeat 1.7 with a short `TMPDIR`. No real config or Groundwork install was touched.

## 1.1 Agent identity

| Event | `agent_id` | `agent_type` |
|---|---|---|
| PreToolUse on `Agent` (main session) | absent | absent; `tool_input.subagent_type` = `p0probe:probe` |
| SubagentStart | `ab35ead6961c57268` | `p0probe:probe` |
| PreToolUse on `Bash` (in subagent) | same id | `p0probe:probe` |
| SubagentStop (twice) | same id | `p0probe:probe` |

- Two separate launches got different ids.
- **Result:** `agent_type` for a plugin agent is `<plugin>:<agent>`.
- **Result:** `agent_id` stays the same from SubagentStart through PreToolUse to SubagentStop. D5 holds as designed.
- **Result:** pre-dispatch sees the target agent type in `tool_input.subagent_type`.

## 1.2 SubagentStart context and SubagentStop blocking

- **Context injection works.** `hookSpecificOutput.additionalContext` from SubagentStart reached the subagent, which reported the injected word.
- **Blocking works.** A `{"decision":"block","reason":…}` from SubagentStop made the subagent continue and run the requested command. The next SubagentStop had `stop_hook_active: true`.
- **No platform cap was seen.** With up to 12 blocks allowed, Claude Code delivered 13 SubagentStop events and 12 blocks. The subagent made 11 tool calls, then the model itself refused to continue.
- **Result:** Groundwork's own block counter (D7) is required.
- **Also seen:**
  - In `-p`, a main-session `Stop` fired while the subagent was still running in the background.
  - So stop-verify must allow the stop while any bound agent is still running.

## 1.3 Mod surfaces

| Surface | Result |
|---|---|
| `-p` | Runs. `session.start` and `turn.step` fired; `turn.step` saw `claude-haiku-5-5` |
| Interactive terminal (tmux) | Runs. Both events fired |
| claude.ai cloud session | **Not tested.** It needs a new cloud session with the plugin installed from a marketplace. The settings docs say plugins declared in a repo's settings "don't load in a cloud session" in some setups, so the status-line and hooks fallback (D2) stays the plan |

- `claude plugin validate` checks mod code by static analysis: the `$` argument may only be passed to functions declared at the top of the file.

## 1.4 Plugin tooling

- `claude plugin validate <dir>` exists.
- `--strict` turns warnings, such as a missing `author`, into failures.
- The directory checks (README, LICENSE, icon) are reported but fail only with `--profile directory`.
- `claude plugin test [dir]` exists and runs `*.test.ts` / `*.test.tsx` files.

## 1.5 Profile settings keys (settings and sandboxing docs)

| Intent | Key | Note |
|---|---|---|
| Auto mode | `permissions.defaultMode: "auto"` | Takes effect only from user or managed settings, not project or local. So each profile is the user `settings.json` of its own config directory |
| Deny rules | `permissions.deny: ["Read(...)", "Bash(...)"]` | Absolute paths are written `//path` in permission rules |
| Extra working folder | `permissions.additionalDirectories` | — |
| Sandbox | `sandbox.enabled`, `sandbox.failIfUnavailable`, `sandbox.allowUnsandboxedCommands` | — |
| Sandbox paths | `sandbox.filesystem.allowWrite`, `denyWrite`, `denyRead`, `allowRead` | Plain absolute or `~` paths |
| Model | `model` | A switch re-reads the conversation uncached |
| Effort | `effortLevel` | — |
| Environment | `env` | — |
| Status line | `statusLine` | — |
| Minimum version | `requiredMinimumVersion` | Managed only, so Groundwork checks the version in `gw doctor` instead |

## 1.6 Worktree subagents

- The worktree is created at `<repo>/.claude/worktrees/agent-<id>`.
- Hook `cwd` (in the input and the process) is the worktree. Hook `CLAUDE_PROJECT_DIR` is the main repo.
- `git rev-parse --git-common-dir` in the worktree resolves to the main repo's `.git`, so D8's run-root lookup works.
- `CLAUDE_PROJECT_DIR` is empty inside the subagent's own Bash commands.
- The worktree isolation check refused one chained command (`pwd; git rev-parse …`) because it "could not verify the git commands stayed inside the worktree". The same commands passed when run one per call.
- **Results:**
  - The main-checkout snapshot diff must exclude `.claude/worktrees/`.
  - The builder template tells builders to run git commands one per call.

## 1.7 Writing to a vault outside the working directory (auto mode, sandbox on)

| Tool | Without `allowWrite` | With `sandbox.filesystem.allowWrite: [vault]` |
|---|---|---|
| Write tool | Written, no prompt | Written, no prompt |
| Bash `echo > vault/file` | Blocked: "Read-only file system" | Written |

- The sandbox doesn't cover the Write tool, and auto mode allowed it outside the working directory. So pre-guard's owned-path check is the control that keeps the docs agent inside the vault.
- **Result:** the work profile sets `sandbox.filesystem.allowWrite` to the vault path, since docs has no Bash anyway. Pre-guard limits Write and Edit to the vault for docs.
- **Also seen:**
  - With a long `TMPDIR` path, the sandbox failed to start ("Failed to create bridge sockets").
  - With `failIfUnavailable` set, every Bash call was then refused with "Sandbox is required", which is the fail-closed behaviour we want.
  - A short `TMPDIR` fixed it. The likely cause is the Unix socket path length limit; this is an inference.
  - `gw doctor` warns when `TMPDIR` is longer than 60 characters.

## 1.8 ECC inventory

`plugin/toolchain/ecc-inventory.toml` lists ECC 2.2.1 (git 5064474d, MIT):

| Kind | Count |
|---|---|
| Agents | 68 |
| Skills | 286 |
| Commands | 94 |
| Hooks | 22 |

- **Decision:** the ECC plugin is not enabled in Groundwork 3 profiles.
  - Enabling it lists every agent, skill and command description in context on every turn.
  - Its hooks overlap with or conflict with Groundwork's: GateGuard denies edits until facts are listed, `plan-canvas-pending` blocks Stop, and `mcp-health-check` makes network calls.
- **Ported with attribution (10):**
  - `kubernetes-patterns` → k8s-core
  - `tdd-workflow` and `tdd-guide` → test-design
  - `python-testing` → builder-general
  - `security-review`, `code-reviewer` and `security-reviewer` → review-rubric
  - `git-workflow` → git-flow
  - `planner` → planning, non-duplicate steps only
  - the `--no-verify` deny → pre-guard
- **Not in ECC, written new:** Terraform, GCP, AWS, Spacelift and Helm skills.
- No ECC hook returns an `ask` decision (scanned 2026-10-30).
