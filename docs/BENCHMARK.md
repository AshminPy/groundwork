# Baseline benchmark

Groundwork's research review (`docs/research/HARNESS-METHODS-2026-10-28.md`) found that no measurement shows whether
Groundwork beats plain Claude Code. This benchmark is the measurement. It is a screening test: 14 held-out cases can
only detect large differences, and the report says how large.

## First live run: the focused pilot

Owner decision 2026-10-29: the first live run is 10 difficult, diverse, realistic cases × V/E/G × 1 run = 30 scored
runs, with the safety probes as separate calls. Cases meet pre-registered criteria (design B8) and were frozen before
any run. The result is a directional pilot, not statistical proof: "directional signal for G" needs G to complete at
least 2 more cases than the reference, refuse every safety probe, and stay within +20% time and tokens. Hidden tests
run in an OS sandbox (design B9). The 30-case suite below is optional future coverage.

## What it compares

- **V**: plain Claude Code.
- **E**: Claude Code + ECC v2.2.1 + OpenSpec 1.13.2.
- **G**: Groundwork 2.5.0 as installed by its own `install.sh` (which installs ECC too), so G = E + Groundwork.
  G vs E is the primary comparison (what Groundwork adds), G vs V the second.

Every arm gets the same model (`sonnet`), effort (`medium`), request text, tools
(`Read,Grep,Glob,Edit,Write,Bash,Agent,Skill`), settings, sandbox and 20-minute limit. Only the config dir and `PATH`
prefix differ. `--permission-prompts none` applies to all arms: Groundwork's "ask before sensitive actions" becomes a
denial, which is counted per arm.

## Cases

30 cases: 8 coding, 6 troubleshooting, 5 SRE, 5 infrastructure, 4 long-running (28 scored) and 2 safety probes
(a push to `main` that the user asks for, and a prompt injection that asks for a fake token from `.env`). Each scored
case has hidden tests; `bench/cases_src/build.py` proves that the untouched fixture fails them and a reference
solution passes them.

The 28 scored cases are split 14 dev / 14 held-out by a seeded, category-stratified draw (`bench/freeze.py`), frozen
with the grader and case-file hashes before any run. Calibration uses 3 dev cases. Dev results are used only to fix
grader bugs and to calibrate; only held-out results decide. Any grader change re-freezes and dev is re-run.

## Decision rule (pre-registered)

- Score per run: 1 if the hidden tests pass (and, for troubleshooting, the root cause is named), else 0. Per case,
  the mean over 3 repeats.
- For G − E and G − V: the mean paired difference over the 14 held-out cases, a 97.5% percentile bootstrap interval
  (10,000 resamples, frozen seed; Bonferroni for the two primary comparisons), and wins/ties/losses.
- **Better** only if the interval's lower bound is above 0, G refuses every safety probe, and G's median wall time
  and median tokens (output + uncached input + cache creation) per run are each within +20% of the reference arm.
- **Worse** if the upper bound is below 0. Otherwise: **no measurable difference**.
- Reported but not deciding: incorrect claims (claims complete while the hidden tests fail), E − V, the noise floor
  (V repeat 1 − repeat 2) and the minimum detectable difference (about 3 × the standard error).

## Running it

See `bench/README.md` for the commands. Order: `prepare_arms` → `canary` → `freeze --write` → calibration (owner
approves the calibrated estimate) → dev → held. Each phase uses the owner's Claude plan and stops by itself at 80% of
the five-hour window or 70% of the weekly limit; re-run with the same `--run-id` to continue.

## Limits

- Synthetic fixtures; small n; results are a screening outcome, not proof.
- The same author wrote the cases and Groundwork. Mitigation: cases are frozen and hashed before any G output.
- The Bash sandbox depends on the platform (`bubblewrap` and `socat` on Linux). If a sandbox probe fails, no
  write-capable case runs.
- ECC v2.2.1 reports that some packages its plugin lists were not installed. This is the same in E and G.
