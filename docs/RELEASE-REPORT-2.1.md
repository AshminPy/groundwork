# Groundwork 2.1.0 — release-candidate report

Prepared at the end of the autonomous implementation authorized by the "Groundwork 2.1 — Context, Capabilities, Routines & UX" brief. This is the single consolidated report for owner review before any merge decision. It duplicates nothing from `docs/VALIDATION.md`, `openspec/changes/groundwork-2.1-context-routines-ux/design.md`, or that change's `tasks.md` — it points at them — except where a number needed to be re-verified fresh for this report (each such number is marked with the exact command run). Structure follows the brief's own required sections.

**Release status: NOT merged, NOT tagged, NOT published.** Open as draft PR [#22](https://github.com/AshminPy/groundwork/pull/22) against `main`, for owner review. This is an explicit, hard constraint the brief itself sets — nothing in this report should be read as recommending an autonomous merge.

---

## 1. Release identity

- **Branch**: `claude/groundwork-2.1-context-routines-ux`
- **HEAD**: `b7a80a3fa45b1c61726b479b021c05510c02cf19`
- **Base**: `origin/main` at `73d5d13ffaa0c5a5755b77f88f7f2cb0b07e798c` (the already-merged Groundwork 2.0.0)
- **Commits on top of base**: 2 — `6913008` (the full 2.1 implementation) and `b7a80a3` (independent-review fixes)
- **Files changed vs `origin/main`**: 27 (`git diff --name-only origin/main..HEAD | wc -l`), 14 newly added
- **Diff summary**: `git diff --stat origin/main..HEAD` → 27 files changed, 2010 insertions(+), 42 deletions(-)
- **PR**: [#22](https://github.com/AshminPy/groundwork/pull/22), draft, subscribed for CI/review activity
- **OpenSpec change**: `openspec/changes/groundwork-2.1-context-routines-ux/` — `proposal.md`, `design.md` (§A–§L), `tasks.md` (67 tasks, 63 checked `[x]`, 4 explained deferrals — see §12 below), 4 capability spec deltas (`routines`, `dependency-pinning`, plus `ADDED` requirements folded into the existing `onboarding` and `task-routing` baseline capabilities)
- PR #21 (a separate, unrelated documentation-only change) was never touched by any of this work, per the owner's standing instruction.

## 2. Scope and status

All 12 phases in `tasks.md` are complete or explicitly, honestly deferred:

| Phase | What | Status |
|---|---|---|
| 0 | OpenSpec scaffold | Complete |
| 1 | Context-engineering audit | Complete |
| 2 | Capability resolution model | Complete |
| 3 | MCP/integration capability matrix | Complete |
| 4 | Curated optional skills evaluation | Complete |
| 5 | Routines subsystem | Complete |
| 6 | Browser/Chrome governed execution policy | Complete |
| 7 | `setup.sh` capability configurator | Complete (1 real bug found+fixed, see §9) |
| 8 | `groundwork doctor`/`configure`/`routines` commands | Complete (1 real bug found+fixed, see §9) |
| 9 | ECC pinning | Complete except upgrade-cycle re-proof (§12, known gap) |
| 10 | Testing | Complete |
| 11 | Live validation | Complete |
| 12 | Independent review + docs + this report | Complete |

## 3. Architecture — what changed, what didn't

Groundwork's ownership model is unchanged in kind: Groundwork owns policy (routing, evidence, safety, continuity, completion truth), never execution capability. OpenSpec still owns WHAT/WHY; ECC still owns HOW (agents/skills); Claude Code still owns runtime primitives; the task's own environment still owns MCP/CLI/credentials. **Unchanged, verbatim**: 10 playbooks, 4 dynamic builder personas (still dynamic, no permanent agent files), automatic main/subagent/Agent-Team selection, the session-snapshot/investigation-continuity mechanism, the independent-review gate, the push guard, telemetry's schema and privacy discipline, the evidence taxonomy, OpenSpec's and ECC's roles.

**What 2.1 adds** — four new policy/mechanism surfaces, each with exactly one owner (`docs/ARCHITECTURE.md`'s capability-ownership table, extended with 5 new rows):
1. **Capability resolution** (`rules/engineering-workflow.md` §6a) — judgment guidance for *which tool* serves a task, layered on top of (never replacing) the existing tier/evidence/authorization rules.
2. **Routines** (`scripts/groundwork_routines.py`) — a new execution mode (scheduled, headless, non-interactive) for the same governance the interactive session already has, not a second rule system.
3. **Capability configuration** (`scripts/groundwork_config.py`) — one small, human-readable, no-secrets config file.
4. **Dependency pinning** (`install.sh`) — ECC now installs pinned rather than floating `main`.

No new hooks, no new playbooks, no new rule files beyond the two extended, no new persistent daemon, no new third-party dependency (Groundwork remains 100% Python-stdlib across every script — confirmed by grep, no `requirements.txt`/`pyproject.toml` anywhere in the repo).

## 4. Context engineering

Full detail: `docs/CONTEXT-ENGINEERING.md` (new). Summary of the classification every context source received:

| Class | Examples | Notes |
|---|---|---|
| Always-loaded | 5 rule files (~290 lines total, +21 lines this pass for §6a and task-routing §4) | Unchanged budget discipline |
| Selectively-loaded | 10 playbooks (1838–3589 bytes each, capped at 4000) | Unchanged |
| Lazy-deferred | MCP tool schemas (native Tool Search, observed live in this session's own deferred-tool listing), skill bodies (progressive disclosure — description-only until invoked) | Native mechanism, nothing built |
| Isolated | Subagent transcripts (only the final report crosses back — directly exercised by this very report's two independent-review dispatches) | Unchanged, and the mechanism this report's own evidence trail depends on |
| Persisted | Session snapshot (≤2500 chars), investigation-continuity file (≤800 chars display), Routines' own telemetry (`routines.jsonl`, structured fields only) | Routines telemetry is new, same discipline |
| Reconstructed | Git/OpenSpec state at session start, re-derived every session | Unchanged |
| Unnecessary/duplicated | None found (§ of `CONTEXT-ENGINEERING.md` states this explicitly, not silently omitted) | |

**Conclusion, unchanged from the audit**: every 2.1 capability composes native Claude Code mechanisms (Tool Search, progressive-disclosure skills, subagent isolation, headless `claude -p`) rather than building custom context infrastructure. No token-usage number in this report or its linked docs is fabricated — where the platform doesn't expose reliable measurement (e.g., a live activity view), that's stated as a limitation (§13), not worked around with an invented number.

## 5. Skills

No new skill was installed or bundled by this change. Evaluated per the brief's own instruction (full detail: `docs/FUTURE-SCOPE.md` §13):

| Skill | Source | Trust | Decision | Why |
|---|---|---|---|---|
| `teach` | github.com/mattpocock/skills, MIT | Community, small, single-purpose | Recommended, optional | Already lazy (`disable-model-invocation: true`, user-invoked via `/teach`); no context cost unless explicitly summoned; owns *technique*, Groundwork still owns routing/evidence |
| Task Observer | rebelytics/one-skill-to-rule-them-all, CC BY 4.0 | Community | Declined | Every credible implementation is near-always-on; conflicts with the brief's own strict no-raw-capture privacy requirement (no raw prompts/source/credentials/transcripts) |
| `wshobson/agents` | 40k★, MIT, native plugin marketplace | Community, large | Documented candidate only, **not adopted** | Per the owner's explicit instruction; deeper SRE/CloudOps coverage than ECC but a real supply-chain decision requiring its own evaluation, not bundled into this pass |
| security-review, architecture-review, doc-gen, diagram | Existing (from `groundwork-2-enterprise-sre`) | N/A | Confirmed already present, not duplicated | This pass checked for overlap before proposing anything new — none found needing a new capability |

## 6. MCP/integrations

Documentation only — `docs/INTEGRATIONS.md` (new). No MCP server, CLI tool, or credential was installed, configured, or wired by this change; this sandbox has no credentials for any of these systems to wire even if it wanted to. The capability matrix (Domain / Preferred access / Trust level / Read-Write / Auth model / Context strategy) covers GitHub, Spacelift, Jira, Confluence, AWS, GCP, Kubernetes, Terraform, and observability (Grafana/Datadog/PagerDuty/Sentry/Prometheus) — each researched live (2026-09-28) against current vendor/official sources, not assumed from training data. **Slack is deliberately excluded**, per explicit instruction. Validation status for every row: **NOT WIRED — documentation only**, stated as such, not implied otherwise.

## 7. Routines

Full detail: `docs/ROUTINES.md` (new). Framework: `scripts/groundwork_routines.py`, one generic mechanism (name + prompt-template function + `mutates` flag + default schedule), not six bespoke scripts.

| Routine | Mutates | Schedule | Inputs | Evidence sources | Safety | Failure behavior | Validation status |
|---|---|---|---|---|---|---|---|
| `jira_eod` | Yes | daily | offline-work text (optional) | git/PR/OpenSpec/investigation-continuity/tests | dry-run default, read-back-before-VERIFIED, never widens Jira write access beyond what's already configured | Reports `failed`/`BLOCKED` with reason, never invents a post | **Live-verified** (dry-run, this session) |
| `news` | No | daily | topic list | web search (authoritative sources only) | N/A (read-only) | No filler when nothing material | **Live-verified** (§11) via `work_digest`'s identical mechanism — not independently re-run for `news` specifically this pass |
| `weekly_status` | No | weekly | none | git/PR/OpenSpec/tests/reviews | N/A | States unknown rather than guessing | Mechanism-verified, not separately live-run |
| `pr_followup` | No | daily | none | `gh`/repo equivalent | N/A | Merged ≠ deployed, stated explicitly in the prompt | Mechanism-verified, not separately live-run |
| `work_digest` | No | daily | none | git/PR/OpenSpec/investigation state | N/A | No task from a weak signal | **Live-verified** — real `claude -p` run, exit 0, 15.8s, structured telemetry recorded (0600, no raw output) |
| `doc_drift` | No | weekly | none | code vs docs | Never auto-rewrites docs | Reports drift, doesn't fix it | Mechanism-verified, not separately live-run |

Every routine shares the same safety contract (`build_command()`, tested for all 6 × both dry-run states): never `--dangerously-skip-permissions`, never `--bare`, always `--permission-mode dontAsk --permission-prompts none` plus an explicit `--allowedTools` allowlist. Scheduling reuses `groundwork_report.py`'s existing launchd/cron pattern — confirmed by direct code reading, not a new scheduler. Off-switches (`GROUNDWORK_ROUTINES[_<NAME>]=off`) confirmed to prevent any subprocess spawn, even with `claude` unreachable on `PATH`.

## 8. UX — setup, profiles, config, doctor

`setup.sh` gained one optional fourth question (capability/Routines selection, default **skip** — the unmodified `./setup.sh` one-command path installs exactly the same core as before) and three new read-only/low-risk modes:
- `--doctor` — extends `--verify` with Capabilities/Routines status; now degrades gracefully (INVALID row, not a crash) on a corrupted `config.json` (§9).
- `--configure` — revisit selection only, no backup, no reinstall.
- `--routines` — list configured Routines and last-run status.

8 profiles (SRE/CloudOps, Platform Engineering, DevOps, Software Engineering, Cloud Architecture, Security Engineering, Minimal, Custom) — a starting point, never a forced install; every capability and Routine stays individually toggleable in `config.json`. **No new terminal-UI dependency**: Groundwork stays stdlib-only; the existing HTML dashboard is unchanged and remains the presentation layer. A live activity view was researched and deferred (§13) rather than faked.

## 9. Tests — exact commands and results

```
$ python3 -m pytest tests -q
............................                                             [100%]
28 passed in 34.12s

$ python3 tests/test_hooks.py               → 131 passed, 0 failed
$ python3 tests/test_playbooks.py           → 143 passed, 0 failed
$ python3 tests/test_report.py              → 67 passed, 0 failed
$ python3 tests/test_setup.py               → 94 passed, 0 failed
$ python3 tests/test_telemetry.py           → 81 passed, 0 failed
$ python3 tests/test_groundwork_config.py   → 112 passed, 0 failed   (new)
$ python3 tests/test_groundwork_routines.py → 115 passed, 0 failed   (new)

$ openspec validate groundwork-2.1-context-routines-ux --strict
Change 'groundwork-2.1-context-routines-ux' is valid

$ openspec validate --changes
✓ change/groundwork-2-enterprise-sre
✓ change/groundwork-2.1-context-routines-ux
✓ change/intelligent-engineering-harness
Totals: 3 passed, 0 failed (3 items)

$ bash -n setup.sh && bash -n install.sh && bash -n uninstall.sh
(all clean)
```

743 total deterministic checks across 7 files (131+143+67+94+81+112+115), 0 failed. Two new test files added this pass (`test_groundwork_config.py`, `test_groundwork_routines.py`); every existing file extended, not rewritten; the full pre-2.1 suite (16 test functions, 485+ checks) still passes unmodified in kind.

## 10. Runtime validation — exact scenarios and results

All performed live in this sandbox against the real, installed Claude Code CLI (2.1.284) and real `bash`/`python3` — never simulated. Full detail and exact commands: `docs/VALIDATION.md`'s "Groundwork 2.1.0" entry.

1. **Fresh non-interactive install with `--capability-profile sre-cloudops`** → `config.json` written correctly under the target `CLAUDE_CONFIG_DIR`, `jira_eod`/`news`/`pr_followup`/`weekly_status`/`work_digest` all enabled, `--doctor` reports them all correctly.
2. **`--doctor` against a deliberately broken core install** (playbooks dir removed) → Capabilities/Routines section still prints (this was Bug 2, fixed and confirmed by a second independent reviewer's old-vs-new reproduction, §11).
3. **`--doctor` against a hand-corrupted `config.json`** → degrades to one `Capabilities INVALID` row, still reaches `-- Routines --`, exits 0 (this was independent-review MUST FIX 1, fixed and confirmed).
4. **Live routine execution**: `work_digest` via real `claude -p` → exit 0, 15.8s, structured telemetry recorded with `0600` permissions, zero raw output persisted (confirmed by reading the file directly). `jira_eod --dry-run --offline-work "..."` → exit 0, ~15.0s, dry-run and offline-work-folding paths both exercised.
5. **ECC pinning**: `--doctor` reports `plugin ecc@ecc 2.2.1 (pinned to v2.2.1)` on a matching stub, and the differs-from-pin message on a mismatched one.
6. **Uninstall after a pinned, capability-configured install**: `config.json` removed, every scheduled routine plist unscheduled — confirmed via a real launchd-plist write/read cycle in a test-scoped `LaunchAgents` directory.
7. **Version-bump sanity check**: fresh install after the CHANGELOG 2.1.0 entry stamps `VERSION` as `2.1.0` (was `2.0.0` through earlier tests in this same session, confirming `install.sh`'s CHANGELOG-derived version stamping works end-to-end).

## 11. Independent review — full history

Two rounds, both fresh-context background subagents with no access to this session's own reasoning, per the project's "do not self-certify" convention.

**Round 1** — full adversarial review of the entire diff vs `origin/main`. Returned `changes-required`, 2 MUST FIX:
1. The doctor fix in Phase 8 was incomplete: `verify_capabilities()`'s inline Python had no fail-open guard, so a corrupt `config.json` crashed the *entire* `--doctor` command under `set -euo pipefail` — worse than the bug it was meant to fix (silence, not just a dropped section).
2. `docs/ARCHITECTURE.md`/`README.md` still asserted ECC "installs unpinned from GitHub `main`" elsewhere in files this change otherwise edits, self-contradicting the new pinning content.

Plus 3 NICE TO HAVE findings (all fixed): `uninstall.sh`'s hardcoded routine-name list (now derived from the `ROUTINES` registry), an unpinned `JIRA_LIVE_TOOLS == READ_ONLY_TOOLS` safety claim (now a direct test), and an overstated "never contains credentials" guarantee (reworded to what's actually true).

Both MUST FIX findings were fixed at the root (not worked around) and committed as `b7a80a3`.

**Round 2** — narrowly-scoped confirmation review, per the same project convention already used once in 2.0 (Phase 4/5: "a second, narrowly-scoped independent review verified both MUST FIX fixes by direct old-vs-new reproduction"). Extracted the actual pre-fix `setup.sh` via `git show HEAD^:setup.sh`, ran both old and new against the identical corrupted-`config.json` scenario side by side, confirmed the old script dies silently while the new one degrades correctly; grepped both doc files for every remaining "unpinned" occurrence and confirmed each is inside a clearly-dated historical clause, not a live claim. Independently re-ran the full test suite and `openspec validate --strict`.

**Final verdict: `approve`, `Must-fix: 0`.**

Full transcripts of both rounds' findings: `docs/VALIDATION.md`'s "Independent review" subsection.

## 12. Known limitations and deferred items (honestly carried forward, not fixed)

**Known limitations:**
- **ECC upgrade-cycle re-proof not exercisable** (`tasks.md` 9.7) — confirming `claude plugin update ecc@ecc` stays within the pinned ref rather than jumping to a newer, untested version needs live network access to the real plugin marketplace, unavailable in this sandbox. Documented, not claimed as tested.
- **No live activity view** (§13 of `design.md`) — no reliable Claude Code lifecycle-event source was found to build one on honestly; not faked.
- **Prompt-content quality for `news`/`weekly_status`/`pr_followup`/`doc_drift`** was mechanism-verified (same `build_command()`/`run_routine()` path as the live-run `work_digest`) but not independently live-run per routine this pass — a model-behavior property of the prompt text, not the framework, and each shares the identical, already-tested invocation mechanism.
- **MCP/CLI integrations are documentation only** — `docs/INTEGRATIONS.md` is researched guidance, not a wired, credentialed, validated connection to any of the systems it covers.

**Deferred items, with reasons** (all in `docs/FUTURE-SCOPE.md` §13 and `design.md`):
- Task Observer — privacy-requirement conflict (near-always-on implementations vs. the brief's own strict no-raw-capture rule).
- Six further routine candidates (cert/PKI expiry, dependency advisories, infra drift, cost anomaly, stale-RCA follow-up, release readiness) — scored, not built; six real, tested routines was the right scope for one release.
- `wshobson/agents` adoption — candidate only, per explicit instruction not to auto-adopt.
- A new terminal-UI dependency — Groundwork stays stdlib-only; no evidence justified the first-ever third-party dependency.

## 13. Acceptance-standard walkthroughs

The brief's own two end-to-end UX examples, walked through against what actually shipped:

**"Investigate why this GKE deployment is failing and fix it."** Capability resolution (§6a) routes this through the existing TROUBLESHOOT playbook unchanged — repository-understanding discovery, evidence-first investigation, then the resolution order: repo's own tooling first (e.g. a `Makefile`/deploy script), then Claude Code native (Bash/kubectl if configured), then a trusted already-installed skill, then a trusted already-configured MCP/CLI for GKE/Kubernetes (per `docs/INTEGRATIONS.md`'s guidance — nothing auto-installed), then browser only if nothing structured exists. The user never names a playbook, a persona, or an MCP — routing, evidence discipline, and capability choice all resolve from the request itself, exactly as before 2.1; 2.1 only made the *tool-choice* step (repo → native → skill → MCP/CLI → browser → user) into explicit rule text instead of implicit judgment.

**"Teach me how this Terraform module works."** Routes through EXPLAIN's existing teach/learn capability (from 2.0); the optional `teach` skill (§5 above), if the user has it installed, adds pedagogical technique without taking over routing or evidence — Groundwork still owns *what* gets explained and from what evidence, the skill only owns *how* it's taught. No change to this flow was required by 2.1; it was already the target architecture, and this pass's capability-resolution rule text formalizes the "does a skill already installed" check as an explicit early step rather than an implicit one.

Neither flow requires the user to know a playbook name, a persona name, a skill name, an MCP name, an OpenSpec command, or when review/validation fires — consistent with the brief's own stated goal.

---

*Every figure in this report was re-verified by running the underlying command at report time (§9–§10), not recalled from memory. See `docs/VALIDATION.md`, `openspec/changes/groundwork-2.1-context-routines-ux/design.md` and `tasks.md` for full supporting detail.*
