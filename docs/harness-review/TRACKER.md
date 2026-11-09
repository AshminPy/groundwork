# Harness review tracker

Purpose: decide, one item at a time, what the next Groundwork keeps, changes or removes, so the result is a
simpler, structured, evidence-first harness. Started 2026-11-08.

How to use: we discuss one row at a time. Each row gets a decision (KEEP / SIMPLIFY / MERGE / REMOVE / FREEZE /
BUILD), a one-line reason with evidence, and the date. Nothing is deleted until its row says so.

## Scoring dimensions (every component is judged on these)

| Dimension | Question |
|---|---|
| Accuracy | Does it make answers and changes more correct? |
| Evidence | Can every claim and decision be traced to a source, command or file? |
| Safety | Does it prevent harmful or irreversible actions? |
| Speed | Does it add wall-clock time? |
| Cost | Does it add tokens (always-loaded context, extra calls)? |
| Simplicity | Code and rules to maintain; how easy to understand |
| Continuity | Does work survive compaction, new sessions and machines? |
| Quiet | Does it interrupt or add noise (prompts, follow-ups)? |
| Measurability | Can we prove its value with data? |

Evidence base so far: calibration run (3 cases x 1 run, directional only): plain Claude Code 3/3, 11 s, 10.6k
tokens; + ECC/OpenSpec 3/3, 18 s, 30.5k; Groundwork 2/3, 24 s, 51.6k
(`claude/baseline-benchmark:bench/results/calibration-1/report.md`). Noise audit (`claude/groundwork-3-redesign`,
`design.md:7-14`). Research report (`docs/research/HARNESS-METHODS-2026-10-28.md`). Design review
(`docs/groundwork-design-review` branch).

## Part 1. Current Groundwork inventory (42 items)

| # | Group | Item | What it does | Size / trigger | Decision | Reason / evidence | Date |
|---|---|---|---|---|---|---|---|
| 1 | Upstream | ECC plugin | Third-party agents, skills, commands | Calibration tokens 10.6k → 30.5k; listed every session | | | |
| 2 | Upstream | OpenSpec + `/opsx:*` | Spec-driven change workflow | CLI + 6 skills + 6 commands; on use | | | |
| 3 | Rules (always loaded) | `engineering-workflow.md` | Tiers, 9-step order, completion facts, approvals, subagents/teams, capability resolution, continuation template | 24 KB every turn | | | |
| 4 | Rules | `output-contract.md` | 3-layer reply format, checklist style, metadata line, reviewer format | 11 KB every turn | | | |
| 5 | Rules | `evidence-policy.md` | Evidence priority, labels, decision record, validation ladder, RCA rule | 6.9 KB every turn | | | |
| 6 | Rules | `task-routing.md` | 10-category router, ask-only-when-it-matters, five concepts, coach modifier | 5.3 KB every turn | | | |
| 7 | Rules | `architecture-quality.md` | Smallest sound design, variation points | 3.3 KB every turn | | | |
| 8 | On-demand | 10 playbooks | Per-category workflow and answer shape | 25 KB total; one per task | | | |
| 9 | On-demand | Coach mode | Architect coaching style modifier (PR #82) | 4 KB; on "coach me" | | | |
| 10 | Hook | Push guard | Blocks push to main/master and force push | 1,017 lines; every Bash call | | | |
| 11 | Hook | Review gate | Blocks "done" when an implemented OpenSpec change is unreviewed | 348 lines; Stop | | | |
| 12 | Hook | Session snapshot | Branch, dirty files, task progress, test commands at start | 635 lines; SessionStart | | | |
| 13 | Hook | Task brief | Per-branch goal and decision log across compaction | 433 lines; start/compact/stop | | | |
| 14 | Hook | Telemetry | Local turn and tool-call records | 613 lines; Stop + every tool call | | | |
| 15 | Hook | Task intake + authorization gate | Records tasks; asks before sensitive actions | 1,487 lines; every prompt + tool call | | | |
| 16 | Hook | Task ledger | Task state, verification by code fingerprint | 1,004 lines; used by #15 | | | |
| 17 | Hook | Reply check | Asks once for missing Evidence/metadata | 204 lines; prompt + Stop | | | |
| 18 | Hook | Shared helpers | Common hook code | 206 lines | | | |
| 19 | Settings | Deny rules | sudo, rm -rf / and ~, chmod 777, force push, dd, mkfs, diskutil erase | settings.json | | | |
| 20 | Settings | Env defaults | ECC GateGuard exemption, macOS Node fix, optional Agent Teams flag, profile label | settings.json | | | |
| 21 | Tool | `groundwork` CLI | Command dispatcher | 274 lines | | | |
| 22 | Tool | statusLine | Status bar with Groundwork state | 867 lines | | | |
| 23 | Tool | Health dashboard | HTML report + weekly scheduled job | 888 lines | | | |
| 24 | Tool | `groundwork usage` | Per-session plan usage | in #22/#14 | | | |
| 25 | Tool | Routines | 6 scheduled prompts (Jira EOD, news, weekly status, PR follow-up, work digest, doc drift) | 932 lines; launchd | | | |
| 26 | Tool | Copilot explain | Read-only help with tmux pane output | 679 lines | | | |
| 27 | Tool | Integrations catalog | available/configured/connected/used per integration | 591 lines | | | |
| 28 | Tool | Capability profiles | `setup.sh --configure` | 475 lines | | | |
| 29 | Tool | Update / rollback | Self-update to a release, roll back | 408 lines | | | |
| 30 | Tool | Live routing check | `check_routing.py` | 78 lines | | | |
| 31 | Tool | Legacy rules migration | One-time migration | 64 lines | | | |
| 32 | Install | `install.sh` + settings merge/unmerge | Copy files, merge settings | 222 + 520 lines | | | |
| 33 | Install | `setup.sh` | Wizard, prereqs, doctor, verify, configure | 974 lines | | | |
| 34 | Install | `uninstall.sh` | Remove Groundwork | 139 lines | | | |
| 35 | Docs | README | | 53 KB | | | |
| 36 | Docs | CHANGELOG | | 80 KB | | | |
| 37 | Docs | `docs/` | 19 files incl. 6 release reports | 2 MB with images | | | |
| 38 | Records | OpenSpec records | 10 specs, 12 active + 13 archived changes | | | | |
| 39 | Tests | Test suite | 17 files, no CI | 10.9k lines | | | |
| 40 | In progress | Groundwork 3 redesign branch | Plugin rewrite, tier routing, agents, run state | not on main | | | |
| 41 | In progress | Benchmark harness branch | V/E/G benchmark; full and focused runs not run | not on main | | | |
| 42 | In progress | Architect Coach Mac app | Voice coach (PR #82, `tools/`) | not on main | | | |

## Part 2. Harness components (target design)

Every capable harness needs a decision on each of these, even if the decision is "use the native feature".
Column "Groundwork today" maps to Part 1 numbers.

| C# | Component | What it is | Native Claude Code mechanism | Groundwork today | Decision | How it fits | Date |
|---|---|---|---|---|---|---|---|
| C1 | Instructions and rules | Always-loaded guidance: principles, conventions, must-do and must-not | `CLAUDE.md`, rules files | #3–#7 | | | |
| C2 | Router and risk tiers | Classify each request: type of work and risk level, then pick the workflow | none (prompt-only) | #6, tiers in #3 | | | |
| C3 | Workflows / playbooks | Step-by-step procedure per task type | none; skills or commands can carry them | #8, #9 | | | |
| C4 | Skills | On-demand packaged knowledge and scripts, loaded only when relevant | Skills (`SKILL.md`) | ECC skills, OpenSpec skills | | | |
| C5 | Spec and plan layer | Requirements, design and tasks before material work | plan mode; OpenSpec (external) | #2, #38 | | | |
| C6 | Tools and integrations | What the agent can call: built-in tools, MCP servers, CLIs | built-in tools, MCP | #27, #28 | | | |
| C7 | Hooks | Deterministic checks and automation at lifecycle events | Hooks (PreToolUse, Stop, SessionStart, …) | #10–#18 | | | |
| C8 | Permissions and sandbox | What may run without asking; hard denies; isolation | permission modes, allow/deny, sandbox | #19, #15 | | | |
| C9 | Subagents and delegation | Fresh-context workers for search, review, parallel work | subagents, Agent Teams (experimental) | rule text in #3 | | | |
| C10 | Loop controller | The plan → act → verify → fix cycle: stop conditions, max rounds, budgets, retries | agent loop, `/goal`, `--max-budget-usd` | rule text in #3 | | | |
| C11 | Verification gates | Tests, linters, validation ladder; proof before "done" | Stop hook can block | #5, #11, #16 | | | |
| C12 | Independent review | Fresh-context reviewer with a stated must-fix bar | subagents, `/code-review` | #11, rule text in #3 | | | |
| C13 | Evidence and citations | Labels (verified, assumption…), sources, file:line, claim checks | none | #5, #17 | | | |
| C14 | Context management | What loads when; budget; compaction; caching | compaction, rules loading, `/context` | #3–#8 sizes, #13 | | | |
| C15 | Memory and continuity | Facts and decisions that survive sessions and compaction | auto memory, `--resume`, checkpoints | #12, #13 | | | |
| C16 | Task and run state | What is in progress, done, blocked; resumable | todo list, OpenSpec `tasks.md` | #15, #16 | | | |
| C17 | Human in the loop | When to ask, approval gates, escalation | permission prompts, plan mode | #15, ask rules in #3/#6 | | | |
| C18 | Output contract | Reply shape and reporting | output styles | #4, #17 | | | |
| C19 | Security and untrusted input | Secret redaction, prompt-injection handling, untrusted content | sandbox, deny rules | #10, #19, #26 redaction | | | |
| C20 | Observability and telemetry | Tokens, cost, time, outcomes, traces | OpenTelemetry, `--output-format json` usage | #14, #22–#24 | | | |
| C21 | Evaluation and benchmark | Prove the harness beats plain Claude Code; catch regressions | none | #41, #30 | | | |
| C22 | Model and effort routing | Which model and effort for which step | per-subagent `model`, `/model`, effort | none | | | |
| C23 | Packaging, install, update | How it ships, versions, rolls back; settings profiles | plugins, marketplaces | #1, #21, #29, #32–#34, #40 | | | |
| C24 | Domain knowledge | Cloud, Terraform, Kubernetes specifics | skills, MCP docs servers | ECC skills, #9 | | | |
| C25 | Scheduled automation | Work that runs without a session | `claude -p`, routines/scheduled tasks | #25 | | | |
| C26 | Learning loop | Capture failures, propose rule changes, human approves | none | none | | | |

## Decision log

| Date | Item | Decision | Reason |
|---|---|---|---|
