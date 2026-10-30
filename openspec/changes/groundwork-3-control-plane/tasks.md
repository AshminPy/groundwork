# Tasks

Rules for every group:
- Python 3.11, standard library only; tests run with `python3 -m pytest`.
- Formats are those in design.md "Data formats".
- Each group lands its own tests and docs.
- Tasks marked **[live]** start a real Claude session, and tasks marked **[paid]** call a paid model. Both need the owner's approval for that run, with the run count stated.
- "Reuse" names existing code to port, not rewrite.

## 1. Phase 0 platform checks (can run alongside plan approval)

- [ ] 1.1 **[live]** Start a throwaway plugin agent twice and log `agent_id` and `agent_type` from SubagentStart, PreToolUse and SubagentStop; verify the plugin-scoped `agent_type` value, and whether `agent_id` is stable, are recorded in design.md D5 (about 2 sessions)
- [ ] 1.2 **[live]** Check that SubagentStart can add context, and how SubagentStop blocking behaves (re-prompt, continuation cap, `stop_hook_active`); verify the results are recorded in design.md D7 (about 2 sessions)
- [ ] 1.3 **[live]** Load a minimal mod in the terminal, in a cloud session and with `-p`; verify which surfaces run it, recorded in design.md D2 (about 3 sessions)
- [ ] 1.4 Confirm `claude plugin validate --strict` and `claude plugin test` exist and behave as documented on 2.1.314; verify the command output is recorded in design.md "Testing strategy"
- [ ] 1.5 Check every intended profile key (permission mode, sandbox and `denyRead`, deny rules, model, env, statusLine) against the settings reference; verify a confirmed-key table is added to design.md D1
- [ ] 1.6 **[live]** Check the hook working directory and `CLAUDE_PROJECT_DIR` in an `isolation: worktree` subagent, and that `git rev-parse --git-common-dir` finds the main checkout; verify the result is recorded in design.md D8 (about 1 session)
- [ ] 1.7 **[live]** Check that a write to a folder outside the working directory, standing in for the vault, works in auto mode with the sandbox without a prompt; verify the result and any needed `allowWrite` entry are recorded in design.md D1 (about 1 session)
- [ ] 1.8 Inventory the installed ECC v2.2.1 agents, skills, commands and hooks with a role for each (reuse, wrap or disable), and flag any hook that can return ask; verify `toolchain/ecc-inventory.toml` lists every component found on disk

## 2. Plugin skeleton, profile and doctor

- [ ] 2.1 Create the plugin tree: manifest version `3.0.0-alpha.1`, `userConfig` for `vault_path` and `profile`, no `bin/`, an empty `components.json`; verify `claude plugin validate --strict` passes
- [ ] 2.2 Write `profile/work.json` and `profile/personal.json` using only the keys confirmed in 1.5 (auto mode, sandbox with secret `denyRead`, deny rules, `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, statusLine); verify a test checks every key against the table in D1
- [ ] 2.3 Implement `gw profile diff | apply | revert` with a backup and an approval step (reuse `scripts/merge_settings.py` and `unmerge_settings.py`); verify by tests that apply writes nothing without approval and that revert restores the file byte for byte
- [ ] 2.4 Implement `gw doctor` as a report-only framework with its first checks (plugin version, profile drift, pinned OpenSpec CLI version) and a fix command for each problem; later groups add their own checks (3.3, 4.6, 10.2); verify by fixture tests that each drift case prints its fix and changes no file
- [ ] 2.5 Document install, profile apply, doctor and rollback in the plugin README; verify the documented commands run on a clean config directory

## 3. Run state core

- [ ] 3.1 Implement the run root lookup through `git rev-parse --git-common-dir` and `gw run new | status` with the run.json format and the `.gitignore` entry; verify by tests that a worktree and the main checkout resolve to the same run folder
- [ ] 3.2 Implement the file lock, atomic replace and per-task revisions; verify by a multi-process test that two writers on different tasks both succeed, and that a stale write to the same task is refused
- [ ] 3.3 Implement the hash-chained `log.jsonl` with the state hash of `run.json` and `tasks.json` in each entry, the check on every read, and a doctor check for it; verify by tests that an outside edit to `tasks.json` is detected and stops `gw`
- [ ] 3.4 Implement `gw task claim | done | block | list` with the status machine and one owner per task; verify by tests that a second claim names the owner and that a blocked task can reopen
- [ ] 3.5 Implement evidence records with file hashes, and the stale check in `gw task done`; verify by tests that done fails without evidence and fails after a covered file changes
- [ ] 3.6 Implement `gw approve | reject` writing owner decisions and moving the stage; verify by tests that reject stops the run and approve opens the build stage
- [ ] 3.7 Implement `gw run report` and the status-line output (reuse `scripts/groundwork_statusline.py`), with separate counts for auto-mode denials, guard denials and failures; verify by a fixture test that the counts and evidence paths match the run files
- [ ] 3.8 Implement format-version checks for every state file; verify by a test that a newer format version stops `gw` with both versions named

## 4. Safety hooks and replay harness

- [ ] 4.1 Build the hook-replay harness: feed recorded event JSON sequences to the hook scripts and `gw`, and assert on outputs; verify it replays a recorded PreToolUse deny correctly
- [ ] 4.2 Implement pre-guard hard denies: `terraform apply`/`destroy` including `-auto-approve`, Kubernetes deletes in production contexts, force-push, protected paths (reuse the `block_protected_push.py` parsing and the `groundwork_task_gate.py` `split_segments`); verify by replay tests for each command and for `bash -c` and `;` wrapping
- [ ] 4.3 Add secret-path denies for Read, Grep, Glob and Bash reads (reuse the task-gate secret tables); verify by replay tests that a credentials-file grep is denied
- [ ] 4.4 Add action-time production detection (kube context, terraform workspace, `prod_globs` from `project.toml`) that denies and raises the tier; verify by replay tests with a prod context on a T2 run
- [ ] 4.5 Deny direct edits to `run.json`/`tasks.json`, and `git commit` without a `Task:` trailer under an active run; verify by replay tests
- [ ] 4.6 Register pre-guard with `"onFailure": "block"` and the anchored matcher `^(Bash|Edit|Write|NotebookEdit|Read|Grep|Glob)$|^mcp__.*`, and add a doctor check for hook registration; verify by tests that a missing script, a timeout and invalid JSON each block, and that `TodoWrite` doesn't match (live check of one case is **[live]**, 1 session)
- [ ] 4.7 Add a test that runs every hook against every recorded input and fails if any output is an ask decision
- [ ] 4.8 Implement denied-log and post-failure as fail-open recorders (reuse the `groundwork_telemetry.py` pattern); verify by tests that bad input exits 0 and is logged

## 5. Alpha: routing, T0/T1, memory and telemetry

- [ ] 5.1 Write `rules/tiers.toml` and implement prompt-route (minimum tier, matched rules, join the active run unless `/groundwork:run`), plus the floor check in `gw run new` (reuse `tests/routing_scenarios.json`); verify by table tests including negations and a follow-up "yes, continue"
- [ ] 5.2 Implement T0 logging to `sessions/<id>/routing.jsonl`, and the T1 light run (run.json plus evidence, no claim or handoff); verify by replay tests that T1 starts no subagent and still requires evidence before done
- [ ] 5.3 Implement session-start (resume list from run folders, brief, memory file; installs nothing) and pre-compact (brief, never blocks) (reuse `hooks/groundwork_brief.py`); verify by replay tests for startup and compact
- [ ] 5.4 Implement `gw remember` and `.groundwork/memory.md` per profile; verify by a test that the brief includes it and that the other profile's file is not loaded
- [ ] 5.5 Implement telemetry records with model, effort, component versions, outcome and denial counts, stored per profile, with paths hashed; verify by tests that a planted token in a command never reaches telemetry
- [ ] 5.6 Implement stop-verify for the main session (T1: no "done" while the run's task lacks fresh evidence and a passing scope check) with the block counter in `blocks.json`; verify by replay tests including a third block that is allowed
- [ ] 5.7 Implement post-record (evidence capture for test, lint and plan commands, telemetry tool counts) and session-end (close telemetry, list memory candidates) as fail-open hooks; verify by replay tests that evidence records appear and bad input exits 0
- [ ] 5.8 Write the command skills run, status, approve, doctor and profile that call `${CLAUDE_PLUGIN_ROOT}/scripts/gw`; verify each runs on a fixture project
- [ ] 5.9 **[live]** Alpha check: the owner uses T0/T1 with the profile in auto mode for one working day; verify the report shows zero permission prompts from Groundwork hooks, and record the owner's feedback in design.md

## 6. Decisions and context continuity

- [ ] 6.1 Implement `gw decide` (closed kind list, short form, refusals for no reason or missing evidence path, warning on a same-topic decision that isn't superseded); verify by tests for each case
- [ ] 6.2 Implement `gw why` for file, task, decision and run, using commit trailers; verify by a fixture repo test that the full chain prints
- [ ] 6.3 Add the handoff template, `gw handoff write`, and the validator (six headings, evidence paths exist, decision ids exist); verify by tests for each failure
- [ ] 6.4 Implement the packet builder (ids and paths only); verify by a test that no file contents appear in the packet
- [ ] 6.5 Implement `gw handoff export` with allow-listed fields and refusal on a pattern or entropy match; verify by tests that a planted token refuses the export and that evidence files are never included
- [ ] 6.6 Implement `gw handoff load`; verify by a test that export then load on a fresh run root gives the same task statuses and decisions
- [ ] 6.7 Implement `gw run close`, which writes the live decisions into the change's OpenSpec `design.md` under "Run decisions", with owner decisions listed separately; verify by a fixture test
- [ ] 6.8 Document the run folder, decision schema and handoff format; verify the documented examples pass the validators

## 7. Agents and orchestration

- [ ] 7.1 Write the internal skills (route, evidence, planning, test-design, review-rubric, git-flow, docs-template with a decision-log section), with one-line descriptions, `user-invocable: false` and `metadata.gw-version`; verify by a frontmatter test
- [ ] 7.2 Write the agent files (explorer, investigator, planner, qa, egm, final-reviewer, docs), each declaring `tools` without `Agent`, plus their entries in `components.json`; verify `claude plugin validate --strict` passes, and a test fails any agent without `tools`
- [ ] 7.3 Implement pre-dispatch, registered with `"onFailure": "block"`: a run and task id are required for Groundwork task agents, explorer and non-Groundwork subagents are allowed only as read-only, plus the stage gates (egm approval for T3/T4 builders, owner approval for T4, docs after all tasks are closed) and the tier roster; verify by replay tests for each gate, and that a crash blocks
- [ ] 7.4 Implement agent-start: the binding in `bindings.json`, the working-tree snapshot, and the packet; verify by replay tests, and that pre-guard denies writes by an agent with no binding
- [ ] 7.5 Implement agent-stop part 1: read and validate the handoff file, record its short-form decisions through `gw`, and the block counter (2 blocks, then the task is blocked and the stop allowed); verify by replay tests including egm and docs, which have no Bash, and a third failure
- [ ] 7.6 Implement agent-stop part 2: diff against the start snapshot, write the scope-check record, and make `gw task done` require it; add per-agent stop checks (planner: `openspec validate --strict`; qa: red evidence for each criterion; builders: green evidence; reviewers: verdict or review file); verify by replay tests for each agent, for a pre-dirty file, and for a missing scope record
- [ ] 7.7 Extend stop-verify to multi-agent runs (no "done" while any task is open without evidence); verify by replay tests
- [ ] 7.8 Implement the 2-round loop limits and tier-up (tier never lowered); verify by tests that round 3 isn't started and that tier-up records a decision
- [ ] 7.9 Wrap or disable ECC components per `toolchain/ecc-inventory.toml`; verify by a replay test that no enabled ECC hook can ask
- [ ] 7.10 Write the handoff and domain command skills; verify each runs on a fixture project
- [ ] 7.11 Add the T4 guards: before `gw approve`, writes only in the change folder and test paths; after approval, a mutating command on a task needs dry-run evidence; verify by replay tests

## 8. Domain packs, wave 1

- [ ] 8.1 Implement `gw domain new | build` and the builder template, with deterministic output; verify by tests that running build twice gives identical files, and that a dummy domain routes with no other tracked file changed
- [ ] 8.2 Write `builder-general` (sonnet, project `test_command` check); verify a Python fixture task routes to it and runs the test command
- [ ] 8.3 Write the terraform pack (tf-core, gcp, aws and spacelift skills; `fmt -check` and `validate`; 3 to 5 eval cases); verify it builds and its checks run on a fixture module
- [ ] 8.4 Write the kubernetes pack (k8s-core, gke, eks and helm skills; `helm lint`; 3 to 5 eval cases); verify it builds and `helm lint` runs on a fixture chart
- [ ] 8.5 Implement routing by file pattern: an uninstalled pack's patterns block, and anything else goes to builder-general; verify by tests
- [ ] 8.6 Report unapproved third-party checks as skipped; verify by a test that nothing is installed
- [ ] 8.7 Add the builder stop check that each pack's declared checks ran and passed, with evidence, before done; verify by replay tests for builder-terraform and builder-kubernetes

## 9. Console mod and model routing

- [ ] 9.1 Implement the status band and run-board pane from the run files, with no guessed values; verify with `claude plugin test`
- [ ] 9.2 Implement alerts (stage change, blocked task, denial, approval needed); verify with `claude plugin test`
- [ ] 9.3 Implement model correction in `agent.spawn` and in `tool.call` on `SendMessage`, to the declared model or a recorded per-task raise; verify with `claude plugin test` that a raise is kept and a wrong model is corrected
- [ ] 9.4 Implement stage-boundary routing in `turn.step`, off by default; verify with `claude plugin test` that the model changes only at a stage change when routing is on
- [ ] 9.5 Implement the `$.store` run index with fallback to the run folders; verify that session-start lists open runs with the mod disabled
- [ ] 9.6 Verify that all group 4 and group 7 replay tests pass with the mod disabled

## 10. MCP management

- [ ] 10.1 Define the `mcp/catalog.toml` schema with an empty work catalog; verify the validator rejects an entry with a field missing
- [ ] 10.2 Implement `gw mcp list | check | enable | disable` and `/groundwork:mcp`, limited to the catalog, plus a doctor check for the catalog; verify by tests that an unlisted server is refused, and a failing server shows its error
- [ ] 10.3 Add per-agent MCP denies to pre-guard; verify by a replay test
- [ ] 10.4 Verify by a test that enabling Groundwork adds no MCP server, and that no Groundwork file contains a credential after configuring a sensitive `userConfig`

## 11. Eval, dashboard, release and learning

- [ ] 11.1 Connect `gw eval run | compare` to gw-bench (reuse `bench/stats.py` `bootstrap_ci` and `compare`) with an approval step showing the run count, plus the `/groundwork:eval` skill; verify by a fixture test that compare refuses a result below the previous lower bound
- [ ] 11.2 Implement `gw dashboard` as a self-contained local HTML page, with sources and record counts on every figure and "not enough data" marking below `min_records` from `evals/criteria.toml`; verify by a test that it builds offline and contains no canary secrets
- [ ] 11.3 Implement the release check (validate, unit and replay tests, canaries, `tools` declared, version bumps against `components.json`, changelog, model downgrades need eval evidence, every installed ECC component has a role in the inventory); verify by tests for each failure
- [ ] 11.4 Port the gw-bench safety canaries (reuse `bench/canary.py`) **[live]**; verify that all probes pass in an isolated config directory (about 15 probe calls)
- [ ] 11.5 Implement `gw learn propose` and `/groundwork:learn`, writing a candidate OpenSpec change only; verify by a test that no plugin file changes
- [ ] 11.6 Document versioning, release and rollback; verify that the rollback steps restore the previous tag and profile on a fixture

## 12. Baseline and integration

- [ ] 12.1 **[paid]** Run the 2.5.0 focused pilot (gw-bench #78 task 7.5: 30 agent runs plus 6 canary calls) after the owner approves; verify `bench/results/focused-1/report.md` exists with per-arm results and denials reported separately
- [ ] 12.2 Run hook-replay end-to-end sequences for T0 to T4; verify each run starts only its tier's agents, passes its gates, and produces a valid report
- [ ] 12.3 **[paid]** Run the Groundwork 3 focused eval against the baseline from 12.1, after owner approval; verify the comparison report states accuracy, safety and cost against the pre-registered criteria

## Workflow follow-up

- A cutover change retires the 2.x components and specs after 12.3 meets or beats the baseline.
- The Ansible and Elastic packs are separate changes after wave 1 passes its eval.
- An optional 2.5.x "quiet" patch is a separate change if the owner wants it.
