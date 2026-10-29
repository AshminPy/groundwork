# Groundwork baseline benchmark

A contributor tool, not installed for users. It compares three Claude Code setups on a frozen held-out task set:

| Arm | What it is |
|---|---|
| **V** | Plain Claude Code: an empty `CLAUDE_CONFIG_DIR`, no `openspec` on `PATH` |
| **E** | Claude Code + ECC `v2.2.1` + OpenSpec `1.13.2` |
| **G** | Groundwork `v2.5.0` via its own `install.sh` (which also installs ECC), so **G = E + Groundwork** |

Plan and decision rule: `openspec/changes/add-baseline-benchmark/` (design B1–B7). Full guide: `docs/BENCHMARK.md`.

## Commands

```bash
python3 -m bench.prepare_arms                 # build V, E, G under ~/gw-bench (GW_BENCH_HOME); writes arms-meta.json
python3 -m bench.canary                       # isolation gate on every arm
python3 -m bench.freeze --write               # freeze split + fingerprints (once, before any run)
python3 -m bench.run --runs-dir /tmp/gw-bench-runs --phase focused       # FIRST LIVE RUN: 10 focused cases x 1 x 3 arms
python3 -m bench.run --runs-dir /tmp/gw-bench-runs --phase calibration   # 3 dev cases x 1 run x 3 arms
python3 -m bench.run --runs-dir /tmp/gw-bench-runs --phase dev           # 14 dev cases x 2 repeats
python3 -m bench.run --runs-dir /tmp/gw-bench-runs --phase held          # 14 held-out + 2 probes x 3 repeats
python3 -m pytest bench/tests -q                                         # unit tests and stub dry run
python3 -m bench.cases_src.build                                         # regenerate cases (then re-freeze)
```

Each phase needs the owner's approval before it runs (it uses the owner's Claude plan). A stopped run continues with
the same `--run-id`.

## Focused pilot (owner decision 2026-10-29)

The first live run is `--phase focused`: 10 difficult cases (`cases_src/focused_a.py`, `focused_b.py`; 2 per
category, each with a named trap), one run per arm = 30 scored runs, plus the 2 safety probes reported separately.
`cases_src/build.py` checks the pre-registered bar (reference changes ≥2 files or ≥30 lines, ≥5 hidden checks, a
named trap, 2 per category). The report is a **directional pilot, not statistical proof** (design B8). The 30-case
suite and its dev/held phases stay as optional future coverage.

## Layout

- `tasks/<id>/instruction.md` and `case.json`: the 30 baseline cases (28 scored, 2 safety probes). The 20 older
  read-only cases (`tasks/<id>/task.toml` + `keys/`, fixture `payments-client`) stay as a regression set for
  `grade.py` and are not re-run in this baseline.
- `fixture/<id>/`: the files the agent starts with. `hidden/<id>/`: tests the agent never sees. `oracle/<id>/`: a
  reference solution, used only by `cases_src/build.py` and the unit tests to prove each case is solvable and that
  the untouched fixture fails. `cases_src/`: the source all of these are generated from.
- `results/`: the M1/M2 pilot results from the parked orchestrator comparison (history only).

## Isolation

- Each arm runs with an allow-listed environment (locale, home, temp dir, proxy and CA bundle only). Host tokens
  such as `GH_TOKEN` or cloud credentials never reach an agent or its commands.
- File tools: the original read fence (`blockReadsOutsideWorkingDirectories`), flags byte-identical to the parked
  adapter (`_adapter.py`).
- Bash: Claude Code's sandbox with `failIfUnavailable`, no unsandboxed retry, no network (`strictAllowlist` with an
  empty allowlist), writes only in the run's workspace, and reads of home, this repository, other runs and `/tmp`
  denied except the run's own workspace. On Linux it needs `bubblewrap` and `socat`.
- Hidden tests and keys enter a run's workspace only after the agent process has exited.
- The canary proves all of this per arm (file-tool probes, Bash and subagent reads, network, `env`, writes outside)
  before any case runs.

## Grading

Hidden tests import agent-written code, so they run inside an OS sandbox (`grader_sandbox.py`): bubblewrap on Linux
(`--unshare-all`, read-only system dirs, the workspace the only writable path, no home or repository), `sandbox-exec`
on macOS (deny by default; unverified on a real Mac until its isolation check passes there). With no sandbox, grading
refuses. `grader_sandbox.isolation_check()` must pass before any run and is also a unit test, with a negative control.

`grade_write.py` copies `hidden/<id>/` into the workspace as `.bench_hidden/` after the run and runs pytest from
inside it, with ini files, plugins and outer conftests ignored. Exit 0 means completed; troubleshooting cases also
need the root cause named in the final answer (a frozen regex). "Claims complete" is a frozen regex on the final
text; an incorrect claim is a claim on a run that is not completed. The Kubernetes checks need PyYAML in the
grader's Python.
