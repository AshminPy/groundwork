## Why

No measurement shows that Groundwork beats plain Claude Code, and none shows what its overhead costs:
- The benchmark branch added vanilla (V) and Groundwork (G) arms but never ran them (`bench/vanilla-vs-groundwork`, commits `e621a61`, `cb0d3f4`).
- The only paired data comes from a "plain Claude Code" arm that ran with Groundwork's hooks on (`orchestrator/bench/README.md`, Fairness table). Even so, that arm scored 39/40 (`orchestrator/bench/results/m2-comparison.md`).

The research in `docs/research/HARNESS-METHODS-2026-10-28.md` found that every candidate method from other harnesses needs
this baseline before it can be justified. The owner's question is whether Groundwork needs more features at all.

## What Changes

- Bring the existing benchmark runner to `main` as a contributor tool under `bench/`. It is not installed for users.
  - **Kept:** the isolation canary, the read fence, the frozen regex grader, the grader fingerprint (`freeze.py`), the plan-usage stop and resume.
  - **Vendored:** the adapter helpers the runner imports from the parked package (`ISOLATION_FLAGS`, `claude_bin`, `worker_env`, `preflight`, `WorkerRequest`/`run_worker`, `stop_group`). The flags stay byte-identical.
  - **Dropped:** the parked orchestrator arm (B) and the rest of `orchestrator/`.
- **New work.** The existing runner is read-only (Read, Grep and Glob only). This change adds:
  - write-capable runs with Edit, Write and an allow-listed Bash, inside a per-run fixture copy, behind a Bash sandbox with no network;
  - hidden-test grading after the agent exits;
  - a frozen "claims complete" rule for the incorrect-claim metric;
  - Bash and network probes in the canary.
- Three arms, each with its own `CLAUDE_CONFIG_DIR` and its own `PATH` prefix:
  - **V**, plain Claude Code, with no `openspec` on `PATH`;
  - **E**, Claude Code with ECC `v2.2.1` and OpenSpec `1.13.2`;
  - **G**, Groundwork 2.5.0, installed with `install.sh`. Because `install.sh` also installs ECC, **G = E + Groundwork**, and G vs E is the primary comparison.
- 30 new cases: 28 scored cases (8 coding, 6 troubleshooting, 5 SRE, 5 infrastructure, 4 long-running) and 2 safety probes, run as a pass/fail gate in every arm. The 20 existing read-only cases stay in the repo but are not re-run in this baseline.
- A seeded, category-stratified 14/14 dev/held-out split of the scored cases, frozen and hashed before the first run. 2 repeats per dev case and 3 per held-out case.
- A report with:
  - paired held-out differences;
  - bootstrap confidence intervals;
  - wins, ties and losses;
  - a noise floor;
  - a minimum detectable difference;
  - a pre-registered, directional decision rule.
- A 9-run calibration pass on dev cases, after the freeze, to measure real token use and time before the full run of about 228 runs.

**Not changed:** hooks, rules, install, setup, and any released behavior.

**No new features** are built. Candidates (a STANDARD-turn completion gate, a failed-fix counter) are left for a later change, if the baseline shows the failure they address.

The result covers whole installs. It cannot attribute an effect to one Groundwork surface.

## Capabilities

### New Capabilities
- `harness-benchmark`: a fair, repeatable comparison of plain Claude Code, ECC+OpenSpec and Groundwork on a frozen
  held-out task set.

## Impact

- New `bench/` directory (Python stdlib only) and `docs/BENCHMARK.md`.
  - Nothing is copied into `~/.claude`.
  - Arm installs go into separate benchmark config dirs.
  - G's install never calls launchd, and the owner's real report job is checked unchanged.
- Running it uses the owner's Claude plan: an estimated 6–20 hours of run time over several five-hour windows (see design). It needs owner approval for each run, and the calibration result comes before the full run.
