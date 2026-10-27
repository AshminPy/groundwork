# Groundwork: end-to-end architecture (as built, 2.5.0) and the next two changes

*   **Author:** AshminPy (drafted with Claude Code)
*   **Status:** In Review
*   **Date:** 2026-10-27
*   **Code baseline:** `main` at `ccc807e` (Groundwork 2.5.0 plus PR #72)

--------------------------------------------------------------------------------

## Overview

Groundwork is an add-on for Claude Code. It aims to make every answer accurate, backed by
evidence, and cheap in tokens. It has three parts:

1.  **Rules** that Claude Code loads into every request (`rules/*.md`, installed to
    `<config>/rules/groundwork/`), plus ten **playbooks** that Claude reads only when a task
    needs one (`playbooks/*.md`, installed to `<config>/groundwork/playbooks/`).
2.  **Hooks**: Python scripts that Claude Code runs on its own events (`hooks/*.py`,
    registered in `<config>/settings.json` by `scripts/merge_settings.py`). Hooks enforce
    what the rules can only ask for.
3.  **Scripts and state**: a `groundwork` CLI, an updater, a status line, a report
    generator, scheduled routines, and files under `<config>/groundwork/`.

`<config>` means `$CLAUDE_CONFIG_DIR` when set, else `~/.claude`.

Groundwork sits on top of two other tools that it installs:
*   **ECC** (`ecc@ecc` Claude Code plugin, pinned to `v2.2.1`, `install.sh:65-73`):
    agents, skills and its own hooks.
*   **OpenSpec** (npm CLI, `install.sh:81`): spec files per repository for larger changes.

This document describes the system as it is built today. It then plans the next two
changes, both found by the 2.5.0 benchmark
(https://claude.ai/artifact/QKxahqihaPhNsgcRwYDb4f): install portability (change A) and
context cost (change B).

## The Problem

Plain Claude Code answers correctly most of the time, but it does not reliably:
*   show evidence (links, `file:line`) for its claims;
*   say honestly what was and was not verified;
*   keep the task's goal and decisions across compaction and new sessions;
*   ask before risky actions such as pushes to `main` or cloud changes.

Rules alone did not fix this: 31 of 51 tool-using turns in this repository lacked the
required metadata block when only rules asked for it (PR #66). So Groundwork moves every
check that can be made deterministic into a hook.

The 2.5.0 benchmark (20 questions, Groundwork arm "G" vs plain Claude Code "V") showed:
*   both arms 20/20 correct;
*   G cited 41% more sources and had an evidence section in 18/20 answers (V: 1/20);
*   G cost about 58k more input tokens per answer (median 79k vs 21k), and its median
    answer took 20.2 s instead of 15.7 s;
*   two defects: the Stop hooks stayed silent without a transcript (fixed in PR #72), and
    the install assumed `~/.claude` (change A below).

## Goals

*   **G1 Evidence:** every tool-using reply has an evidence section with at least one link
    or `file:line`, checked by a hook. Measure: share of benchmark answers with the section
    (currently 18/20).
*   **G2 Honest status:** every tool-using reply states what was verified. Measure:
    `HARNESS METADATA` present (currently 20/20 in the benchmark).
*   **G3 Continuity:** the task's goal, decisions and next step survive compaction and new
    sessions without Claude having to remember to save them.
*   **G4 Safety:** pushes to protected branches are denied. Cloud, cluster, production,
    destructive and credential actions ask the owner first.
*   **G5 Cost:** Groundwork's added input tokens per request go down (change B targets the
    rule text, the largest share Groundwork owns).
*   **G6 Portability:** install works on any macOS or Linux laptop, in any config folder,
    with no API key (Claude subscription only).

## Non-Goals

*   Replacing Claude Code, ECC or OpenSpec. Groundwork adds checks around them.
*   A sandbox. Hooks are not a security boundary against a process run by the same user.
*   A separate agent runtime. A LangGraph orchestrator was built and parked: it scored
    39/40 vs 40/40, was slower and used 52% more output tokens. Its code lives only on
    branches `feat/m2-engine`, `feat/m2-question-evidence`, `bench/vanilla-vs-groundwork`.
*   Checking every citation's content. A free-text citation checker flagged 6 issues in
    852 citations, all 6 false (PR #63), so it was rejected.
*   Windows support.

## Open Questions

*   **Q1 Which context cost does Groundwork own?** On the owner's Mac, every request loads
    Groundwork's rules (50,339 bytes), the owner's own `~/.claude/rules/*.md` and
    `CLAUDE.md` (39,465 bytes, some of it says it is superseded by Groundwork's output
    contract), and ECC's skill and agent listings (ECC share not yet measured). Change B
    shrinks only Groundwork's rules. Should Groundwork also warn about duplicate user rules?
*   **Q2 Hook firing on progress messages.** The reply check runs on every Stop, so it also
    asks for evidence sections on a short progress note sent while a background subagent
    is still working (seen on 2026-10-27 in this session). Should it skip turns that only
    launched background work?
*   **Q3 Telemetry growth.** `events.jsonl` and `tool_events.jsonl` are never pruned. One
    row is written per tool call. What retention is acceptable?
*   **Q4 Status line ownership.** Groundwork sets `statusLine` only when none exists
    (`scripts/merge_settings.py:305-307`). On the owner's Mac another tool owns it, so
    usage tracking records nothing. Accept, or offer a wrapper?

## Critical User Journeys (CUJs)

### CUJ 1: Install on a new laptop

*   **Given**: macOS or Linux, Claude Code installed and logged in, Node 20.19+, Python 3.10+.
*   **When**: the user runs `./setup.sh` (or `install.sh`), optionally with
    `CLAUDE_CONFIG_DIR` set to a non-default folder.
*   **Then**: rules, playbooks, hooks and scripts are copied into `<config>`;
    `settings.json` gets 15 hook entries pointing at the hook files that were copied;
    `setup.sh --verify` reports every Groundwork hook as present and registered;
    a second install in a different `<config>` does not replace the first one's
    scheduled report job.

### CUJ 2: A tool-using answer

*   **Given**: Groundwork installed.
*   **When**: the user asks a question and Claude runs tools to answer it.
*   **Then**: at prompt time the reply check adds a format reminder and the matching
    playbook's output format; at Stop, if the reply lacks `Technical details`,
    `Evidence & references` (with a link or `file:line`) or `HARNESS METADATA`, the hook
    blocks once and Claude adds only the missing parts. This works with and without a
    saved transcript.

### CUJ 3: Compaction and a new session

*   **Given**: work in progress on a branch.
*   **When**: compaction runs (manual or automatic), or a new session starts.
*   **Then**: PreCompact refreshes the brief's Snapshot section; SessionStart injects the
    brief for this repository and branch (Next step first, at most 2400 chars) and the
    project snapshot (git, OpenSpec, task ledger, investigation file, at most 2500 + 700
    chars).

### CUJ 4: A risky action

*   **Given**: a session in any repository.
*   **When**: Claude runs `git push origin main`, a cloud write, or an edit of
    `settings.json`.
*   **Then**: the push is denied (`block_protected_push.py`); the other actions get
    Claude Code's native `ask` permission prompt (`groundwork_task_gate.py`).

### CUJ 5: MATERIAL work is finished

*   **Given**: an OpenSpec change in the repository with every task checked.
*   **When**: Claude tries to end its turn without an independent review, or the latest
    review reports MUST FIX findings.
*   **Then**: `require_material_review.py` blocks the Stop until a review reports
    `Must-fix: 0`.

## Technical Plan (Architecture)

### Components

```text
                         ┌──────────────────────── Claude Code (runtime) ───────────────────────┐
  user prompt ─────────▶ │ loads <config>/rules/**/*.md every request (Groundwork 50 KB + user) │
                         │ loads plugins: ECC (agents, skills, its own hooks)                    │
                         │ runs hooks from <config>/settings.json on each event ────────┐        │
                         └──────────────────────────────────────────────────────────────┼────────┘
                                                                                        │
   SessionStart ── session_snapshot (git/OpenSpec/tasks/investigation facts) ──▶ context│
                └─ brief (branch brief + last decisions)                       ──▶ context│
   UserPromptSubmit ─ task_gate (task intake, may run `openspec new change`)    ──▶ context│
                    └ reply_check (format reminder + playbook format; marks turn) ─▶ context│
   PreToolUse ─ block_protected_push (Bash: deny protected/force push)                    │
              └ task_gate (any tool: `ask` for sensitive actions, deny ledger edits)      │
   PostToolUse / Failure ─ telemetry (1 row per call) · task_gate (evidence)               │
   PreCompact ─ brief (refresh Snapshot section)                                          │
   Stop ─ require_material_review (block until review Must-fix 0)                         │
        ─ reply_check (block once if evidence/metadata missing)                           │
        ─ brief (snapshot; ask once for Goal/Next step or evidence)                       │
        ─ telemetry (1 row per turn)                                                      │
                                                                                        ▼
  <config>/groundwork/  telemetry/*.jsonl · briefs/<repo>/<branch>-<sha8>.md (+ .decisions.md)
                        tasks/<repo>/<KEY>.json · investigations/<repo>.md · state/turns/*.json
                        reports/ · routines/results/ · bin/ (CLI, scripts) · playbooks/ · VERSION
```

### Context layer (paid on every request)

| File | Bytes | Owns |
|---|---|---|
| `rules/engineering-workflow.md` | 24,046 | tiers, execution order, completion facts, autonomy, execution model, continuation |
| `rules/output-contract.md` | 11,170 | reply shape, checklist style, metadata block, review block |
| `rules/evidence-policy.md` | 6,924 | evidence priority, labels, DECISION record, validation ladder |
| `rules/task-routing.md` | 4,909 | ten categories, pick one playbook |
| `rules/architecture-quality.md` | 3,290 | design criteria |

Playbooks (25,497 bytes in total, 1.8–3.6 KB each) load only on demand. The reply check
injects only the chosen playbook's "Output Format" section at prompt time
(`hooks/groundwork_reply_check.py:145-159`).

### Hooks (15 registered entries, `scripts/merge_settings.py:50-80,235-260`)

| Hook file | Events | Can block? | Writes |
|---|---|---|---|
| `block_protected_push.py` | PreToolUse (Bash) | deny | nothing |
| `groundwork_task_gate.py` | UserPromptSubmit, PreToolUse (all), PostToolUse (all), PostToolUseFailure (Bash) | `ask`; deny on ledger edits | `tasks/<repo>/<KEY>.json`; may create `openspec/` in the repo |
| `require_material_review.py` | Stop | block (no `stop_hook_active` check) | nothing |
| `groundwork_reply_check.py` | UserPromptSubmit, Stop | block once | `state/turns/<sid>.json` |
| `groundwork_brief.py` | SessionStart, PreCompact, Stop | block once per kind per session | `briefs/…` |
| `groundwork_session_snapshot.py` | SessionStart | no | nothing |
| `groundwork_telemetry.py` | Stop, PostToolUse, PostToolUseFailure | never | `telemetry/events.jsonl`, `tool_events.jsonl` (0600) |

Every hook fails open: a crash, bad input or missing file means no output and exit 0.
The one exception: `groundwork_task_gate.py` turns an internal error during PreToolUse
into `ask`, so a broken check never silently allows a sensitive action.

`groundwork_shared.py` and `groundwork_tasks.py` are libraries, not hooks.

### Data flows that cross hooks

*   **Turn tools without a transcript** (PR #72): reply check writes
    `state/turns/<sid>.json` at UserPromptSubmit; at Stop, the reply check and brief read
    this session's `tool_events.jsonl` rows newer than that time.
*   **Brief evidence ask**: brief reads `events.jsonl` to decide when to ask for an empty
    brief.
*   **Snapshot ← task ledger and investigations**: the snapshot reads files other hooks or
    Claude wrote.

### Scripts

*   `groundwork` CLI (`scripts/groundwork_cli.py`): version, doctor, integrations, update,
    rollback, routines, statusline, usage, copilot, task.
*   `groundwork update` (`scripts/groundwork_update.py`): installs only published GitHub
    Releases, checks the CHANGELOG version matches the tag, runs the release's
    `setup.sh --non-interactive`.
*   Report (`scripts/groundwork_report.py`): dashboard and dated snapshots from telemetry;
    scheduled with launchd label `com.groundwork.report` (`:43`).
*   Routines (`scripts/groundwork_routines.py`): six scheduled `claude -p` jobs, launchd
    labels `com.groundwork.routine.<name>` (`:58`).
*   Status line (`scripts/groundwork_statusline.py`): reads Claude Code's status-line JSON;
    writes `telemetry/usage.jsonl` (trimmed to 8 days once over 1 MB).

## Alternatives Considered

### Alternative A: Rules only, no hooks

*   **Pros**: zero runtime cost, no Python.
*   **Cons**: Claude skips rules under load. 31/51 tool turns lacked metadata (PR #66).
*   **Reason for Rejection**: measured failure.

### Alternative B: Separate LangGraph orchestrator around Claude Code

*   **Pros**: explicit state machine, checkpoints.
*   **Cons**: 39/40 vs 40/40 correct, slower, +52% output tokens
    (`orchestrator/bench/results/m2-comparison.md:12` on `feat/m2-question-evidence`).
*   **Reason for Rejection**: worse on every measured axis.

### Alternative C: Full citation checker at Stop

*   **Pros**: catches wrong links.
*   **Cons**: 852 citations, 0 real errors, 6/6 flags false (PR #63).
*   **Reason for Rejection**: only false positives.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security & Privacy**: telemetry never reads `tool_input` or `tool_response`; files are
    0600 in 0700 folders. Snapshot and brief text is framed as data, not instructions.
    Hooks are not a sandbox (Non-Goals).
*   **Performance & Latency**: each tool call starts two Python processes (telemetry and
    task gate, about 35 ms each, measured for telemetry). Each Stop starts four. Every
    request pays the rule text (50,339 bytes, about 12.6k tokens).
*   **Rollout & Rollback**: `groundwork update` installs a published release only;
    `setup.sh --rollback` restores the newest backup made by `setup.sh`.

--------------------------------------------------------------------------------

### Additional Resources

*   `README.md`, `docs/ARCHITECTURE.md`, `docs/TASK-LIFECYCLE.md`, `docs/ROUTINES.md`
*   `docs/RELEASE-REPORT-2.5.md`
*   Benchmark report: https://claude.ai/artifact/QKxahqihaPhNsgcRwYDb4f
*   Claude Code hooks reference: https://code.claude.com/docs/en/hooks

### Future Improvements

*   **Doc drift**: `docs/ARCHITECTURE.md:26-31` says four hooks and `README.md:220` says
    five; the code registers seven hook files. `setup.sh --verify` checks only six files
    and four events (`setup.sh:614,642-643`). Fix with a single source of truth for the
    hook list.
*   **Telemetry retention** (Q3).
*   **Uninstall** leaves `state/`, `routines/`, `integrations/`, `report.json` and
    `statusline-config.json` behind without saying so (`uninstall.sh:131-137`).

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Two independent changes, each its own branch and pull request from `main`, test-first.

### Change A: install works in any config folder

Problem: `install.sh` copies hooks to `$CLAUDE_DIR/hooks/` (`install.sh:91`) and calls
`merge_settings.py "$CLAUDE_DIR/settings.json"` (`install.sh:196`), but every hook command
is the constant `python3 ~/.claude/hooks/<name>.py` (`scripts/merge_settings.py:50-80`),
and the status line is `python3 ~/.claude/groundwork/bin/groundwork_statusline.py`. With
`CLAUDE_CONFIG_DIR=/other`, the registered hooks run the files in `~/.claude` (or nothing).
The report's launchd label is the constant `com.groundwork.report`
(`scripts/groundwork_report.py:43`), so two installs replace each other's job.

#### 1. `scripts/merge_settings.py` (Modify)

*   **Type / Scope**: Python script.
*   **Proposed Changes**:
    *   Add `def hook_root(settings_path: Path) -> str`: returns `"~/.claude"` when
        `settings_path.parent.resolve() == Path("~/.claude").expanduser().resolve()`,
        otherwise the absolute, `shlex.quote`d path of `settings_path.parent`.
    *   Replace each `*_CMD` constant with `def cmd(root: str, rel: str) -> str` returning
        `f"python3 {root}/{rel}"`; `merge(data, …, root="~/.claude")` builds all 15 hook
        commands and the status line from `root`.
    *   Default `root` keeps the exact old strings, so re-running on an existing default
        install changes nothing.

#### 2. `scripts/unmerge_settings.py` (Modify)

*   **Type / Scope**: Python script.
*   **Proposed Changes**: compute the same commands with the same `hook_root()` (import it
    from `merge_settings`), and also remove the legacy `~/.claude/...` strings, so an
    uninstall cleans both forms.

#### 3. `scripts/groundwork_report.py` and `scripts/groundwork_routines.py` (Modify)

*   **Type / Scope**: Python scripts.
*   **Proposed Changes**: add `def label_suffix() -> str` in `groundwork_report.py`:
    `""` for the default config folder, else `"." + sha256(str(config_dir().resolve()))[:8]`.
    `LABEL` becomes `"com.groundwork.report" + label_suffix()`; routines use
    `f"{LABEL_PREFIX}{label_suffix()}.{name}"`. The plist file name follows the label.

#### 4. `uninstall.sh` (Modify)

*   **Type / Scope**: Shell.
*   **Proposed Changes**: boot out and delete the labels with this config folder's suffix
    (computed by calling the installed `groundwork_report.py`), not every
    `com.groundwork.*` job, so uninstalling one folder never removes another's jobs.

#### 5. `setup.sh` (Modify)

*   **Type / Scope**: Shell.
*   **Proposed Changes**: `--verify` checks all seven hook files plus `groundwork_shared.py`
    and counts registered entries for all six events used (PreToolUse, PostToolUse,
    PostToolUseFailure, Stop, SessionStart, UserPromptSubmit, PreCompact).

#### 6. Tests (Modify `tests/test_setup.py`, `tests/test_report.py`, add cases to `tests/test_hooks.py`)

*   **Proposed Changes**:
    *   merge into `/tmp/x/settings.json` → every command starts with `python3 /tmp/x/`;
        merge into the default path → commands byte-identical to 2.5.0.
    *   unmerge removes both forms.
    *   two config folders → two different labels; default folder → `com.groundwork.report`.
    *   `install.sh` with `CLAUDE_CONFIG_DIR` set to a temp folder, then run each registered
        hook command with a SessionStart payload → exit 0 and the file executed is the one
        in the temp folder.

### Change B: smaller always-loaded rules

Problem: 50,339 bytes of Groundwork rules load on every request. The hooks now enforce the
reply shape (reply check), continuity (brief, snapshot), push safety and review, so much
rule text repeats what a hook already checks.

#### 1. `rules/*.md` (Modify)

*   **Type / Scope**: Markdown rules.
*   **Proposed Changes**: keep in always-loaded rules only what Claude must decide on every
    request: tier choice, evidence labels, the autonomy and ask triggers, the reply shape
    in one short list, and a pointer to the reference files. Target: at most 15,000 bytes
    in total across `rules/`.

#### 2. `reference/` (Create; installed to `<config>/groundwork/reference/`)

*   **Type / Scope**: Markdown, read on demand like playbooks.
*   **Proposed Changes**: move the rest, without changing meaning:
    `reference/workflow-detail.md` (execution order detail, execution model, capability
    resolution, continuation), `reference/output-detail.md` (checklist style, layers,
    review block), `reference/evidence-detail.md` (DECISION record, validation ladder,
    RCA rule). Each playbook names which reference file to read for its category.

#### 3. `install.sh`, `uninstall.sh`, `setup.sh --verify` (Modify)

*   **Proposed Changes**: copy, remove and count `reference/*.md`.

#### 4. Hooks that quote rule section names (Modify if needed)

*   **Proposed Changes**: `hooks/groundwork_reply_check.py`, `groundwork_brief.py`,
    `require_material_review.py`, `groundwork_telemetry.py`,
    `groundwork_session_snapshot.py`, `scripts/groundwork_routines.py` and
    `scripts/migrate_legacy_rules.py` mention `engineering-workflow.md` or
    `output-contract.md`; update any text that points to a moved section.

#### 5. Tests (Modify `tests/test_playbooks.py`, `tests/test_hooks.py`)

*   **Proposed Changes**: assert total `rules/*.md` size ≤ 15,000 bytes; assert every
    phrase the existing tests require still exists in `rules/` or `reference/`; assert each
    playbook names an existing reference file.

### Verification Plan

*   **Unit Tests**: `python3 -m pytest tests -q` (160 passed at baseline `ccc807e`).
*   **Static checks**: `bash -n install.sh setup.sh uninstall.sh`.
*   **Install, change A**: `CLAUDE_CONFIG_DIR=$(mktemp -d) ./install.sh` followed by
    `setup.sh --verify` against that folder → all hooks PASS; one `claude -p` session in that
    folder shows the SessionStart snapshot.
*   **Benchmark, change B**: re-run the 20-question suite (`orchestrator/bench`, branch
    `bench/vanilla-vs-groundwork`) for G vs V. Pass when correctness stays 20/20, the
    evidence section stays ≥ 18/20, and the first-request input tokens drop by at least
    the removed rule bytes ÷ 4.

--------------------------------------------------------------------------------

*Drafted with EGM template*
