## Why

Groundwork's product vision (R1–R9, stated by the owner on 2026-10-13) asks for one experience: an engineer gives a loosely defined task, such as `COR-123: Deploy GoldenGate VM in GCP`, and Claude Code plans it, executes it safely, verifies it, gets it reviewed, tracks it and resumes it later with little supervision.

Most of that loop already exists. Rules, playbooks, hooks, the Integration Catalog, the statusLine, telemetry, Routines and Copilot are released in 2.4.0. M1 task tracking (intake, native OpenSpec plan, `ask` for sensitive actions, evidence-based completion and continuity) is merged to `main` but not released.

Existing records show five gaps that block the vision:
- M1 has not reached users. It also has reproduced bypasses in its own authorization check.
- There are no estimates, dependencies or prioritisation across tasks.
- The statusLine shows no task state. Integration readiness is not tied to the task at hand.
- ECC adds about 40.6K always-on tokens. On a trivial task it doubled the measured cost ($0.21 to $0.41). It also makes the install abort if ECC fails to install. Groundwork's own code does not require ECC.
- Nothing measures Groundwork against Claude Code alone.

This change is the plan that closes those gaps with the fewest new parts. It is planning only. Implementation starts only after the owner approves it.

## What Changes

The milestones are in the recommended order. Each one ships as its own release, using the existing release, update and rollback process.

- **M0. Reconcile `main` with the released 2.4.0 (docs only).**
  - Bring the 2.4.0 CHANGELOG section and the release report from the `v2.4.0` tag into `main`.
  - Remove the nonexistent `groundwork report schedule` command from them.
  - This is a prerequisite for M1: `install.sh` and `groundwork update` read the version from the top CHANGELOG heading.
- **M1. Release task tracking (proposed 2.5.0).**
  - Ship the merged M1 behaviour unchanged in scope.
  - Fix the security findings from the Claude Security scan on 2026-10-12:
    - task-gate bypasses (F7, F8, F11, F12);
    - push-guard bypasses (F4, F5, F6, F10);
    - settings.json losing its owner-only mode (F13);
    - routines' broad `Bash(git *)` grant and the `news` routine's web grant (F1–F3);
    - the quadratic snapshot regex (F9).
  - Fix `groundwork routines schedule` not saving the time. This bug affects the 2.4.0 macOS upgrade instructions.
  - Validate the release on a real install, upgrade, rollback and a live `claude -p` acceptance run. Then archive `add-task-lifecycle-gate`, so `task-lifecycle` enters the main specs.
  - Follow the release with a short owner pilot on real work.
- **E. Make ECC optional (owner decision; recommended between M1 and M2).**
  - Groundwork stops depending on ECC.
  - New installs ask whether to install ECC. Existing installs keep it.
  - An ECC install failure no longer aborts the install, and a missing ECC no longer fails `--verify`.
  - The rules name native subagents and review commands first, and ECC agents only "when installed".
  - The `--no-verify` block moves into Groundwork's existing task gate. The GateGuard "investigate before edit" hook stops being listed as an enforced control and stays as rule guidance.
  - ECC itself is not modified.
- **M2. Intelligent task planning.**
  - Planning facts live in the native OpenSpec plan, in one `## Planning` section: an estimate with range and confidence, `Depends on` task keys, and priority.
  - Groundwork reads that section the same way it reads `## Verification` today.
  - Several keyed tasks in one prompt are recorded separately.
  - A deterministic `groundwork task next` explains which task is ready and why.
  - MATERIAL intake guidance asks Claude to record prerequisites, analogous implementations and genuine blockers in the plan.
- **M3. Integrated developer experience.**
  - The statusLine shows the current task: key, phase, progress and review state.
  - MATERIAL intake names the catalog integrations relevant to the task and their cached readiness, as guidance only.
  - Two dashboard readability defects are fixed: clipped labels and unsorted rows.
- **R9 evaluation (cross-cutting).**
  - A small, repeatable comparison with and without Groundwork on three reference tasks, with the same model and environment.
  - It runs at M1 and again after M2 and M3.
  - Results are reported as observed, with sample size and variance stated.

None of these is a breaking change. Every new behaviour reads existing state, adds guidance, or can be switched off with an existing kill switch or statusLine setting.

## Capabilities

### New Capabilities
- `task-planning`: planning facts in the native OpenSpec plan (estimate, dependencies, priority), readiness, deterministic prioritisation across tasks, multi-task intake, and planning guidance at intake.

### Modified Capabilities
- `groundwork-statusline`: adds a current-task segment read from the local task ledger.
- `integration-catalog`: adds task-relevant integration hints at MATERIAL intake, read from the existing readiness cache.

Not changed here:
- M1 hardening fixes defects against requirements that already exist in `add-task-lifecycle-gate`.
- The ECC spec delta (`ecc-capability-policy`) is written as E's first task, after the owner chooses the option and after `groundwork-2-enterprise-sre` is archived. That capability lives in that change today.

## Impact

- **Code (later, on approval):**
  - `hooks/groundwork_tasks.py` and `hooks/groundwork_task_gate.py` (M1 hardening, M2, M3 intake hints);
  - `hooks/block_protected_push.py`, `scripts/merge_settings.py`, `scripts/groundwork_routines.py` and `hooks/groundwork_session_snapshot.py` (M1);
  - `scripts/groundwork_statusline.py` and `scripts/groundwork_report.py` (M3);
  - `install.sh`, `setup.sh`, `scripts/merge_settings.py` and `rules/engineering-workflow.md` (E);
  - tests next to each.
- **Docs:**
  - CHANGELOG, release reports, `docs/TASK-LIFECYCLE.md` and `docs/ARCHITECTURE.md` (the enforced-controls table);
  - README and `docs/FUTURE-SCOPE.md` (stale items).
- **Dependencies:** none new. Python standard library, the installed OpenSpec CLI and Claude Code only. No network calls in hooks. No paid services.
- **Users:** each milestone is opt-out or read-only, and is reversible with `groundwork rollback`. E changes only the default for new installs and never removes ECC from an existing install.
