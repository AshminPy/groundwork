## 0. Direction
- [x] 0.1 Owner approved: park the separate harness, extend core (2026-10-26)
- [ ] 0.2 Close PR #62, #64, #65 as parked (branches kept)

## 1. Benchmark in core
- [ ] 1.1 Never-case tests: grader never reads arm status; mismatched fingerprints refused; canary failure stops the run
- [ ] 1.2 Move bench from orchestrator/bench to bench/, arms G0/G1 without the orchestrator; existing grader tests pass
- [ ] 1.3 Live: canary passes; a 2-case smoke run of G0

## 2. Usage visibility
- [ ] 2.1 Never-case tests (no content stored; render survives a write failure; no "exceeded by" claim)
- [ ] 2.2 statusLine usage record (throttled) + `groundwork usage` + optional segment
- [ ] 2.3 Live: two concurrent sessions appear in the report

## 3. Task brief continuity
- [ ] 3.1 Never-case tests (no cross-task overwrite, no cross-repo load, checkpoint never blocks)
- [ ] 3.2 Per-task brief path, checkpoint hook, snapshot reload
- [ ] 3.3 Live: forced early compaction reloads the brief verbatim

## 4. Citation check
- [ ] 4.1 Verify final-message access from `transcript_path`; choose Stop-hook or command delivery
- [ ] 4.2 Never-case tests; port the locate logic to core
- [ ] 4.3 Live: planted wrong citation reported

## 5. Decision gate
- [ ] 5.1 Benchmark cases modelled on the runner incident; run G0 first
- [ ] 5.2 Build only if G0 shows the leap: record + rule + challenge reviewer, test-first
- [ ] 5.3 G0 vs G1 comparison
