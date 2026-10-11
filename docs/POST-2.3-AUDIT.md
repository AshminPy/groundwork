# Post-2.3.0 programme: final security and release audit

**Status: NOT READY FOR A RELEASE CANDIDATE.** Every gate that could be run here was run and none found a new
defect in the merged result, but three gates are open (see "Open gates"). No release candidate or release notes
were prepared, and nothing was merged or published.

Date: 2026-10-11. Base: `main` at `24080a6` (v2.3.0). Every row says how it was established. Anything not
observed is labelled `RUNTIME VALIDATION REQUIRED` or `NOT VERIFIED`.

## What was audited

The audit ran on a scratch merge of all milestone branches (not on each PR alone), because the PRs overlap in
`scripts/groundwork_cli.py`, `uninstall.sh`, the README, `docs/ARCHITECTURE.md` and `CHANGELOG.md`.

| PR | Branch | Head audited |
|---|---|---|
| #43 per-tool-call telemetry | `feat/per-tool-call-telemetry` | `ce54557` |
| #41 Jira `acli` probe | `feat/jira-acli-connected-probe` | `2533ea2` |
| #42 statusline symbol presets | `feat/statusline-symbol-presets` | `1445a63` |
| #45 Claude mods evaluation (docs) | `docs/claude-mods-evaluation` | `c821f46` |
| #47 evidence receipt | `feat/evidence-receipt` | `529fa48` |
| #49 Groundwork Copilot | `feat/groundwork-copilot` | `ae30d9a` |
| #46 snapshot worktrees | `feat/snapshot-worktrees` | `8dc56cc` |
| #48 Autoship recipe (docs) | `docs/autoship-recipe` | `b8e94be` |
| #50 Hands-Free SRE investigation (docs) | `docs/hands-free-sre-investigation` | `a1e2c83` |

If any of these heads moves after this audit, the integrated rows below must be re-run.

## Gates

| Gate | Result | Evidence | Not covered |
|---|---|---|---|
| Regression | PASS | `python3 -m pytest tests -q` on the merged tree: 158 passed in 119.8 s (main: 110). `openspec validate --all --strict`: 15 of 17 pass; the two failures (`spec/onboarding`, `spec/health-dashboard`, placeholder `## Purpose`) are the same two that fail on `main` | no CI exists in the repository (`.github/` absent), so this was run by hand |
| Clean install | PASS (ECC step stubbed) | `setup.sh --non-interactive --profile personal --no-agent-teams --schedule disabled --no-install-prereqs` with `HOME` set to an empty sandbox holding a user `settings.json` and `CLAUDE.md`: exit 0; `--verify` and `groundwork doctor` report all checks passed; the user's model, allow and deny rules, env value, own Stop hook and `CLAUDE.md` are unchanged; 6 hook files and the `groundwork` command are installed (`--verify` checks a fixed list of 4 of them) | The `claude plugin` commands were replaced by a stub, so the real ECC install and the real parsing of `claude plugin list` were **not** exercised (no third-party code was fetched) |
| Upgrade | PASS | Installed `main` (v2.3.0) into a sandbox, then ran the merged tree's `setup.sh` over it: exit 0; two new hook entries appear (`PostToolUse`, `PostToolUseFailure`, from #43); every non-hook settings key and the user's own Stop hook are unchanged; a new backup directory was created | `groundwork update` (which downloads a published release) cannot be tested until a release contains these changes: `RUNTIME VALIDATION REQUIRED` |
| Idempotence | PASS | Second `setup.sh` run: `settings.json` byte-identical; installed rules, hooks and scripts identical; only generated reports, the integration cache and a timestamp file differ; a second backup was written | |
| Rollback | PASS | `setup.sh --rollback <first backup>`: exit 0; `settings.json` byte-identical to the pre-Groundwork file; `CLAUDE.md` unchanged; `rules/` and `hooks/` gone; the rolled-back state was saved to a `.claude-groundwork-disabled-*` directory | |
| Uninstall | PASS | `uninstall.sh` after a re-install: exit 0; `settings.json` equal (as parsed JSON) to the pre-Groundwork file; hooks, rules and the `groundwork` command removed; reports, `report.json`, and the integration `cache.json` remain | `cache.json` and `report.json` are not named in the uninstall header (NICE TO HAVE) |
| Work / personal separation | PASS, with a limit | Installing with `--profile work` and `--profile personal` produces the same file set and differs in one settings value, `env.GROUNDWORK_PROFILE`. Code search: the value is only recorded (telemetry, snapshot header, update re-pass), never used to enable or disable anything | The profile is a **label**, not an enforcement. Separation between a company and a personal setup comes from using separate machines or `HOME` directories. The programme installed no community code anywhere and ships no mod |
| Permissions | PASS | The merged settings add no `permissions.allow` entry and no bypass mode; code search of `hooks/`, `scripts/`, `setup.sh`, `install.sh` finds `--permission-mode dontAsk` with an explicit `--allowedTools` list only in the existing Routines runner and no `--dangerously-skip-permissions`. Copilot runs `claude -p --safe-mode --tools ""` | Routines were not changed by this programme and were not re-reviewed here |
| Mod security | PASS (no mod used) | #45 is documentation only. No mod was installed, run, or downloaded in executable form; five mods were read as source at pinned commits. The finding that matters is in `docs/CLAUDE-MODS.md` of #45: a mod runs before non-managed `PreToolUse` hooks and can approve a call such a hook blocked, so Groundwork's push guard and review gate do not bind an installed mod | Behaviour of any mod at runtime: needs the owner's disposable machine |
| Prompt injection / untrusted output | PASS for what is deterministic | Copilot has no tools and cannot run what the terminal text suggests (`test_live_containment`, `test_project_facts_are_untrusted`); evidence receipt treats transcript text as data (a forged `REVIEW RESULT` inside a tool result is not accepted: `test_review_parsing`, `test_round3_regressions`); redacted text is cut after redaction | What a model does with injected text in its answer. Containment rests on "no tools, no execution", not on the model refusing |
| Secrets and telemetry privacy | PASS | Redaction tests for both modules (`test_redaction_review_findings`, `test_redaction_and_terminal_safety`); the installed Stop hook run on this session's real 111 MB transcript wrote a 0600 record holding tool names, counts, a hashed working directory and the label, with no command text, path or file content; added lines of all branches searched for personal paths, e-mail addresses, session URLs and token shapes: one hit, an absolute container path in an OpenSpec design record (NICE TO HAVE, below), plus test fixtures that deliberately look like secrets | GitHub push protection rejected an earlier push of AWS-shaped test fixtures; they are now built at run time. The unblock URL was not used |
| Multi-session isolation | PASS | Copilot binds to its own tmux pane by tty and process ancestry; a real two-pane tmux test shows each pane's question answered from that pane only (`test_real_tmux_two_panes`); evidence defaults to the current session's transcript and ignores sub-agent transcripts (`test_cli_default_transcript_scope`, `test_sidechain_and_collect_cap`); investigation notes are keyed per repository | Terminals other than tmux, and macOS: `RUNTIME VALIDATION REQUIRED` (none available here) |
| Loop termination | PASS | Autoship runs on a disposable fixture ended three different ways: success after a review finding was fixed, BLOCKED when a test contradicted the spec, and a budget cap that was overshot (USD 0.109 against 0.05). Official docs: a Stop hook is overridden after 8 consecutive blocks; `--max-budget-usd` can be overshot by a turn | The Groundwork review gate blocking inside a loop was not exercised |
| Real operational behaviour | PASS | Installed Stop hook on the 111 MB transcript: exit 0 in 0.07 s, 25 MB peak memory; `groundwork evidence` 0.32 s on the same transcript; snapshot hook about 0.14 s; Copilot dry run 0.06 s; one real model call from Copilot on a genuine traceback worked | macOS terminals, voice, `acli`, a real tool abort event |
| Resource use and complexity | NOTE | Shipped code added by the programme is about 2,170 lines: #47 994, #49 628, #43 254, #46 208, #42 54, #41 31; about 3,170 lines of tests. #47 is the largest piece and nothing gates on its output | Whether #47's size is justified by its value is an owner decision (see below) |

## Result per milestone against the brief

| Milestone | State | Why |
|---|---|---|
| 1a #43, 1b #41, 1c #42 | COMPLETE | reproduced, fixed, independently reviewed, confirmation review 0 MUST FIX; #41 awaits an owner decision (below) |
| 2 Claude mods | PARTIAL | static review only; no runtime trial |
| 3 Evidence receipt #47 | BUILT; fresh confirmation reviews (security and correctness) of the latest head pending when this was written | final mutation set: 55 of 55 caught |
| 4 Copilot #49 | BUILT; fresh confirmation review of the latest head pending when this was written | mutation runner: every non-equivalent mutant caught; one mutant classed equivalent, with its reason |
| 5 Hands-Free SRE | NOT NEEDED as code; demonstration BLOCKED | native `/voice` covers voice input, cancel and approval; no microphone here |
| 6 Autoship | NOT NEEDED as code | `/goal`, `claude -p`, `--max-budget-usd`, `--allowedTools` and the review gate already give a bounded loop; the required multi-step demonstration with a failing test, a fix, an independent review and a passing re-run was observed |
| 7 SmartMemory #46 | BUILT; fresh confirmation review of the latest head pending when this was written | the reproducible gap (unpushed work in sibling worktrees never mentioned) is closed by one bounded snapshot section; no new memory system |
| 8 This audit | COMPLETE as an audit; no RC | gates above |

## Open gates

1. **Reviews.** Fresh confirmation reviews of #47, #49 and #46 had not returned when this was written. A phase is cleared only by a fresh review reporting `Must-fix: 0`; until then it is not complete, whatever the tests show.
2. **Owner decisions.** Keep or close #41 (Jira is reached by browser in the owner's setup); whether to run the
   mods trial on a disposable machine; whether #47's 994 lines are worth an estimate that gates nothing; judging
   the evidence labels on sessions the owner knows.
3. **Runtime on the owner's platform.** macOS terminals, `/voice`, `acli`, and `groundwork update` to a release
   that contains these changes were not run.

## Findings carried forward

NICE TO HAVE
- Absolute container path in `openspec/changes/add-evidence-receipt/design.md` (`/root/.claude/projects/…`); use `~`.
- `setup.sh --verify` checks a fixed list of four hook files and at least four registered entries (`setup.sh:644`); it does not notice the extra hook file added by #47 or the two entries added by #43.
- Telemetry `events.jsonl` has no rotation.
- `uninstall.sh` header does not list `cache.json` or `report.json` as kept files.
- `groundwork_routines.py` accepts `gh auth status` exit code 0 alone as connected; the integration catalog rejects that signal.
- Statusline configuration keys are not documented in a README or docs page.
- `groundwork_copilot.py` and `groundwork_evidence.py` keep separate redaction patterns.
- `docs/VALIDATION.md` states that every git call of the snapshot hook is bounded by the new deadline; only the worktree section is.
- The snapshot hook hides some errors behind `try/except: pass`; one deleted constant was found only by an older test.
- Background-agent review results arrive as later messages and are not credited by the evidence receipt.

NOT VERIFIED
- Any behaviour on macOS, with a microphone, with a real `acli`, with a real tool abort, or with an installed mod.
- The real ECC install path with this tree (stubbed here on purpose).

## Merge order and conflicts

Merging is the owner's step. `CHANGELOG.md` conflicts between nearly all branches under `## Unreleased`.
#47 and #49 also conflict in `scripts/groundwork_cli.py`, `tests/test_groundwork_cli.py`, the README,
`docs/ARCHITECTURE.md` and `uninstall.sh`. Both additions are needed (two sub-commands, two tests, two
file lists); take both sides by hand, not with an automatic "keep both", which produced invalid Python and a
garbled `uninstall.sh` header in the scratch merge.

## Reproduce

```bash
git worktree add ../groundwork-audit-merge -b audit/integration-scratch origin/main
# merge the nine branches in the table above; resolve the conflicts named above by hand
python3 -m pytest tests -q
openspec validate --all --strict
# sandbox: use a throwaway HOME that already holds a settings.json, then
HOME=$SANDBOX ./setup.sh --non-interactive --profile personal --no-agent-teams --schedule disabled --no-install-prereqs
HOME=$SANDBOX ./setup.sh --rollback <backup dir printed by the first run>
HOME=$SANDBOX ./uninstall.sh
```

## Release readiness

Not ready. A release candidate and release notes are to be prepared only after the open gates are closed and the
owner has authorised a release; no release was or will be published by this programme without that.
