# EGM review of the plan

The plan was reviewed with the Elephant-Goldfish Model before any implementation (2026-10-30). Three reviewers ran in parallel, each in a fresh context, with only the plan files and the code:

- **Zoom-out:** owner goals, scope, phasing.
- **Design critic:** platform claims checked against code.claude.com, security, failure modes.
- **Implementation readiness:** requirement-to-task coverage, formats, dependencies, reuse.

A fourth fresh-context reviewer re-audits the revised plan; its result is recorded at the end of this file.

The main author checked the key platform claims independently before accepting them: `onFailure: block`, the fields plugin agents ignore, that skills with `disable-model-invocation` can't be preloaded, and that an agent without `tools` inherits all tools.

## Must-fix findings and their resolution

| # | Finding | Resolution |
|---|---|---|
| 1 | Bash can bypass per-agent write scope | D6: post-stop `git status` diff against owned paths; log hash chain (run-state); no Bash for egm and docs |
| 2 | "Fail closed" isn't the default; a crashed hook lets the action through | D7: `"onFailure": "block"` on pre-guard and pre-dispatch; minimum Claude Code 2.1.295; tests for a missing script, timeout and invalid JSON |
| 3 | The guard matcher missed Read, Grep, Glob and MCP tools | Matcher now covers `Read\|Grep\|Glob\|mcp__.*`; profile `denyRead` for secrets |
| 4 | Stop checks can loop forever | A file-kept block counter: after 2 blocks the task is blocked and the stop allowed (context-continuity) |
| 5 | The revision check races; worktree builders lose the run folder | Lock plus atomic replace, a revision per task, run root found through `git --git-common-dir` (D8) |
| 6 | No builder for non-Terraform or non-Kubernetes work | `builder-general`; T1 runs in the main session (D10, D11) |
| 7 | No eval dashboard | New `eval-dashboard` capability and task 11.2 |
| 8 | ECC integration unspecified; ECC hooks may prompt | New `toolchain-integration` capability, ECC inventory (1.8), wrap or disable (7.9) |
| 9 | First useful release too late | Phase 0 runs alongside approval; alpha milestone after groups 2 to 5 (D17, 5.9); baseline moved to 12.1 and required only before 12.3 |
| 10 | Owner approval had no mechanism | `gw approve` and `gw reject` (agent-orchestration, 3.6) |
| 11 | YAML with only the standard library | JSON for state, TOML through `tomllib` for config (D8) |
| 12 | Undefined data formats | design.md "Data formats" |
| 13 | Agent-to-task binding undefined | D5: the task id is required at dispatch; `bindings.json` from SubagentStart; stability checked in 1.1 |
| 14 | Phase 0 check 2.5 depended on a file built later | 1.5 records a key table; 2.2 checks against it |
| 15 | Items marked unverified were already documented | Recorded as facts in the design; Phase 0 trimmed to what is really unknown |

## Should-fix and nits resolved

- Full roster per tier, with T4 including qa.
- Follow-up prompts join the active run, and T0 has a routing log.
- TDD red/green evidence.
- `gw doctor`.
- A project memory file (`gw remember`).
- A closed list of decision kinds with a short form.
- Allow-listed export that refuses on a match.
- Testable scenarios (rule floor, conflicting rules, negations, "not listed or loaded").
- Agent versions kept in `components.json`.
- `SendMessage` model guard.
- VS Code status-line fallback.
- Every agent must declare `tools`.
- Routing only at stage boundaries.
- Reuse table.
- Hook-replay harness.
- Split large tasks.
- **[live]**/**[paid]** markers.
- Unambiguous task references.
- Inter-session messages dropped.
- Docs agent gets Glob.
- Conversation residue removed.
- Owner open questions answered in the design.
- The 2.0 "heuristic production detection" note addressed in D9.

## Not adopted

- **Skip final-reviewer on T2 when checks pass.** Not adopted. The owner asked for an independent final review, and T2 has no egm step.
- **A 2.5.x "quiet" patch now.** Left to the owner as a separate change.

## Re-audit (fourth reviewer, fresh context)

The re-audit marked rows 2–7, 10, 11 and 13–15 resolved. Rows 1, 8, 9 and 12 were only partly resolved. It confirmed three platform facts against the docs: `onFailure`, the fields plugin agents ignore, and mods `agent.spawn` / `AbovePrompt` / `$.store`. It also found new issues, all now fixed:

| Finding | Fix |
|---|---|
| The log chain couldn't detect an outside edit to `tasks.json` | Each log entry stores the state hash of `run.json` and `tasks.json` (D8, run-state, 3.3) |
| The scope post-check ran in a stop hook that fails open | Scope-check record; `gw task done` requires it (D6, safety-guards, 7.6) |
| `git status` in a shared checkout blames the wrong agent | Snapshot at agent-start, diff at stop; parallel builders use worktrees; blind spots listed in Risks (D6, 7.4, 7.6) |
| egm and docs couldn't call `gw` without Bash | Handoff file written with Write and ingested by agent-stop (D7a, context-continuity, 7.5) |
| The task-id rule would block explorer and non-Groundwork agents | Rule limited to Groundwork task agents; others run read-only (D5, agent-orchestration, 7.3) |
| The baseline dependency was stated inconsistently | Needed before 12.3 (design Migration Plan) |
| The alpha had no verify gate | Main-session stop-verify moved to 5.6; pre-dispatch registered only in 7.3 |
| Formats were still undefined | `bindings.json`, `scope/`, `blocks.json`, `floor.json`, `routing.jsonl`, `components.json`, `evals/criteria.toml`, and the packet are now defined inline |
| Review file named `review.md` in one place and `review.json` in another | `review.json` everywhere |
| Some requirements had no task | T4 dry-run guard 7.11; decision promotion 6.7; post-record and session-end 5.7 |
| T4 approval contradicted the roster | Writes before approval limited to the change folder and test paths |
| Model correction undid the planner's raise | Correct to the declared model or the recorded raise (D12, 9.3) |
| Doctor and domain checks were ordered before their dependencies | Doctor checks added in each group; builder domain checks moved to 8.7 |
| The matcher over-matched (`TodoWrite`) | Anchored matcher (4.6) |
| Small gaps | Profile command skill (5.8), T0 explorer wording, `format` field in the log entry |
