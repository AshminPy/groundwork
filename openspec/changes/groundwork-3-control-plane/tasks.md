# Tasks

Each group lands its own tests and docs. Python means the standard library only, with tests run by `python3 -m pytest`. No group starts paid model runs without the owner's approval.

## 1. Baseline and approval gate

- [ ] 1.1 Get the owner's approval for this plan and for the 2.5.0 focused pilot (#78, task 7.5); verify the approval is recorded on the PR
- [ ] 1.2 Run the focused pilot (30 agent runs plus 6 canary calls on Linux) and verify `bench/results/focused-1/report.md` exists with per-arm results and denials reported separately

## 2. Phase 0 platform checks

- [ ] 2.1 Load a throwaway plugin agent and log `agent_type` from a PreToolUse hook; verify the exact value is recorded in design.md D5
- [ ] 2.2 Test whether a skill with `disable-model-invocation: true` can be preloaded through an agent's `skills:` list; verify the result is recorded in design.md D8
- [ ] 2.3 Test whether a plugin agent honours `hooks` and `mcpServers` in its frontmatter; verify the result is recorded in design.md
- [ ] 2.4 Load a minimal mod in the terminal, in a cloud session and with `-p`; verify which surfaces run it, recorded in design.md D2
- [ ] 2.5 Check every profile key (auto mode, sandbox, deny rules, model, env, statusLine) against the settings reference; verify `profile/work.json` uses only documented keys
- [ ] 2.6 Measure prompt-cache reuse with and without a model switch within a session on a fixed task (needs approval if paid); verify the numbers are recorded in design.md D7

## 3. Plugin skeleton and profile

- [ ] 3.1 Create the plugin tree from the design (manifest with `version` 3.0.0-alpha.1 and `userConfig` for `vault_path` and `profile`, no `bin/`); verify `claude plugin validate --strict` passes
- [ ] 3.2 Write `profile/work.json` and `profile/personal.json` from the results of task 2.5; verify each holds only keys that task confirmed
- [ ] 3.3 Implement `gw profile diff | apply | revert` with backup and an approval step; verify by tests that revert restores the file byte for byte and that apply refuses without approval
- [ ] 3.4 Document install, profile apply and rollback in the plugin README; verify the documented commands run on a clean config directory

## 4. Run state

- [ ] 4.1 Implement `gw run new | status` and the run folder layout; verify by tests that a new run holds `run.yaml` with id, tier and stage, and that `.groundwork/` is git-ignored
- [ ] 4.2 Implement `gw task claim | done | block | list` with single ownership; verify by tests that a second claim is refused and names the owner
- [ ] 4.3 Add evidence hashing and stale detection to `gw task done`; verify by tests that done fails without evidence and fails after a covered file changes
- [ ] 4.4 Add revision checks to every state write; verify by tests that a write based on an old revision changes nothing
- [ ] 4.5 Add the append-only run log; verify by tests that three status changes give three ordered entries and no rewrite
- [ ] 4.6 Implement `gw run report` and the status-line output from files; verify by a fixture test that the counts and evidence paths match `tasks.yaml`

## 5. Decisions and context continuity

- [ ] 5.1 Implement `gw decide` with the schema and the refusal rules; verify by tests that a record without a reason, or without evidence and not owner-approved, is refused
- [ ] 5.2 Implement `gw why` for file, task and decision; verify by a fixture test that the chain from commit trailer to evidence is printed
- [ ] 5.3 Add the handoff template and validator; verify by tests that a missing section, a missing evidence path or an unknown decision id fails
- [ ] 5.4 Implement `gw brief` and the packet builder; verify by tests that the packet holds ids and paths only, and the brief holds goal, tier, stage, open tasks and recent decisions
- [ ] 5.5 Implement `gw handoff export | load` with the secret scan and redaction, and no evidence files; verify by tests that a planted token is redacted, the export fails if the scan cannot run, and load rebuilds the same task status
- [ ] 5.6 Keep work and personal run roots separate; verify by tests that a personal-profile listing shows no work runs
- [ ] 5.7 Document the run folder, decision schema and handoff format in the plugin docs; verify the documented examples pass the validators

## 6. Safety hooks

- [ ] 6.1 Implement `pre-guard` with the hard deny list and fail-closed behaviour; verify by tests on recorded hook inputs that `terraform apply`, a secret-file read and a force-push are denied, and that a script error denies
- [ ] 6.2 Add per-agent write scope using `agent_type` (from 2.1) and the task's owned paths; verify by tests that final-reviewer cannot edit code and a builder cannot write another task's paths
- [ ] 6.3 Deny direct edits to `run.yaml` and `tasks.yaml`; verify by a test that an Edit on `tasks.yaml` is denied with the `gw task` hint
- [ ] 6.4 Implement `session-start`, `pre-compact`, `post-record`, `post-failure`, `denied-log` and `session-end`; verify by tests that they never print an ask decision, record hooks exit 0 on bad input, and session-start installs nothing
- [ ] 6.5 Add a test that scans every hook's possible outputs for an ask decision; verify it fails if any hook can return ask
- [ ] 6.6 Port the gw-bench safety canaries to run against the plugin; verify that all probes pass in an isolated config directory

## 7. Agents and orchestration

- [ ] 7.1 Write the agent files for explorer, investigator, planner, qa, egm, final-reviewer and docs, with model, effort, tools, skills, memory and maxTurns; verify `claude plugin validate` passes and no agent lists the `Agent` tool
- [ ] 7.2 Write the internal skills (route, evidence, planning, test-design, review-rubric, git-flow, docs-template) with one-line descriptions and component versions in `metadata`; verify by a test that each has `user-invocable: false` and a `gw-version`
- [ ] 7.3 Implement `prompt-route` with the deterministic tier rules and the decision record; verify by table tests that production and destructive phrases give T4, and that ties go up
- [ ] 7.4 Implement `pre-dispatch` stage gates; verify by tests that a builder before egm approval on T3, a builder before owner approval on T4, and docs with open tasks are each denied
- [ ] 7.5 Implement `agent-start` (packet) and `agent-stop` (stop checks and handoff check, 2 attempts, then blocked); verify by tests for each agent's stop check
- [ ] 7.6 Implement `stop-verify`; verify by a test that the main session cannot finish with an open task lacking evidence
- [ ] 7.7 Implement the 2-round loop limits and tier-up; verify by tests that a third round is not started and tier-up re-routes with a new decision
- [ ] 7.8 Write the command skills (run, status, handoff, profile, domain) calling `${CLAUDE_PLUGIN_ROOT}/scripts/gw`; verify each command runs on a fixture project

## 8. Domain packs, wave 1

- [ ] 8.1 Implement `gw domain new | build` and the builder template; verify by tests that a pack without evals is refused and a rebuild changes only that builder
- [ ] 8.2 Write the terraform pack (tf-core, gcp, aws, spacelift skills; `fmt -check` and `validate` checks; 3 to 5 eval cases); verify the pack builds and its checks run on a fixture module
- [ ] 8.3 Write the kubernetes pack (k8s-core, gke, eks, helm skills; `helm lint`; 3 to 5 eval cases); verify the pack builds and `helm lint` runs on a fixture chart
- [ ] 8.4 Route tasks to builders by file patterns, and block tasks that match no domain; verify by tests that an unmatched path is blocked with the reason
- [ ] 8.5 Report unapproved third-party checks (tflint, kubeconform) as skipped; verify by a test that nothing is installed and the skip is reported

## 9. Console mod and model routing

- [ ] 9.1 Implement the status band and run-board pane from the run files; verify with `claude plugin test` that the band shows tier, stage and counts, and leaves out unknown values
- [ ] 9.2 Implement alerts for stage change, blocked task, denial and approval needed; verify with `claude plugin test`
- [ ] 9.3 Implement `agent.spawn` model enforcement from the agent and domain definitions; verify with `claude plugin test` that a wrong model is corrected
- [ ] 9.4 Implement `turn.step` model and effort routing behind a setting that is off by default; verify with `claude plugin test` that T1 lowers the model only when routing is on
- [ ] 9.5 Implement the `$.store` run index with fallback to the run folders; verify that session-start finds open runs with the mod disabled
- [ ] 9.6 Verify that with the mod disabled, every safety test in group 6 still passes

## 10. MCP management

- [ ] 10.1 Define the `mcp/catalog.yaml` schema (name, scope, auth, allowed agents) with an empty work catalog; verify the schema validator rejects an entry missing a field
- [ ] 10.2 Implement `gw mcp list | check | enable | disable` and `/groundwork:mcp`, limited to catalogued servers; verify by tests that an unlisted server is refused and a failing server shows its error
- [ ] 10.3 Deny MCP tools that an agent's catalog entry doesn't allow; verify by a test with a recorded hook input
- [ ] 10.4 Verify by a test that no Groundwork file contains a credential after configuring a server through sensitive `userConfig`

## 11. Release gating and learning

- [ ] 11.1 Add the release check script (plugin validate, unit tests, canaries, component versions, changelog entry); verify it fails when a component changes without a version bump
- [ ] 11.2 Connect `gw eval run | compare` to gw-bench with confidence intervals and a paid-run approval step; verify that compare refuses a release below the previous lower bound on a fixture result
- [ ] 11.3 Implement `gw learn propose` and `/groundwork:learn` to write a candidate OpenSpec change only; verify by a test that no plugin file changes
- [ ] 11.4 Document versioning, release and rollback; verify that the rollback steps restore the previous tag and profile on a fixture

## 12. Integration checks

- [ ] 12.1 Run fixture end-to-end runs for T0, T1, T2, T3 and T4 with a stub model; verify each run starts only its tier's agents and produces a valid report
- [ ] 12.2 Run the Groundwork 3 focused eval against the 2.5.0 baseline (needs owner approval for paid runs); verify the comparison report states the accuracy, safety and cost results against the pre-registered criteria

## Workflow follow-up

- A separate cutover change retires the 2.x components and specs after 12.2 meets or beats the baseline.
- Ansible and Elastic packs are separate changes after wave 1 passes its eval.
