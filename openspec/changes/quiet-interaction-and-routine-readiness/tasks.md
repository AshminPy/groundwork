# Tasks — Quiet interaction + routine readiness

## 1. Quiet interaction
- [x] 1.1 Re-verify current official Claude Code docs for `outputStyle` settings.json syntax and Concise style behavior (done in design.md DECISION 1; confirm no change since)
- [x] 1.2 Extend `rules/output-contract.md` with the mid-turn quiet-narration principle, preserving every named carve-out
- [x] 1.3 Add `outputStyle: "Concise"` additive merge to `scripts/merge_settings.py` (set only if absent)
- [x] 1.4 Add symmetric removal to `scripts/unmerge_settings.py` (remove only when a sidecar ownership record confirms Groundwork itself set the value AND it still matches — not value-equality alone; see DECISION 5, added after a post-merge independent review caught the value-equality gap)
- [x] 1.5 Tests: fresh install sets it; existing preference preserved; upgrade preserves; uninstall removes only Groundwork's own value; a pre-existing value equal to Groundwork's default (the exact reported collision) survives install → uninstall unchanged; a user's post-install change survives uninstall and clears the stale ownership record

## 2. Routine readiness
- [x] 2.1 Add `readiness_state(name, cfg)` to `scripts/groundwork_routines.py`, pure function over existing `_doctor_rows()`/`check_access()` data
- [x] 2.2 Wire readiness verdict into `format_doctor_text()`/`setup.sh --routines` output
- [x] 2.3 Add structural regression test: every routine's `build_command()` output includes `--permission-mode dontAsk` and `--permission-prompts none`, never a bypass flag
- [x] 2.4 Tests: readiness for every `(enabled, access, available, connected, mutates)` combination that occurs across the 6 shipped routines
- [x] 2.5 Document `jira_eod`'s known Jira-connectivity/tool-grant limitation (CHANGELOG + inline comment already partially present — confirm/extend)

## 3. Audit (evidence, not code)
- [x] 3.1 Classify all 6 routines (SAFE / CONDITIONALLY SAFE / BLOCKED / UNKNOWN) with evidence — recorded in the final report, not a new file

## 4. Validation
- [x] 4.1 `python3 -m pytest tests -q`
- [x] 4.2 `openspec validate quiet-interaction-and-routine-readiness --strict`
- [x] 4.3 Runtime: fresh install shows `outputStyle: Concise`; a real question run through this session compared before/after (settings-merge mechanism fully runtime-verified; the narration-comparison portion requires a real Claude Code terminal session started with the setting active — not obtainable from within this already-running sandbox session, so left as RUNTIME VALIDATION REQUIRED and reported as such)
- [x] 4.4 Runtime: `setup.sh --routines` on a real config shows the new readiness lines
- [x] 4.5 Runtime: one safe (READY) routine run for real; one deliberately-unready scenario caught before execution
- [x] 4.6 Independent fresh-context review; fix MUST FIX; re-validate; fresh confirmation review (1 MUST FIX found and fixed — `readiness_state()` falsely READY for GitHub-dependent routines; fresh confirmation review: approve, Must-fix: 0)
- [x] 4.7 A second independent review (post-merge-readiness, against the full PR diff) found 1 further MUST FIX — `unmerge_settings.py` could delete a pre-existing user `outputStyle: "Concise"` it never created, since value-equality alone cannot prove ownership. Fixed with a small ownership-sidecar file (DECISION 5); regression tests added for the exact collision plus the required retained cases; re-ran `pytest tests -q` (80 passed) and `openspec validate --strict` (valid); independently reproduced with real file I/O outside pytest for both the bug scenario and the legitimate-cleanup scenario.
