## 0. Direction
- [x] 0.1 Owner approved: park the separate harness, extend core (2026-10-26)
- [x] 0.2 Close PR #62, #64, #65 as parked (branches kept) — done 2026-10-26

## 6. Response contract enforcement — PR #66
- [x] 6.1 Verified against the hooks docs: Stop input has stop_hook_active and last_assistant_message; decision "block" continues the turn (cap 8)
- [x] 6.2 Never-case tests (no block without tool use, at most one ask, kill switch, fail-open, long-token time bound) — 47 tests
- [x] 6.3 hooks/groundwork_reply_check.py: prompt-time reminder + routed playbook Output Format; Stop-time check
- [x] 6.4 Live: a bare "3" reply after Bash got one request and was completed; a chat turn was untouched
- Baseline: 31/51 tool turns in this repo lacked HARNESS METADATA; 40/40 saved benchmark answers pass the check (no false asks)

## 2. Usage visibility — PR #67
- [x] 2.1 Never-case tests (no content, no session name, render survives a write failure, no "exceeded" claim) — 35 tests
- [x] 2.2 statusLine usage record (throttled, trimmed) + `groundwork usage` + `5h NN%` / gateway `spend NN%` segment
- [ ] 2.3 Live: two concurrent sessions appear in the report — needs merge + install (statusLine does not run in `-p`)

## 3. Task brief continuity — PR #69
- [x] 3.1 Never-case tests (no cross-branch/cross-repo load, byte-exact outside the snapshot, no overwrite of a concurrent edit, ask once) — 45 tests
- [x] 3.2 hooks/groundwork_brief.py: per-branch brief; Snapshot rewritten on PreCompact and tool-using Stop; SessionStart reload with its own 2,400-char budget (no change to the #61 snapshot file); ask once for Goal/Next step
- [x] 3.3 Live: a new session recalled the brief's next step without tools; a real /compact refreshed the snapshot
- Deferred: a context-% checkpoint (hooks do not receive context %; PreCompact covers the loss point)

## 4. Citation check — NOT BUILT (measured)
- [x] 4.1 Measured on 80 saved answers against the benchmark fixture: 852 citations, 0 missing files, 0 lines out of range; a free-text quote check flagged 6, all false alarms (truncated or paraphrased quotes)
- Decision: a Stop check on free text would add false asks and catch nothing measured. Revisit only with structured claims.

## 7. Portability — PR #68
- [x] 7.1 Clean install/uninstall into a temporary config dir is covered by tests/test_setup.py (hook counts updated per feature PR)
- [x] 7.2 docs/NEW-MACHINE-CHECKS.md: one live check per feature
- [ ] 7.3 Work laptop: run step 0 (`/status`; check managed `allowManagedHooksOnly` / `disableAllHooks`) — needs the work laptop

## 1. Benchmark in core — OWNER DECISION
- [ ] 1.1-1.3 Port bench/ from the parked feat/m2-question-evidence branch. Only worth it together with 5.1, which spends plan quota.

## 5. Decision gate — OWNER DECISION
- [ ] 5.1 Runner-style benchmark cases, G0 first (about 16-40 `claude -p` runs; roughly $0.40 each at list price, from plan quota)
- [ ] 5.2 Build only if G0 shows the unproven-leap failure
- [ ] 5.3 G0 vs G1 comparison
