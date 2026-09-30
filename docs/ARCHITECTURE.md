# Architecture

## Responsibility split

```
OpenSpec   → WHAT / WHY. Delta specs with acceptance criteria as scenarios,
             a design decision record, a task checklist. Per-repo, file-based
             (openspec/ directory + .claude/commands/opsx + .claude/skills/openspec-*).
             No plugin, no hooks — nothing to conflict with ECC by construction.

ECC        → HOW. Dozens of agents (planner, code-explorer, tdd-guide, code-reviewer,
             language-specific reviewers, security-reviewer, …) and hundreds of
             skills and command shims — installed pinned to a tested ref (2.1;
             see "Upstream versions" below), so the exact agent/skill count only
             moves when Groundwork itself re-pins it, not on every fresh install;
             `claude plugin details ecc@ecc` shows the current one. Installed
             once, user-scoped, as a single Claude Code plugin. Its own hooks:
             GateGuard (investigate-before-edit, destructive-Bash fact gate),
             block-no-verify, session persistence, pre-compact save, continuous
             learning.

Claude Code → the runtime. Subagents (Agent tool), experimental Agent Teams
             (named Agent calls when CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1),
             SendMessage, permissions, hooks, CLAUDE.md/rules loading, auto memory.

Groundwork → the governance layer. Rule files loaded into every session's
             context (five — engineering-workflow, architecture-quality,
             evidence-policy, task-routing, output-contract; unchanged count
             since 1.5.1); hooks that enforce or inject what the rules can
             only ask for (four — push guard, review gate, session snapshot,
             telemetry; also unchanged in count since 1.5.1).
```

Groundwork does not replace any upstream project's job. It exists because, tested plainly, neither ECC nor OpenSpec on its own reliably makes an agent plan, design for change, test against the real runtime, review, and honestly report completion for a request that doesn't spell every step out. See [VALIDATION.md](VALIDATION.md) for the actual tests that established this.

**Upstream versions, verified 2026-09-28**: ECC installs via `claude plugin marketplace add affaan-m/ECC#$ECC_REF` + `claude plugin install ecc@ecc` (`install.sh`) — a `git clone` of ECC's GitHub repository through Claude Code's own plugin mechanism, **not npm**. Through Groundwork 2.0, this floated ECC's `main` branch unpinned: each fresh install or `claude plugin update ecc@ecc` resolved to whatever commit was HEAD on `main` at that moment, which at 2.0's verification time resolved to `2.2.2` (68 agents, 386 skills per `claude plugin details ecc@ecc`). **As of Groundwork 2.1, ECC installs pinned to a specific, previously-tested ref** (`v2.2.1` by default; override per-machine with `GROUNDWORK_ECC_REF`) — see the `dependency-pinning` OpenSpec capability and `docs/VALIDATION.md`'s 2.1.0 entry for the live-verification evidence. A published npm package `ecc-universal@2.2.1` (286 skills) also exists, but Groundwork does not install it or depend on it in any way — an earlier draft of this document conflated the two; see `openspec/changes/groundwork-2-enterprise-sre/design.md` §A.6 for that correction and evidence. OpenSpec, by contrast, genuinely installs from npm (`npm install -g @fission-ai/openspec@latest`) and was `1.13.2` as of the same date (Groundwork's own compatibility testing was last done against `1.12.0`); `openspec list --json`/`openspec status --all --json`, which Groundwork's continuation design depends on, are confirmed present and current through `1.13.2`. `setup.sh --verify`/`--doctor` reports the installed OpenSpec version next to the version last verified here, and the installed ECC plugin version against the `#ref` pin (no live network call in either case, so drift is visible without adding a network dependency to every install run).

## The three rules

| File | Owns |
|---|---|
| `rules/engineering-workflow.md` | Tier classification (TRIVIAL / STANDARD / MATERIAL); the execution order UNDERSTAND → DESIGN → IMPLEMENT → TEST → INDEPENDENT REVIEW → FIX MUST FIX → VERIFY → RUNTIME VALIDATE → REPORT; the state table for existing projects; the completion status block; the six owner-decision triggers (autonomy); §6 execution model (main session / subagents / Agent Teams); §7 continuation procedure |
| `rules/architecture-quality.md` | The governing design principle; quality dimensions as decision criteria; the pre-MATERIAL questions; the variation-point rule; no abstraction without a reason |
| `rules/evidence-policy.md` | Evidence priority; VERIFIED / UNVERIFIED / ASSUMPTION / INFERENCE / CONFLICTING EVIDENCE / UNKNOWN / RUNTIME VALIDATION REQUIRED (extended 2.0 — see CHANGELOG); the six-field DECISION record; source rules; the validation ladder; the completion-evidence table; the RCA rule (now requires UNKNOWN/CONFLICTING EVIDENCE rather than a softened guess when the chain doesn't support a cause); repository-wins-over-memory |

Every line in these files is paid in every session (Claude Code loads `~/.claude/rules/**/*.md` at launch), so they are written as short imperative lines, and anything a hook can enforce is a hook instead.

## Task routing (additive layer, 1.2.0)

`rules/task-routing.md` is a fourth always-loaded rule (~45 lines). It classifies each substantive request into one of ten categories, applies the material-ambiguity test, and tells Claude to read exactly one playbook from `~/.claude/groundwork/playbooks/` — a directory deliberately outside `~/.claude/rules/`, so Claude Code never auto-loads playbooks and each task pays for one ~40–60-line file only. The engineering categories still run inside the request lifecycle below (tiers, OpenSpec, review gate, completion block); the router only decides which workflow shape and answer shape apply. `rules/output-contract.md` is the fifth always-loaded rule (~25 lines): the three-layer answer shape every playbook inherits — plain main response, `Technical details`, `Evidence & references` — with the omit-empty, honest-validation and no-debug-lines rules stated once. On any conflict the pre-existing rule wins. Routing and output shape are advisory (rule text); it is validated structurally by `tests/test_playbooks.py` and behaviourally by `scripts/check_routing.py`.

## Harness metadata and telemetry (1.3.x)

`output-contract.md` asks every playbook-driven response to end with a four-line `Harness metadata` block. `hooks/groundwork_telemetry.py` (Stop) writes one JSON line per such response to `~/.claude/groundwork/telemetry/events.jsonl` (0600). Record schema 2 keeps two objects apart: `observed` — what the hook determined itself from the current turn of the transcript and the environment (profile from `GROUNDWORK_PROFILE`, tool names, MCP servers, Agent calls and their types, count of distinct edited files, test-shaped / deploy-shaped commands, harness version) — and `declared` — what the model stated (playbook, execution mode, agent count/roles, evidence types, validation, environment, and the outcome read from the response's Status/Result sentence with precedence failed > blocked > partial > complete, `unknown` when no status language is present). Reports must not present declared fields as verified. The transcript is read from its tail (cost follows the current turn); free text is kept only as short labels. A turn is recorded when the block is present or at least one tool ran (`declared.block_present` says which); a conversational reply with no tool use produces nothing. The hook never blocks, prints or raises. Uninstall keeps the records.

## Onboarding wrapper (1.5.x)

`setup.sh` adds nothing to the installation logic. It first checks prerequisites per OS — Claude Code must already be present (never installed by the script); missing git, Node 20.19+/npm or Python 3.10+ are installed with the official packages (Homebrew on macOS, apt/dnf/apk on Linux) only after the user agrees or passes `--install-prereqs`, and the check is repeated afterwards. It then backs up the whole config dir (APFS clonefile when available), asks three questions, calls `install.sh`, `scripts/merge_settings.py --profile`, `groundwork_report.py schedule` and `generate`, then verifies read-only. `--rollback` never deletes: the current dir is renamed to `<dir>-groundwork-disabled-<ts>`, then the newest unambiguous backup (same `source=` in `BACKUP-INFO.txt`) is copied back. `--uninstall` runs `uninstall.sh`.

## Health dashboard (1.4.0)

`scripts/groundwork_report.py` (installed to `~/.claude/groundwork/bin/`) reads at most the last 64 MB of `events.jsonl`, normalises schema 1 and 2 records, aggregates them into day-level buckets keyed by profile × playbook × version × environment × execution mode (collapsing to ISO weeks above 4000 buckets), and embeds those buckets in `dashboard.html`. Metrics are computed twice from the same buckets — in Python for the Markdown snapshot and tests, and in the page's JavaScript for client-side filters — and a test runs the JS under node to assert parity. Charts are inline SVG; there is no dependency, CDN or network request. `schedule` writes one launchd agent (`com.groundwork.report`) after booting out any previous one, so replacement never duplicates; `generate --snapshot` also writes dated `.html`/`.md` files. The generator is never called from a hook: reporting failures are isolated from task execution and telemetry.

## Request lifecycle

```
                 USER GOAL  (a fresh session first receives the Groundwork snapshot:
                     │       branch · HEAD · dirty files · OpenSpec progress · discovered commands)
                     ▼
   rules/engineering-workflow.md classifies the request
                     │
        ┌────────────┼────────────┐
    TRIVIAL       STANDARD      MATERIAL
        │             │             │
    just do it   UNDERSTAND     UNDERSTAND — state table from repo evidence
        │         inline plan   openspec init (if needed)
        │         + dimensions  /opsx:propose — proposal, delta spec,
        │           that apply  design (answers architecture-quality.md §2),
        │         + tests       tasks; openspec validate
        │         + self-       DECISION records (evidence-policy.md §3)
        │           review      choose execution model (§6): main /
        │             │         subagents / Agent Team
        │             │             │
        │             │       /opsx:apply — implement, tests from the
        │             │       project's own commands (validation ladder)
        │             │             │
        │             │       independent fresh-context review —
        │             │       ECC reviewer, subagent, or reviewer
        │             │       teammate; MUST FIX vs NICE TO HAVE;
        │             │       ENFORCED by hooks/require_material_review.py
        │             └────────────┤
        │                          ▼
        │              verify → runtime-validate when runtime matters
        │              → deploy / live-validate if in scope
        └────────────────┬─────────┘
                          ▼
              COMPLETION STATUS block
   Code / Tests / Reviewed / Merged / Deployed / Live validated
      → COMPLETE / PARTIAL / BLOCKED / PLANNED / FAILED
```

## What is actually enforced versus advisory

Being honest about this distinction is the whole point of Groundwork — a rule that only asks is not the same as a rule that blocks.

| Mechanism | Enforced (hook) or advisory (rule text) |
|---|---|
| Tier classification (TRIVIAL/STANDARD/MATERIAL) | Advisory — judgment call, not machine-checked |
| OpenSpec proposal/spec/design/tasks for MATERIAL work | Advisory — the rule says to, nothing blocks skipping it |
| Architecture-quality questions and DECISION records | Advisory |
| Evidence labels, validation ladder, runtime-validation rule | Advisory |
| Execution model choice (main / subagent / team) | Advisory; the platform itself gates team spawning on `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` and interactivity |
| Project snapshot at session start | **Injected** — `hooks/groundwork_session_snapshot.py`, a SessionStart hook. Deterministic facts, framed as data (explicit ▼/▲ boundary, per-field caps, control characters stripped). This *mitigates* prompt injection from hostile branch/commit/file names; it cannot eliminate it, because the text is still shown to the model |
| Independent review before a MATERIAL change is "done" | **Enforced** — `hooks/require_material_review.py`, a Stop hook. Extended 2.0: if the reviewer emits the `REVIEW RESULT` block (`output-contract.md`), the gate also requires the *most recent* review's own verdict to report zero MUST FIX findings — an edit and a validation re-run afterward are not, by themselves, sufficient; a fresh review is structurally required. Without the block, degrades to the original presence-only check. Residual gameability: a call merely *named* "…review…" satisfies presence; a reviewer could self-report `Must-fix: 0` without a genuine fix — the gate proves a review-shaped delegation happened and what it reported, not that the review was thorough |
| No direct push to main/master/production, no force-push | **Enforced** for every `git push` the parser can see — `hooks/block_protected_push.py`, a PreToolUse hook: shell chains, `sh/bash/zsh -c`, `eval`, `HEAD`/`@`, multi-refspec, `:branch` deletion, `--all`/`--mirror`. Not parsed: other wrappers (`xargs`, `python -c`, a script that pushes) and non-exact branch names (`Main`, `release/1.2`). Claude Code's own Bash permission prompt is the backstop for those |
| Investigate before first edit of a file / destructive Bash | **Enforced** — ECC's own GateGuard hook |
| No `--no-verify` git bypass | **Enforced** — ECC's own `block-no-verify` hook |
| Completion status block format and hard rules | Advisory |

## `require_material_review.py` — how the gate actually works

On every `Stop` event:
1. Look for `openspec/changes/*/tasks.md` under the current working directory where every checkbox is `[x]`.
2. Of those, keep only the ones `git status` shows as dirty (uncommitted/untracked) — i.e. this session's own fresh work, not an old change someone already reviewed and merged.
3. If any remain, scan the session transcript in order for every reviewer-shaped call: an `Agent`/`Task` tool call whose `subagent_type` or `name` contains "review", or a `Skill` call whose name contains "review". `name` matters because current Claude Code launches Agent Team teammates and named subagents through the same `Agent` tool, often with no reviewer-specific `subagent_type`. The free-text `description` deliberately does not count — an unrelated "Review existing tests" exploration would otherwise satisfy the gate by coincidence.
4. None found → block, naming the change and what's missing (unchanged from 1.x).
5. **(2.0)** One or more found → for each, look for its own `REVIEW RESULT` block (`output-contract.md`) in its tool result. If the *most recent* review-shaped call's own result reports `Must-fix: 0` (or no parseable block at all — legacy fallback) → allow. If it reports `Must-fix: N > 0` → block, naming the count and whether a follow-up edit and a validation re-run (`groundwork_telemetry.py`'s own `TEST_CMD` pattern, reused) have been observed since — an edit and a re-test are not, by themselves, sufficient; only a *further*, fresh review-shaped call whose own result reports zero remaining findings clears the gate, because the check always evaluates the transcript's most recent review verdict.

Claude Code stops re-running any Stop hook after 8 consecutive blocks, so the gate can never trap a session. Fails open on any error (no git, no `openspec/` directory, unreadable transcript, unparseable review result). Reviewer *selection* is untouched — any reviewer-shaped call satisfies presence; the gate additionally proves what the most recent one's own self-reported verdict was, when it reported one, not that the review was thorough or that the fix is correct.

## `groundwork_session_snapshot.py` — what continuation is built on

On every `SessionStart` (startup, resume, clear, compact, fork) it injects, as `additionalContext`, only facts it can read from the repository: git branch/HEAD/ahead-behind/dirty counts/recent commits, each active OpenSpec change with `<done>/<total>` tasks (flagging a complete-and-uncommitted change as "review gate applies"), the signal files and directories present, and the verification commands the repo declares (Makefile targets, package scripts, pytest/ruff/mypy in pyproject, tox/nox, Go/Rust, Terraform directories, CI workflows). Capped at 2,500 characters, 3-second git timeouts, no network, fail-open, `GROUNDWORK_SNAPSHOT=off` to disable. It complements ECC's SessionStart bootstrap (saved session summary + instincts, matched by worktree) rather than duplicating it: ECC remembers what the last session *said*, the snapshot shows what the repository *is*.

Continuation itself is the rule in `engineering-workflow.md` §7: reconstruct from snapshot → git → OpenSpec → docs → tests/CI/IaC → implementation → only then session files and memory; produce the DONE / PARTIAL / MISSING / BLOCKED / UNVERIFIED table; act on code over docs. For OpenSpec-tracked work, OpenSpec tasks and git remain the record — still no state file there.

**Investigation continuity (2.0), for work not tracked by an OpenSpec change**: the same hook's `investigation_path()`/`investigation_facts()` compute a deterministic path (`~/.claude/groundwork/investigations/<repo-slug>-<hash>.md`, from `git rev-parse --show-toplevel`) and surface that file's content — capped, control-character-stripped — as part of the same `additionalContext`, when one exists. This is the one deliberate, small, capped exception to "no Groundwork state file": a single per-repository Markdown file with an exact field list (objective, proven facts, evidence references, decisions, rejected hypotheses with reason, active hypotheses, files changed, validation results, blockers, uncertainty, remaining tasks, next action) — never chain-of-thought — created lazily by the model's own write, exactly like `telemetry/`/`reports/`, not installed or managed by `install.sh`. `engineering-workflow.md` §7 states the writing/reopening rules, most importantly: a hypothesis recorded as rejected stays rejected on recovery unless new evidence specifically contradicting the rejection reason is stated; current repository/runtime evidence always outranks what was saved.

## Execution model — how Claude chooses main / subagent / team

`engineering-workflow.md` §6. Main session for sequential work sharing context; subagents for isolated investigation, verbose reads, and independent judgment (reviews); an Agent Team only for two or more genuinely independent workstreams with separate file ownership, sized 2–4, with a one-line justification, specialists derived from the task (reusing existing subagent definitions), and the lead synthesizing. When teams are disabled or the session is non-interactive, the same decomposition runs on subagents. Groundwork adds no orchestration code: the Agent tool, `SendMessage`, the task list and the platform's own hooks are the runtime.

## Capability ownership (2.0)

Every Groundwork capability has exactly one owner. No two components define the same contract — this is checked explicitly during design and again at each phase's independent review, not just asserted. This is the same discipline `architecture-quality.md` §4 already states generally ("no abstraction, layer, plugin point, framework, or option without a concrete reason tied to a requirement or evidence") applied specifically to capability ownership — no new rule mechanism, just this table making the existing anti-fragmentation principle's outcome explicit and checkable. Summary (full detail and rationale: `openspec/changes/groundwork-2-enterprise-sre/design.md` §J, the authoritative source — this table is a pointer, not a second copy, and is not repeated in full to avoid drift):

| Capability | Owner | Notes |
|---|---|---|
| WHAT/WHY, acceptance criteria for MATERIAL work | OpenSpec | Unchanged |
| Agent/subagent/team execution primitive | Claude Code | Groundwork adds no orchestration code |
| Task routing (10 categories) | Groundwork (`rules/task-routing.md`) | Unchanged in 2.0 |
| Output truth (evidence, validation, completion) | Groundwork (`rules/output-contract.md`) | Never owned by a native output style — see design.md §H |
| Evidence taxonomy | Groundwork (`rules/evidence-policy.md`) | Extended 2.0: `CONFLICTING EVIDENCE`, `UNKNOWN` |
| Independent review (presence + verdict) | Groundwork (`hooks/require_material_review.py`) | Strengthened 2.0: a MUST FIX finding requires a fresh review reporting `Must-fix: 0` (parsed from its own `REVIEW RESULT` block, `rules/output-contract.md`), not just an edit and a test re-run |
| Protected-branch/push safety | Groundwork (`hooks/block_protected_push.py`) | Unchanged |
| Session continuity snapshot | Groundwork (`hooks/groundwork_session_snapshot.py`) | Extended 2.0: investigation continuity (`investigation_path()`/`investigation_facts()`) for non-OpenSpec-tracked work — see the session-snapshot section above |
| Telemetry | Groundwork (`hooks/groundwork_telemetry.py`) | Unchanged |
| Health dashboard | Groundwork (`scripts/groundwork_report.py`) | Unchanged |
| Installer/upgrade/rollback | Groundwork (`install.sh`/`setup.sh`) | Strengthened 2.0: corrected Node floor, enforced in `install.sh` itself |
| ECC install/curation policy | Groundwork (`install.sh`, documented in `ecc-capability-policy`) | Corrected 2.0: ECC installs unpinned from GitHub `main` (pinned since 2.1, see below); no upstream curation mechanism exists on this install path, so the full catalog ships, governed only by `hook_profile` and whole-plugin disable |
| Repository-understanding discovery | Groundwork (`playbooks/implement.md`/`deploy.md`/`design.md`) | New 2.0: one shared, proportional discovery checklist referenced by all three, not restated |
| Builder execution roles | Groundwork (`rules/engineering-workflow.md` §6) | New 2.0: four dynamic personas (Infrastructure/Platform/Delivery/Application Engineer) — never a permanent `.claude/agents/*.md` file |
| Presentation/output-style truth | Groundwork (`rules/output-contract.md`'s truth/style invariant + `playbooks/document.md`) | New 2.0: a native output style may change tone/format, never Groundwork's evidence or completion rules |
| Teach/learn | Groundwork (`playbooks/explain.md`) | New 2.0: draws only on session/investigation-continuity evidence already established; no new storage |
| ECC's specialist agents/skills | ECC | Installed, not forked or vendored |
| MCP/external tool access | The task's own environment | Groundwork installs nothing by default; `docs/INTEGRATIONS.md` (2.1) documents, never wires |
| Credential handling | The user's own MCP/CLI configuration | Never Groundwork |
| Capability resolution (which tool for a task) | Groundwork (`rules/engineering-workflow.md` §6a, 2.1) | Judgment guidance over repo tooling → native → skill → MCP/CLI → browser → user; never overrides tier/evidence/authorization |
| Scheduled/recurring automation (Routines) | Groundwork (`scripts/groundwork_routines.py`, 2.1) | New in 2.1; reuses `groundwork_report.py`'s launchd/cron scheduling pattern, not a new scheduler |
| Capability/Routines configuration | Groundwork (`scripts/groundwork_config.py`, `setup.sh --configure`, 2.1) | New in 2.1; one human-readable `config.json`; shipped profiles never contain secrets, `validate` checks a hand-edited file on request |
| Dependency version pinning (ECC) | Groundwork (`install.sh`, 2.1) | Pinned via `#ref`; unchanged for OpenSpec (already npm-version-pinned) |
| Integration Catalog (capability → approved mechanism, truthful readiness) | Groundwork (`scripts/groundwork_integrations.py`, 2.1) | New in 2.1; read-only, non-mutating — documents and observes, never installs or wires. See the MCP tool-loading note below for what it deliberately does not do |
| MCP tool-schema loading / lazy discovery | Claude Code (native Tool Search) | Groundwork builds no dynamic loading/activation engine of its own — see below |

This table is extended, not rewritten, as later phases ship (2.0: review-evidence strengthening, investigation continuity, the ECC install-policy correction, repository understanding, builder execution roles, presentation/output-style, teach/learn; 2.1: capability resolution, Routines, capability configuration, ECC pinning, the Integration Catalog) — each documented here only once actually implemented, per the same evidence-first rule this document follows for everything else. SRE-capability consolidation and D5's deferred Tier-2 safety guards added no new owner (composition and an explicit non-build respectively) and so have no row here.

## MCP tool loading — deliberately not Groundwork's job (2.1)

The Integration Catalog (`scripts/groundwork_integrations.py`) tells a session which access mechanism is *approved* for a capability (e.g. `kubernetes.logs.read` → Kubernetes MCP or `kubectl`) and what its currently observed readiness is. It does **not**, and will not, decide which MCP servers or tools are actually loaded into context for a given task, or activate/deactivate one per task. Claude Code's own Tool Search already does exactly this — it defers MCP server connections and full tool-schema loading until a task's tool search actually matches them, which is the documented, supported answer to MCP tool-schema context overhead. Building a parallel dynamic-loading or activation engine inside Groundwork would duplicate a platform capability and, worse, invite a false claim: there is no documented Claude Code mechanism today that lets a plugin force a specific MCP server active or inactive for one task. So the catalog's role stops at *guidance* — recommending an approved mechanism and reporting its observed state — never enforcement of what actually gets exposed at runtime.

## Autonomy — when Groundwork asks versus proceeds

The generic "should I apply this?" stop for every MATERIAL-tier change was tried and removed — it fired constantly and added nothing evidence didn't already answer. The current rule: continue whenever repository evidence, runtime evidence, or official documentation gives a clear answer, and stop only for a genuine owner decision — business/product ambiguity, multiple materially different architectures with no evidence to pick between them, an irreversible/destructive operation, missing credentials, a security boundary needing authorization, or information nothing available can determine. See [VALIDATION.md](VALIDATION.md) for what actually triggers each path in practice.
