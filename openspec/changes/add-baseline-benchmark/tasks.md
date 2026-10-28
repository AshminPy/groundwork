## 0. Owner decision
- [x] 0.1 Owner approves this plan (after the EGM review) before any implementation (approved 2026-10-28 for implementation and calibration; the full baseline needs separate approval)

## 1. Move the runner
- [x] 1.1 Move `orchestrator/bench/` from `bench/vanilla-vs-groundwork` to `bench/` on a new branch; drop arm B and `orchestrator/`
- [x] 1.2 Vendor `ISOLATION_FLAGS`, `claude_bin`, `worker_env`, `preflight`, `WorkerRequest`/`run_worker` and `stop_group` into `bench/_adapter.py`. Keep the flag values byte-identical. Move the bench tests to `bench/tests/`, and they pass
- [x] 1.3 `bench/prepare_arms.py` builds V, E and G (per-arm config dir and `PATH` prefix, OpenSpec 1.13.2 via `--prefix`, `GROUNDWORK_ECC_REF=v2.2.1`, G installed with `GROUNDWORK_OS=linux` and `GROUNDWORK_NO_LAUNCHCTL=1`), checks the owner's report plist hash is unchanged, and writes `arms-meta.json`

## 2. Write-capable runs and grading
- [x] 2.1 Write-capable arm argv: tool list `Read,Grep,Glob,Edit,Write,Bash,Agent,Skill`, per-case Bash allow list, Bash sandbox (settings keys verified against the docs first)
- [x] 2.2 Canary: Bash `cat` probes on the fake key and secret, a network probe, and the arm-metadata check
- [x] 2.3 Grader: copy `hidden/<id>/` after exit, run `test_cmd` with a 300 s timeout (exit 0 = completed), the frozen claim regex, and denial counts

## 3. Cases and split
- [x] 3.1 30 new cases: 28 scored (8 coding, 6 troubleshooting, 5 SRE, 5 infrastructure, 4 long-running), each with a fixture, hidden tests or a key, plus 2 safety probes
- [ ] 3.2 Modify `freeze.py`: seeded stratified 14/14 split per design B4, plus the split hash, the case-file hash and the bootstrap seed, all in `FROZEN.json`

## 4. Report
- [x] 4.1 G-minus-reference differences, bootstrap CIs (97.5% for the two primary comparisons), wins/ties/losses, noise floor, minimum detectable difference, and the directional decision rule from design B6

## 5. Verification
- [x] 5.1 Unit tests (split, statistics, grader rules, claim regex) and a stub-CLI dry run
- [ ] 5.2 Calibration after the freeze: 3 dev cases × 3 arms × 1 run, with measured tokens, time and minimum detectable difference, reported to the owner
- [ ] 5.3 Independent review with the MUST FIX bar stated up front

## 6. Baseline (separate owner approval)
- [ ] 6.1 Full baseline run (about 228 runs) and report
