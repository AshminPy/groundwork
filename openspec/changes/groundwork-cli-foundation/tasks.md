# Tasks — Groundwork CLI foundation (Next Release Program, Phase 1)

## 0. Baseline
- [x] 0.1 Independently verify starting baseline (`origin/main` == `66a382f5b34b194345db6e06faeba74e786d07d9`, PR #29 merged, working tree clean, zero open PRs)
- [x] 0.2 Command-surface audit (1A) — full matrix, evidence-backed, delivered by a dedicated Explore subagent
- [x] 0.3 Product Value Gate applied to the Groundwork CLI concept (DECISION 1)
- [x] 0.4 Git autonomy / protected-branch-safety investigation (release program §12) — USE EXISTING CAPABILITY, zero code change (DECISION 3), confirmed via direct code read + live re-run of `test_push_guard` (25/25 pass)

## 1. CLI implementation
- [x] 1.1 Write `scripts/groundwork_cli.py`: argparse-based dispatcher for `--help`/`-h`/no-args, `version`, `doctor`
- [x] 1.2 `groundwork version` reads `$CLAUDE_CONFIG_DIR/groundwork/VERSION`
- [x] 1.3 `groundwork doctor` dispatches to the installed `setup.sh --doctor` (subprocess), output byte-identical (proven, not assumed — see task 3.2)
- [x] 1.4 Plain-terminal compatible: no Nerd Font dependency, no mandatory color, meaningful exit codes (argparse's own `-h`, non-zero on error, no ANSI/color codes anywhere in groundwork_cli.py)

## 2. Installation mechanism
- [x] 2.1 `install.sh`: copy the `groundwork` executable into `$CLAUDE_CONFIG_DIR/groundwork/bin/`, `chmod +x` (plus a copy of `setup.sh` itself, needed so `doctor` can dispatch to it — DECISION 1)
- [x] 2.2 `install.sh`: write `$CLAUDE_CONFIG_DIR/groundwork/env` (idempotent PATH-prepend script, DECISION 2)
- [x] 2.3 `install.sh`: append one guarded, marked sourcing line to each of `~/.bashrc`/`~/.zshrc`/`~/.profile` that already exists — never create one that doesn't
- [x] 2.4 `uninstall.sh`: remove exactly the marked line(s) and the env script and the `groundwork` executable (the existing `rm -rf .../groundwork/bin` already covers the executable and the setup.sh copy)
- [x] 2.5 `install.sh`'s final message states the exact remedy (new terminal, or `source` the env script) for immediate availability

## 3. Tests
- [x] 3.1 `groundwork --help` / no-args / `version` — deterministic, no `claude` subprocess needed
- [x] 3.2 `groundwork doctor` output byte-identical to the installed `setup.sh --doctor` (real subprocess comparison, not just "should match")
- [x] 3.3 PATH registration: idempotent re-install (no duplicate lines), uninstall removes exactly what was added, rc file creation never happens for a shell that has none — all proven via real `install.sh`/`uninstall.sh` runs + a real fresh login-shell PATH resolution check
- [x] 3.4 Hard-compatibility regression: existing `tests/test_setup.py`/`tests/test_playbooks.py`/full suite (84 tests) still green, confirming hook/statusLine/launchd literal paths unchanged
- [x] 3.5 (found during 3.3's own runtime validation, not planned) Fixed a real test-isolation gap: `tests/test_setup.py`'s `Box` class and two of `tests/test_playbooks.py`'s tests invoked `install.sh`/`uninstall.sh` without isolating `HOME`, so this change's new PATH-registration step appended real marked blocks into this sandbox's actual `~/.bashrc`/`.zshrc`/`.profile` twice during testing. Cleaned up immediately both times (verified via `md5sum` + content diff back to original); fixed at the root by isolating `HOME` in all three call sites. Re-ran the full suite twice more with `md5sum` checks before/after: zero further changes. See design.md DECISION 2's "TEST-HARNESS FINDING."

## 4. Documentation
- [x] 4.1 README.md: document `groundwork --help`/`version`/`doctor` as the primary interface, alongside (not replacing) the existing documented invocations
- [x] 4.2 Clearly distinguish user interface (`groundwork ...`) from internal implementation (the scripts it dispatches to) per the release program's §8

## 5. Validation
- [x] 5.1 `python3 -m pytest tests -q` (84 passed: 80 pre-existing + 4 new in tests/test_groundwork_cli.py)
- [x] 5.2 `openspec validate groundwork-cli-foundation --strict`
- [x] 5.3 Runtime: real `install.sh` in a disposable `$CLAUDE_CONFIG_DIR`/`$HOME` → `groundwork --help`/`version`/`doctor` work → real `uninstall.sh` → clean removal, verified by inspection not assumption (28/28 checks in tests/test_groundwork_cli.py, all real subprocess calls)
- [x] 5.4 Independent fresh-context review — verdict **approve, 0 MUST FIX** (real re-derivation of
      every load-bearing claim: dotfile-safety regression re-reproduced with before/after `md5sum`
      on a clean run, `groundwork doctor`/`setup.sh --doctor` byte-identity re-reproduced
      independently, PATH idempotency/uninstall-symmetry/real-shell-PATH-resolution re-reproduced,
      `openspec validate --strict`, scope-diff check, 5 edge cases incl. symlinked/CRLF/
      not-at-EOF/unwritable rc files, `test_push_guard` 25/25 re-run, secret-pattern grep). Two
      NICE TO HAVE findings (not MUST FIX) — fixed anyway since both were cheap, real
      correctness/UX gaps: (a) `install.sh`'s `PATH_RC_TOUCHED` array was populated but never
      read — wired into the completion message (lists which rc files were updated); (b)
      `uninstall.sh`'s marker-block removal left a stray trailing blank line when the block sat at
      true end-of-file — replaced the two-pass duplicate-blank-collapse hack with a single-pass
      one-line-lookback awk that drops exactly the blank separator line `install.sh`'s own
      `echo ""` adds immediately before the marker, symmetric with what was added. Re-validated
      for real: a disposable `$HOME`/`$CLAUDE_CONFIG_DIR` sandbox exercising all three rc files
      through one install+uninstall cycle, covering all three shapes (marker at true EOF, marker
      in an originally-empty file, marker followed by later user content) — each restored exactly
      byte-for-byte to its pre-install content; full suite re-run green (84 passed); `openspec
      validate --strict` re-confirmed valid.

## 6. Report
- [x] 6.1 Commit, push, create draft PR scoped to Phase 1's actual diff, do not merge — subscribed
      PR to this session for CI/review monitoring. (The release program's full end-of-program
      report format applies once all five phases are complete, not to a single phase's PR.)
