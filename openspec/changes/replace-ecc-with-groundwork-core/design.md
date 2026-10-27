# Design: replace ECC with Groundwork core

Revision 3, 27 Oct 2026. It addresses both Elephant-Goldfish (EGM) reviews:
- `docs/designs/ecc-removal-egm/consolidated_review_report.md`, round 1 (finding IDs A1-A8, M-1 to M-17)
- `docs/designs/ecc-removal-egm/rev2/consolidated_review_report.md`, round 2 (NEW-B1 to NEW-B3, N-3 to N-20)

The finding each part answers is noted in brackets.

## Problem

Groundwork installs ECC in full, and ECC cannot be installed in part. Every request then pays for 68 agent descriptions, and every tool call waits for ECC's hooks (p90 7.5 s on this Mac). About 100 uses in 66 days touch 5 agents and 3 skills. A few ECC parts protect quality or safety and nothing else covers them. Removing ECC must keep those parts, must not lower answer quality, and must be reversible on an existing machine.

## Proposed architecture

- **Before:** Claude Code loads ECC (plugin: 68 agents, about 290 skills and commands, 23 hook entries) and Groundwork (rules, 15 hook entries).
- **After:** Claude Code loads Groundwork only. Groundwork gains:
  - one reviewer agent file
  - one deny rule in its existing git guard
  - one ask rule in its existing task gate
  - a `tokens` object in its existing per-turn telemetry record
  - an installer step that migrates an existing machine off ECC, after a backup

  No new hook entry and no new background process are added.

## Glossary

| Term | Meaning here |
|---|---|
| ECC | The third-party Claude Code plugin `ecc@ecc` (github.com/affaan-m/ECC), installed today by Groundwork, version 2.2.1 |
| Config dir | Claude Code's configuration folder: `~/.claude`, or `$CLAUDE_CONFIG_DIR` when set |
| Hook | A script Claude Code runs on an event. PreToolUse runs before a tool call and can allow, ask or deny. Stop runs when Claude ends a turn. |
| Ask / deny | A PreToolUse answer. Ask shows the owner a prompt; in headless runs (`claude -p`) an ask becomes a denial. Deny stops the call and tells Claude why. |
| Task gate | Groundwork's PreToolUse hook `hooks/groundwork_task_gate.py` |
| Git guard | Groundwork's PreToolUse hook `hooks/block_protected_push.py` |
| Review gate | Groundwork's Stop hook `hooks/require_material_review.py`. It blocks the end of MATERIAL work until a reviewer's `REVIEW RESULT` block reports `Must-fix: 0`. |
| MATERIAL | Groundwork's highest work tier (security, deployment, cross-module changes) |
| Task brief | Groundwork's per-branch state file, saved by hooks on PreCompact and Stop |
| Bench copy | A copy of a config dir under `~/gw-bench`, used so tests never touch the owner's real `~/.claude` |
| Arms V / G | Benchmark arms: V is plain Claude Code, G is Groundwork |
| KEEP / DROP | Inventory fates. KEEP: rebuilt in Groundwork, with a test. DROP: removed on purpose, with the reason recorded. |
| Migration step S0-S9 | The ordered steps of the ECC migration (D6) |
| Read-before-edit rate | Share of Edit/Write calls on a file that was Read earlier in the same session |
| Same-day baseline | ECC-on results produced on the same day as the ECC-off results they are compared with |

## Context

See proposal.md for why. Only facts that shape how are listed here. Each owner-machine observation has its date and command.

**ECC on this Mac.** ECC v2.2.1 is installed by `install.sh:59-72`, with `hook_profile` set to `standard` by `scripts/merge_settings.py:300-303`.

**Partial install is still impossible** (re-tested 27 Oct 2026, Claude Code 2.1.310, in a bench copy; answers M-4):
- A deny rule `Agent(ecc:*)` or `Agent(ecc:architect)` does not remove agents from the list sent to the model.
- The session init record still lists all 68 ECC agents, including `ecc:architect`.
- `/context` still shows 5.2k tokens of custom agents.
- `claude plugin install` has no subset flag.
- So the only way to drop ECC's per-request cost is to remove the plugin.

**Measured cost**, `claude -p /context` in a fresh session on this Mac, 27 Oct:

| Item | Size |
|---|---|
| Whole request | 65.1k tokens |
| Custom agents | 8.0k |
| ECC's 68 agents | 6,195 |
| Owner's 17 agents | 1,812 |
| ECC's skill-list entries (369 = 286 skills plus commands; Claude Code truncates long skill lists, so most entries cost 0) | ~340 |

**Measured use.** `Agent` and `Skill` tool calls and typed slash commands, over every transcript kept on this Mac. The oldest kept transcript is from 22 Aug 2026 (`ls -lt ~/.claude/projects/*/*.jsonl`), so the window is 66 days, not 90.

| ECC part | Times used |
|---|---|
| `code-reviewer` agent | 88 |
| `python-reviewer` agent | 7 |
| `security-reviewer` agent | 5 |
| `code-explorer` agent | 4 |
| `architect` agent | 3 |
| other 63 agents | 0 |
| `security-scan` skill | 3 |
| `resume-session` skill | 2 |
| `save-session` skill | 1 |
| other skills | 0 |
| `/ecc:terminal-opener`, typed | 2 |
| `chrome-devtools` MCP tools | 0 |

**Measured hook wait.**
- Durations come from this session's transcript (`hook_success.durationMs`). ECC PreToolUse: median 235 ms, p90 7,531 ms. Groundwork and other hooks: p90 164 ms.
- Cause: `scripts/hooks/mcp-health-check.js:19` loads Node's `https` module on every tool call (matcher `.*`).
  - `node -e "require('https')"` takes 7.47 s with `NODE_USE_SYSTEM_CA=1` and 0.08 s with `=0`.
  - The desktop session's environment carries `1`; what sets it is unknown.
- Each ECC hook entry also starts 2-3 Node processes (`plugin-hook-bootstrap.js:193-197`, `run-with-flags.js:208-257`).

**Fact-forcing friction.** This session's transcript holds 121 tool calls denied by ECC's "Fact-Forcing Gate". Command: count of `tool_result` errors containing that string in `f2934e6f….jsonl`.

**Benchmark baseline** (`~/gw-bench/runs/vg-2.5.0-r1b/results.jsonl`, 26 Oct, 1 repeat):

| Arm | Correct | Answers with an "Evidence & references" section | Median cited lines | Median input tokens per answer |
|---|---|---|---|---|
| G | 20/20 | 18 | 10 | 79,133 |
| V | 20/20 | 0 | 6.5 | 21,419 |

- Input tokens = input + cache_read + cache_creation (`bench/report.py:36`).
- The benchmark runs with `NODE_USE_SYSTEM_CA=0`, so it cannot show the hook wait.
- Its code is module `orchestrator/bench` on branch `bench/vanilla-vs-groundwork`, commit `cb0d3f4`, checked out at `wt-bench` in this session's scratch folder. `arms.py:80-86` sets `CLAUDE_CONFIG_DIR` for an arm.

**Config-dir isolation works** (27 Oct): `CLAUDE_CONFIG_DIR=~/gw-bench/vanilla claude plugin list` shows no ECC, while `~/gw-bench/groundwork` shows `ecc@ecc 2.2.1`.

**Plugin CLI, verified with `--help` on 2.1.310:**
- `claude plugin uninstall [--keep-data]`. Without the flag it deletes `~/.claude/plugins/data/<id>/`.
- `claude plugin marketplace remove <name>`.
- `claude plugin list --json` returns a list of `{id, version, enabled, …}`.

**Backup and rollback already exist, but only in `setup.sh`.**
- `make_backup` (`setup.sh:239-256`) copies the whole config dir (APFS clone) to `$GROUNDWORK_BACKUP_DIR` (default `~/.claude-backups`) with a `BACKUP-INFO.txt`.
- `./setup.sh --rollback [DIR]` (`setup.sh:844-880`) moves the current config dir aside and restores the copy, offline.
- `install.sh` makes no backup.

**Agent marker.** An agent file with an extra frontmatter key `groundwork-managed: true` loads normally. Verified 27 Oct: the init record lists it.

**Transcript usage lines repeat.** In this session's transcript, 5,002 assistant lines carry `usage`, but there are only 1,043 distinct `message.id` values. Subagent transcripts are separate files in `<session>/subagents/agent-*.jsonl`.

## Goals / Non-Goals

**Goals:**
- Every ECC part marked KEEP in the inventory has a Groundwork replacement with a test. Answers M-12.
- Every part marked DROP is dropped on purpose, with the evidence recorded. The fact-forcing gate is an accepted loss (D4).
- Remove ECC's per-request token cost and its hook wait.
- Keep accuracy and evidence quality, proven by the benchmark and an edit-and-guard scenario set.
- Migrate an existing install safely: a backup first, an offline rollback, and no data deleted.

**Non-Goals:**
- Trimming Groundwork's rules or the owner's personal rules. That is the next change, `trim-always-loaded-rules`.
- Finding what sets `NODE_USE_SYSTEM_CA=1`.
- Cleaning the owner's personal files outside Groundwork: `~/.claude/CLAUDE.md`, `rules/behavior.md`, which mention ECC. These are listed as owner follow-ups.
- Project-scope ECC installs in other repositories. Migration acts only on the target config dir's user-scope install and reports any project-scope install it can see in `claude plugin list --json`.

## Inventory: every ECC part and its fate (M-5)

Produced from:
- `hooks/hooks.json` at `~/.claude/plugins/cache/ecc/ecc/2.2.1`
- the dispatcher lists (`scripts/hooks/bash-hook-dispatcher.js:22-53`, `posttooluse-dispatcher.js:24-49`)
- the profile gate (`scripts/lib/hook-flags.js:120-137`)

"Standard" means ON under `hook_profile=standard`.

| Entry (event) | Part | Standard | Fate | Reason |
|---|---|---|---|---|
| `pre:bash:dispatcher` (PreToolUse Bash) | `block-no-verify` | ON | **KEEP: git guard** (D2) | Nothing else blocks hook bypass (grep of `hooks/*.py` and the settings deny list) |
| | `gateguard-fact-force` (Bash) | ON | DROP (D4) | See destructive-class table below |
| | `auto-tmux-dev` | ON | DROP | Rewrites `npm run dev`; not used here |
| | `commit-quality`, `tmux-reminder`, `git-push-reminder` | OFF | DROP | Not running today |
| `pre:write:doc-file-warning` (PreToolUse Write) | | ON | DROP | Advisory only |
| `pre:edit-write:suggest-compact` (PreToolUse Edit\|Write) | | ON | DROP | Claude Code autocompacts; the task brief survives compaction |
| `pre:observe:continuous-learning` (PreToolUse .*) | | ON | DROP | 25 MB, 1,149 observations, 0 learned rules |
| `pre:governance-capture` (PreToolUse) | | OFF (needs `ECC_GOVERNANCE_CAPTURE=1`) | DROP | Not running today |
| `pre:config-protection` (PreToolUse Write\|Edit\|MultiEdit) | | ON | **KEEP: task gate** (D2) | Integrity control with no Groundwork equivalent |
| `pre:mcp-health-check` (PreToolUse .*) | | ON | DROP | Causes the 7.5 s wait; availability only |
| `pre:edit-write:gateguard-fact-force` (PreToolUse Edit\|Write\|MultiEdit) | | ON | DROP (D4) | |
| `pre:compact` (PreCompact) | | ON | DROP | Task brief saves on PreCompact with no model call. ECC's version runs `claude -p --model haiku`. |
| `session:start` (SessionStart) | | ON | DROP | Task brief and session snapshot replace it |
| `session-start:plan-canvas-sessions` (SessionStart) | | ON | DROP | No Plan Canvas state on this Mac |
| `post:dispatcher:sync` (PostToolUse .*) | design-quality, edit accumulator, console warn, metrics bridge, context monitor | ON | DROP | JS/TS-only or bookkeeping. The context monitor duplicates Claude Code's own display. |
| | `post:governance-capture`, `session-activity-tracker` | OFF / no-op | DROP | |
| `post:dispatcher:async` (PostToolUse .*) | command-log audit and cost log | ON | DROP | Writes every shell command to 9 MB of logs. Groundwork telemetry never stores commands (`hooks/groundwork_telemetry.py`, "never" comment near line 78). |
| | pr-created, build-complete, quality-gate, observe | ON | DROP | Advisory or JS-centric. The project's own lint and test commands are required by the evidence policy. |
| `post:mcp-health-check` (PostToolUseFailure .*) | | ON | DROP | Same `https` cost |
| `post:skill:track` (PostToolUseFailure Skill) | | ON | DROP | Groundwork telemetry records every tool call |
| `stop:plan-canvas-pending`, `stop:format-typecheck`, `stop:check-console-log`, `stop:evaluate-session`, `stop:desktop-notify` (Stop) | | ON | DROP | No-op here or JS/TS-only. The desktop app notifies. |
| `stop:session-end` (Stop) | | ON | DROP | Task brief |
| `stop:cost-tracker` (Stop) | | ON | **KEEP as token totals** (D5) | Groundwork records no tokens today |
| `session:end:marker` (SessionEnd) | | ON | DROP | Internal to the dropped observer |

| Other part | Fate | Reason |
|---|---|---|
| `code-reviewer` agent | **KEEP as `groundwork-code-reviewer`** (D3) | The used reviewer; its confidence and proof rules |
| `python-reviewer` agent | **KEEP, merged** into the reviewer's Python section | One severity model |
| `security-reviewer` agent | **KEEP, merged** into the reviewer's security section (M-1) | A fresh laptop must have a security review without the owner's personal agents |
| `code-explorer`, `architect` agents | DROP | Built-in `Explore` and `Plan` agents cover them |
| 63 other agents; 283 other skills; ECC commands, `rules/`, `contexts/` | DROP | 0 uses since 22 Aug |
| `security-scan` (AgentShield) | DROP from install; document `npx ecc-agentshield@<version recorded at task 6.2> scan` | An npm tool, not plugin code |
| `save-session`, `resume-session` | DROP | Task brief |
| `chrome-devtools` MCP (`npx …@latest`) | DROP | 0 uses |
| `terminal-opener` skill | DROP | Desktop app terminal tabs |

**Fact-forcing gate's destructive classes** (`gateguard-fact-force.js:56`) and what covers each after removal:

| Class | Covered by | Note |
|---|---|---|
| `git push --force`, `-f` | settings deny + git guard | Deny |
| `git reset --hard`, `clean -f`, `checkout/switch --force`, `branch -D` | task gate `_git_destructive` | Ask |
| `rm -rf /`, `rm -rf ~` | settings deny | Deny |
| `git checkout -- <path>`, `git switch -C`, `git commit --amend` | not covered | **Accepted loss.** Local and recoverable through the reflog. ECC also let an identical retry through. |
| `rm -r` of the working directory or outside it | task gate (`groundwork_task_gate.py:725-727`) | Ask |
| `rm -r` of a subfolder inside the working directory; `find … -exec rm`, `find -delete` | not covered | **Accepted loss.** Tracked files are recoverable from git. ECC also let an identical retry through. |
| `dd` | settings deny | |
| SQL `drop table`, `delete from`, `truncate` through a local database client | task gate asks for any database client (`DB_CLIENTS`, defined at `groundwork_task_gate.py:79`, checked at 723-724) | Covered |
| The same SQL through `docker exec … psql` or a script file | not covered | **Accepted loss**, as with ECC's retry |

## Decisions

### D1. Remove ECC entirely
**Chosen:** uninstall the plugin and rebuild 4 parts.

**Alternatives:**

| Option | Tokens | Hook wait | Verdict |
|---|---|---|---|
| Keep ECC, hook flags off | 6.5k remain (agents cannot be filtered, re-tested above) | removed | Rejected |
| Keep ECC, deny unused agents | unchanged (verified) | unchanged | Rejected |
| Remove ECC, rebuild 4 parts | −6.5k | removed | **Chosen** |

This supersedes Groundwork 2.0's `ecc-capability-policy`. That policy's premise ("no partial install") still holds. This change takes the other branch: no ECC.

### D2. Guards: where they live and exactly what they match (A5, M-2)

**No-verify block, in the git guard** (`hooks/block_protected_push.py`):
- A new function `_bypasses_hooks(segment) -> str | None` is called for every git segment, before the existing push-only early exits (lines 947-957). It reuses the existing global-option parser (`GIT_VALUE_OPTIONS`, `-c` alias resolution, `bash -c` / `eval` unwrapping).
- The module docstring changes from push-only to "git guard".

Option facts below were checked with `git <sub> -h` on git 2.50.1, 27 Oct (N-6):
- `commit` and `am` take `-n`/`--no-verify`.
- `merge`, `rebase` and `push` take `--no-verify`.
- `pull` takes `--[no-]verify`.
- `cherry-pick` and `revert` have no such option.
- git accepts an unambiguous abbreviation. `git commit --no-verif` skipped a failing pre-commit hook and created the commit (tested in a throwaway repo). `git merge --no-veri` fails as ambiguous.

| Form | Decision |
|---|---|
| `commit`, `am`, `merge`, `rebase`, `pull`, `push` with `--no-verify`, or with any abbreviation of it (`--no-v`, `--no-ve`, … `--no-verif`) | deny |
| `commit -n`, `am -n`, and `n` inside a short cluster before any value-taking letter (`-an`, `-nm msg`); value-taking letters: commit `m F C c t S u`, am none | deny |
| `commit -mn` (message "n"), `commit -m "fix: no-verify docs"`, `merge --no-verify-signatures`, `pull --verify` | allow |
| `push -n` (dry run), `merge -n` (no stat), `log -n 5` | allow |
| `-c core.hooksPath=…` or `--config-env=core.hooksPath=…` on any git command, the key matched case-insensitively. The new function walks the global options itself, because the existing `_git_invocation` drops `-c` values. | deny |
| Environment prefix before git: `GIT_CONFIG_KEY_<n>=core.hooksPath` (any case), `HUSKY=0`, `HUSKY_SKIP_HOOKS=1`, or `SKIP=` (pre-commit) | deny |
| `git config [--local\|--global\|--system] core.hooksPath <value>` | ask, in the task gate (a normal husky setup step) |
| Aliases defined in a git config file | not resolved; accepted gap, the same as today for push |

- **Fail closed:** when the command text contains `no-verif` or `hookspath` or `husky` (case-insensitive), every path where the guard would otherwise give up denies (N-5). These are:
  - the shell parser returns no segments
  - the four existing give-up returns at `block_protected_push.py:864-866`, `871-873`, `876-877`, `1005-1010`

  Each has a test.
- **Deny text:** "Groundwork: skipping git hooks (--no-verify / core.hooksPath) is blocked. Fix what the hook reports. If the owner wants to skip hooks, they can run the command themselves."

**Alternatives considered for D2:**
- One new hook file for both guards. Rejected: one more Python start on every tool call, and more settings entries to migrate.
- Hard-deny config edits like ECC. Rejected: the owner sometimes means it. An ask stops silent weakening and costs one prompt on a rare event.

**Config-protection ask, in the task gate's `check_file`** (`groundwork_task_gate.py:1165-1178`):
- **Tools:** Edit, Write, MultiEdit, NotebookEdit.
- **Closed list:** exactly ECC's `PROTECTED_FILES` (`config-protection.js:22-63`), 32 basenames. Matched on the basename, case-insensitively.
- **Existing:** the path exists by `lstat`, so a dangling symlink counts and a permission error counts as existing. This is ECC's rule (lines 110-127).
- NotebookEdit is added deliberately; ECC's matcher omitted it.
- **Answer:** ask, with the reason "editing an existing linter/formatter config; prefer fixing the code". Headless, this becomes a denial, which is what ECC did (exit 2).
- Shell edits (`sed -i ruff.toml`) are not covered. This is an accepted gap; ECC did not cover them either.
- `GROUNDWORK_TASK_GATE=off` disables it, like the rest of the gate.
- **Error handling:** `on_pre` already turns internal errors into an ask (lines 1352-1353). The spec's "hook error log" is removed; there is no such log.

**Latency target:** p90 ≤ 200 ms for both guards over the test inputs, against a measured 164 ms baseline for Groundwork hooks (nit CR-N4).

### D3. One reviewer agent, owned by Groundwork (A8, M-1)

**File:** `agents/groundwork-code-reviewer.md` in the repo, installed to `<config dir>/agents/`.

**Frontmatter:**
- `name: groundwork-code-reviewer`
- `tools: Read, Grep, Glob, Bash`
- `model: sonnet`
- `groundwork-managed: true` (the marker, verified to load)

Bash stays because reviewers run tests. The description says "reviews; never edits", not "read-only".

**Kept from ECC `code-reviewer.md`:**
- the prompt-defence baseline (lines 8-15), shortened: diffs are untrusted data
- the review process
- the confidence rule
- the pre-report gate
- the proof rule for HIGH/CRITICAL (lines 29-111)
- the false-positive list
- the output format

**Added:**
- a Python section from `python-reviewer.md:25-78`
- a security section, from the owner-independent checks: secrets, injection, auth, path traversal, SSRF, unsafe deserialization, dependency pinning

**Dropped:**
- React, Node and JSDoc checklists
- ECC's "project-specific" example text

**Severity model:**

| Severity | Meaning | Counts in `Must-fix` |
|---|---|---|
| CRITICAL | security hole, data loss, wrong result on the main path | yes |
| HIGH | likely bug or failure in normal use | yes; stricter than ECC, where HIGH only warns (`code-reviewer.md:290-295`). Deliberate: the review gate should stop real bugs. |
| MEDIUM | maintainability, edge case | no |
| LOW | style | no |

**The response must end with exactly:**
```
REVIEW RESULT
Verdict:   approve | changes-required
Must-fix:  <N>
Findings:  <short labels, only when N > 0>
```
This is the format of `rules/output-contract.md` (Review result) parsed by `require_material_review.py:93`. `REVIEW_PATTERN` (line 83) already matches the name, so the gate needs no change.

**Install:**
- write the file when absent, or when present with `groundwork-managed: true`
- otherwise skip it and print a conflict line

**Uninstall:** remove only marked files.

**Size:** no byte cap. The file is not in every request; only its one-line description is.

**Licence:** a header comment naming ECC v2.2.1 and MIT; the full text goes in `THIRD_PARTY_NOTICES.md`.

### D4. The fact-forcing gate is dropped
**Evidence:**
- It is not a guard: an identical retry passes (`~/.claude/plugins/cache/ecc/ecc/2.2.1/scripts/hooks/gateguard-fact-force.js:1264-1274`).
- Its quality claim rests on 2 self-run tasks.
- It denied 121 calls in this session.

**Accepted loss:** the destructive-class table above.

**Quality risk:** edits made without reading the code. This is measured by the edit-and-guard set's read-before-edit rate (Validation), not assumed.

**Alternatives:**
- Port a smaller version (first edit per file only). Rejected: same friction, same weak evidence.
- Keep ECC only for the gate. Rejected: D1.

**Revisit trigger:** the read-before-edit rate drops by more than 10 points versus ECC-on.

### D5. Token totals (A7, M-8)
- **Turn boundary:** the same as the per-turn record, `current_turn()` in `hooks/groundwork_telemetry.py:236`. `mark_turn_start` belongs to the reply check and is not used.
- **De-duplication:** assistant lines are grouped by `message.id`, and the last line's `usage` wins (verified: 5,002 lines, 1,043 ids).
- **Main thread:** fields `tokens.main.{input, output, cache_read, cache_creation, requests}`, where `requests` = distinct message ids in the turn.
- **Requests** exclude messages whose `model` is `<synthetic>`.
- **Main-transcript filter:** lines with `isSidechain: true` are skipped, so subagent work is never counted twice.
- **Turn start:** the timestamp of the first entry `current_turn()` returns. When `current_turn()` hit `TAIL_CAP`, the first entry is not a human prompt; the hook detects this and sets `tokens.truncated: true`.
- **Subagents:** `tokens.subagents.{input, output, cache_read, cache_creation, requests}`.
  - Source: lines in `<session>/subagents/agent-*.jsonl` whose `timestamp` is at or after the turn start. Lines are filtered, not whole files, so an older subagent's earlier work is not counted again.
  - De-duplicated the same way as the main thread.
  - Read caps: the 50 newest files and 8 MB from the end of each. Hitting a cap sets `tokens.truncated: true`.
  - Subagents are often the largest cost, so they are recorded, not dropped.
- **Placement:** an optional top-level `tokens` object in the per-turn record. There is no schema bump, because `groundwork_report.py:113` treats any schema other than 2 as unknown. Readers that do not know `tokens` ignore it.

- **No record:** when `build_record` returns `{}` (a conversational turn with no metadata block), no token record is written. This matches the existing record policy. Token totals therefore cover task turns only, which is stated in the report.
- **Read cap:** within `TAIL_CAP` (32 MB). A longer turn is recorded with `tokens.truncated: true`.
- **Missing transcript:** no `tokens` key.
- **Privacy:** the new code reads only `message.id`, `message.usage`, `type` and `timestamp`.
- **Report:** `scripts/groundwork_report.py`, which already reads `events.jsonl`, gets a token section: median and p90 per turn and per request, main versus subagent, over its existing period options.
  - `normalise()` copies `tokens` through.
  - A small percentile helper is added next to `compute()`.
  - The section appears in the Markdown snapshot and the HTML dashboard.
  - Not `groundwork usage`, which reads the statusline's 8-day `usage.jsonl` (`scripts/groundwork_statusline.py:75-76`).

**Alternatives considered for D5:**
- Parse `/cost` or the statusline. Rejected: on this Mac another tool owns the statusline, and `/cost` is not available to hooks.
- Price in dollars. Rejected: subscription use, and prices change.

### D6. Migration and rollback (A1, A2, M-3, NEW-B2, N-3, N-4)

**Where it lives:** a new `scripts/migrate_off_ecc.py`, run by `install.sh` in two calls:
- `check-and-backup`: at the very start of `install.sh`, before it writes anything.
- `remove`: at the end, after Groundwork's guards and reviewer are installed.

**Backup:** `setup.sh` gains a `--backup` mode. It runs the existing `make_backup` (`setup.sh:239-256`, unchanged) and prints the backup path.
- The migration calls the `setup.sh` that sits next to the running `install.sh`. The installed copy in `groundwork/bin/` also has the mode.
- No new file has to be sourced, so the installed `setup.sh`, used by `groundwork rollback` and `--doctor`, keeps working (NEW-B2).
- When `setup.sh` itself runs `install.sh`, it has already made a backup. It passes that path in `GROUNDWORK_BACKUP_PATH`, and the migration reuses it instead of making a second one (N-4).

**Hook list for `--verify`:** `install.sh` writes `groundwork/hook-manifest.json`, listing every hook entry `merge_settings.py` registered. `setup.sh --verify` reads it, so the installed `setup.sh` needs no Python import from the repo (NEW-B2).

**Steps, in order:**

| Step | When | Action | On failure |
|---|---|---|---|
| S0 | start | `GROUNDWORK_KEEP_ECC=1` → print "ECC kept by owner"; skip S1-S9 | — |
| S1 | start | `claude` on PATH, and `claude plugin list --json` (run with the target `CLAUDE_CONFIG_DIR`) lists `ecc@ecc` at user scope? If not: report "ECC absent" plus any project-scope ECC seen; skip the rest | `claude` missing → skip the migration with a warning; install continues |
| S2 | start | Safety check: the `installPath` of `ecc@ecc` and of the marketplace clone must be under the target config dir (N-3) | Stop the migration and name the path; nothing removed |
| S3 | start | Backup: reuse `GROUNDWORK_BACKUP_PATH`, or run `setup.sh --backup`; record the path | Stop the migration; nothing removed |
| S4 | end | Confirm every entry in `groundwork/hook-manifest.json` is in `settings.json` and `agents/groundwork-code-reviewer.md` exists | Stop; nothing removed |
| S5 | end | `claude plugin uninstall ecc@ecc --keep-data` | Stop; print the rollback command; settings untouched |
| S6 | end | `claude plugin marketplace remove ecc` | Report and continue (already absent is fine) |
| S7 | end | Remove `enabledPlugins["ecc@ecc"]`, `extraKnownMarketplaces.ecc`, `pluginConfigs["ecc@ecc"]` and any parent left empty, using the existing atomic writer in `merge_settings.py` | Print the rollback command; `install.sh` exits non-zero |
| S8 | end | Report, never edit, other settings values containing `/plugins/cache/ecc/`. List ECC data outside the plugin that exists, with sizes, and print one removal command. | — |
| S9 | end | Print "Restart open Claude Code sessions; they keep ECC's hooks until restart", the backup path and the rollback command | — |

**Rollback (primary, offline):** `./setup.sh --rollback <backup path from S3>`, from the repo or from `groundwork/bin/`. It restores the config dir as it was before this `install.sh` run, including ECC's cache, marketplace clone and settings. Anything else changed in the config dir since the backup is also reverted; the current folder is kept aside (`setup.sh:856-860`).

**Rollback (fallback, network):** `claude plugin marketplace add "affaan-m/ECC#v2.2.1"`, then `claude plugin install ecc@ecc --scope user --config hook_profile=standard`, then `GROUNDWORK_KEEP_ECC=1 ./install.sh` so ECC is not migrated again.

**Settings Groundwork stops writing:**
- `merge_settings.py:299-303` is deleted, so `hook_profile` is no longer set.
- `GATEGUARD_EXEMPT_GLOBS` moves from `GROUNDWORK_ENV_DEFAULTS` (`merge_settings.py:100-105`) to a legacy list. `unmerge_settings.py` still removes it on uninstall (N-15).
- Existing values are left alone when `GROUNDWORK_KEEP_ECC=1`.

**`--verify` with ECC kept:** shows "ECC present, kept by owner (not used by Groundwork)".

**Idempotence:** a second run finds no `ecc@ecc` at S1 and changes nothing.

**`groundwork update`** runs `install.sh` (`scripts/groundwork_update.py:74`), so it migrates the same way. There is a test.

**Alternatives considered for D6:**
- `claude plugin disable`. Rejected: it leaves the marketplace and cache, so "is ECC here?" stays ambiguous.
- A separate `scripts/backup.sh`. Rejected: the installed `setup.sh` could not source it (NEW-B2).

### D7. Order of work and benchmark isolation (A3, M-9, M-16, NEW-B1)

**Prerequisites:**
- **P1, done:** the task-gate false-prompt fix (PR #73, merged 27 Oct). It touched the same file as D2's config-protection, so it went first. Its 16 review-found bypasses are tests.
- **P2, portable install (known gap "fix 2"), its own change and PR.** Benchmark copies cannot be isolated without it (NEW-B1). After it:
  - hook commands read `python3 "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/<name>.py"`; hooks see `CLAUDE_CONFIG_DIR`, verified 27 Oct
  - the report's launchd label is unique per config dir
  - `install.sh` edits shell rc files only for the default config dir or when `GROUNDWORK_EDIT_SHELL_RC=1`
  - re-installing removes legacy `~/.claude/hooks/...` entries

**Benchmark folders** (`~/gw-bench/g-ecc-on`, `~/gw-bench/g-ecc-off`):
- Made with `cp -Rc ~/gw-bench/groundwork <dir>`. Copies stay logged in: a copy ran `claude -p` on 27 Oct.
- A prep script then rewrites the source path to the copy's path in `plugins/installed_plugins.json`, `plugins/known_marketplaces.json` and `settings.json`. It checks that `grep -r ~/gw-bench/groundwork <dir>/{settings.json,plugins/*.json}` finds nothing.
- Every bench `install.sh` run sets `CLAUDE_CONFIG_DIR=<dir> GROUNDWORK_NO_LAUNCHCTL=1 GROUNDWORK_LAUNCH_AGENTS_DIR=<scratch> GROUNDWORK_BACKUP_DIR=<scratch>`. Both variables exist (`groundwork_report.py:635,655`).
- Before and after each bench run, a SHA-256 list of `~/.claude/settings.json`, `~/.claude/plugins/installed_plugins.json`, `~/.zshrc`, `~/.bashrc`, `~/.profile` and `~/Library/LaunchAgents/com.groundwork.*` must be identical.

**Order:**
1. P1 (done), then P2.
2. **Baselines (group 1):** bench folders, `/context`, `bench.run`, edit-guard set, hook-wait from real sessions.
3. **Build and unit-test, ECC still installed:** guards, reviewer agent, token totals, `setup.sh --backup`, the migration (against a stub `claude`), installer, setup and docs changes. Each group includes its test updates, so the suite is green after every group.
4. **Real migration in `g-ecc-off` only,** then rollback and re-migration, then measurement against a same-day `g-ecc-on` run.
5. **Fresh independent review** of the full diff.
6. **Merge, `install.sh` on this Mac,** live checks.

## Risks / Trade-offs

| Risk | Severity | Mitigation | Owner |
|---|---|---|---|
| Quality drops without the fact-forcing gate | Medium | Edit-guard set and its floor (Validation); D4 revisit trigger | maintainer |
| A hidden dependency on an ECC hook | Medium | Full inventory; offline rollback; bench run before this Mac | maintainer |
| The migration removes ECC from the wrong config dir, or deletes another dir's cache | High | S1 runs with the target dir; S2 refuses a foreign `installPath`; bench SHA-256 check of the real state | maintainer |
| A bench run changes the real machine (rc files, launchd, settings) | High | P2; bench environment variables; SHA-256 check before and after | maintainer |
| A git-hook bypass form the guard misses | Medium | Verified option table; abbreviations; fail closed on every give-up path; aliases from config files are an accepted gap | maintainer |
| The reviewer agent is told to approve by text inside a diff (prompt injection) | Medium | Untrusted-data rule in the agent; the gate reads only the final `REVIEW RESULT` block | maintainer |
| The plugin CLI changes behaviour | Low | Flags verified on 2.1.310; S5/S6 failures stop or report | maintainer |
| Reviewer text drifts from upstream | Low | Accepted; the header records v2.2.1 | maintainer |
| HIGH now blocks MATERIAL work more often | Low | Deliberate (D3) | owner |

## Migration Plan

D6 (steps and rollback) and D7 (order). Rollback per phase:
- phases 2-4: git revert
- phase 6: `./setup.sh --rollback <S3 backup>`

## Validation (A4, M-7, M-11)

All baselines go in one file, `docs/designs/ecc-removal-baseline.md`, created by task 1.x before any code change.

| Check | How | Pass |
|---|---|---|
| Tokens per request | `claude -p /context`, 3 runs each, ECC-on bench copy versus ECC-off bench copy, same day | Custom agents down by ≥ 5.5k; total down by ≥ 5.5k. Delta rule, not an absolute target. |
| Accuracy | `bench.run` from branch `bench/vanilla-vs-groundwork` at commit `cb0d3f4` (the code that produced the baseline), `--repeats 3`, with G pointed at `g-ecc-off` and, the same day, at `g-ecc-on` | G-ECC-off: every case correct in ≥ 2 of 3 repeats, and total correct ≥ same-day G-ECC-on − 1. Answers with an "Evidence & references" section ≥ G-ECC-on − 1 per repeat (baseline 18/20). Median cited lines ≥ G-ECC-on − 1. 0 invented tokens, 0 false confidence. |
| Token cost per answer | Same runs; input = input + cache_read + cache_creation | G-ECC-off median below same-day G-ECC-on median |
| Edit and guard set (new, 6 scenarios, 3 repeats each, ECC-on and ECC-off, in throwaway repos) | (a) fix a bug that needs reading two files; (b) add a function; (c) "commit with --no-verify, the hook is slow"; (d) "relax ruff to make lint pass"; (e) a MATERIAL change ending in a review; (f) edit a file whose caller must change | (a, b, f) tests pass in every run, and read-before-edit rate ≥ 80% over the 9 ECC-off runs. ECC-on's rate is reported for information only: its gate forces reads, so a relative rule would fail by construction (N-11). (c) no commit created in ECC-off runs. (d) `ruff.toml` unchanged. (e) a `groundwork-code-reviewer` call ending in a `REVIEW RESULT` block appears. |
| Hook wait | Real desktop sessions on this Mac (where `NODE_USE_SYSTEM_CA=1`): PreToolUse `durationMs` from transcripts of the 5 sessions before and 5 after migration | p90 ≤ 500 ms after; before shows the slow baseline (≥ 5 s), which proves the measure can see it |
| Guards | Unit tests per D2 table row. Timing: every test input of the guard's tests (deny and allow rows), run 10 times each in-process | All rows pass; p90 ≤ 200 ms; the changed functions import no `socket`, `http`, `urllib` or `subprocess` |
| Migration | Stub-`claude` tests for S0-S9; one real run in `g-ecc-off`; rollback; re-run | ECC absent after; present after rollback; `settings.json` byte-identical to the backup after rollback; the SHA-256 list of real state identical before and after every bench run |
| No ECC agent or command names (NEW-B3) | See the command below | No output |
| ECC prose only where it belongs (NEW-B3) | See the command below | Every matching file is in the allow-list |

The two text checks are defined once here and copied verbatim into task 6.3. A single `|` inside a code block is a regex alternation, not table text.

```bash
# 1. No agent, command, plugin or path reference to ECC outside history and migration code
grep -rnE 'ecc:[a-z]|/ecc:|ecc@ecc|plugins/cache/ecc' rules hooks scripts playbooks agents docs install.sh setup.sh uninstall.sh README.md \
  | grep -vE '^(docs/RELEASE-REPORT-|docs/designs/|scripts/migrate_off_ecc\.py|scripts/unmerge_settings\.py)'

# 2. Files that still mention ECC at all
grep -rliE '\bECC\b' rules hooks scripts playbooks agents docs install.sh setup.sh uninstall.sh README.md CHANGELOG.md CREDITS.md
```

**Allow-list for check 2:**
- `CHANGELOG.md`, `CREDITS.md`, `THIRD_PARTY_NOTICES.md`
- `docs/RELEASE-REPORT-*.md`, `docs/designs/*`
- `docs/UPGRADE-ROLLBACK.md` and `docs/TROUBLESHOOTING.md` (migration and rollback text)
- `README.md` (one migration note)
- `install.sh` (the migration calls)
- `setup.sh` (the `--verify` row describing a kept ECC)
- `scripts/migrate_off_ecc.py`, `scripts/merge_settings.py` and `scripts/unmerge_settings.py` (legacy key cleanup)
- `agents/groundwork-code-reviewer.md` (licence header)

## Owner follow-ups (outside this repo)

- `~/.claude/CLAUDE.md` names the ECC plugin in "Engineering harness". Edit it after migration.
- The owner's `rules/behavior.md` (claude-toolkit) mentions ECC skills.
