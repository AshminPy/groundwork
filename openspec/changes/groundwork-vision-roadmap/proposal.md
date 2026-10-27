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

The milestones are in the recommended order. Each one ships as its own release, using the existing release, update and rollback process. Work in every milestone falls into one of three classes (design D10):
- **release-critical** work blocks that milestone's release;
- **product-critical** work is planned in the milestone but moves to the next release if it is not ready;
- **optional** work never blocks anything.

- **M0. Reconcile `main` with the released 2.4.0 (docs only, minimal).**
  - Bring the 2.4.0 CHANGELOG section and the release report from the `v2.4.0` tag into `main`, and remove the released macOS entry, with its nonexistent `groundwork report schedule` command, from Unreleased.
  - Verify that version behaviour is unchanged. `install.sh` and `groundwork update` both take the first `## x.y.z` CHANGELOG heading as the version, so it must still read 2.4.0, and every released section must match the tag.
  - Nothing else goes into M0.
- **M1. Release task tracking (proposed 2.5.0).**
  - Ship the merged M1 behaviour unchanged in scope.
  - Apply severity- and evidence-based release criteria to the Claude Security findings of 2026-10-12 (design D2):
    - **Release blockers**, fixed before release: every finding reproduced at runtime (F4, F5, F6, F7, F8, F12, F13), and every MEDIUM-or-higher finding that the full panel confirmed with at least medium confidence (F1, F2).
    - **Not blockers:** F3, F9, F10 and F11 are fixed in the release when ready, because they sit in code the release already changes or next to it. F14 is deferred, with a written justification.
  - Fix `groundwork routines schedule` not saving the time (product-critical).
  - Validate the release on a real install, upgrade, rollback and a live `claude -p` acceptance run. Then archive `add-task-lifecycle-gate`, so `task-lifecycle` enters the main specs.
  - An owner pilot on real work starts when 2.5.0 is published. It has no fixed duration and blocks nothing except M2's merge.
- **E. Make ECC optional (recommended between M1 and M2).**
  - Groundwork stops depending on ECC.
  - An ECC install failure no longer aborts the install, and a missing ECC no longer fails `--verify`. Existing installs keep ECC.
  - **The default for new installs stays undecided** until the R9 baseline compares Groundwork with and without ECC. The owner then picks it.
  - The rules name native subagents and review commands first, and ECC agents only "when installed".
  - Groundwork's task gate keeps `--no-verify` hard-blocked, with or without ECC. Replacing the block with `ask` would be a security-policy change. It needs explicit owner approval and its own validation, and it is not part of this plan.
  - For installs without ECC, GateGuard's "investigate before edit" stop becomes rule guidance. The owner approves this together with the ECC default.
  - ECC itself is not modified.
- **M2. Intelligent task planning.**
  - Development may start on its own branch once 2.5.0 is published, during the pilot. It merges only after the relevant pilot findings are fixed or explicitly deferred.
  - Planning facts live in the native OpenSpec plan, in one `## Planning` section: an estimate with range and confidence, `Depends on` task keys, and priority.
  - Groundwork reads that section the same way it reads `## Verification` today.
  - Several keyed tasks in one prompt are recorded separately.
  - A deterministic `groundwork task next` explains which task is ready and why.
  - MATERIAL intake guidance asks Claude to record prerequisites, analogous implementations and genuine blockers in the plan.
- **M3. Integrated developer experience.**
  - The statusLine shows the current task: key, phase, progress and review state.
  - MATERIAL intake names the catalog integrations relevant to the task and their cached readiness, as guidance only.
  - Optional: two dashboard readability defects (clipped labels, unsorted rows). They never block the M3 release.
- **R9 evaluation (cross-cutting).**
  - A small, repeatable comparison with and without Groundwork on three reference tasks, with the same model and environment.
  - It runs at M1 and again after M2 and M3.
  - Every run has a hard spending cap, so the maximum cost is stated before the owner is asked to authorize it (design D7).
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
