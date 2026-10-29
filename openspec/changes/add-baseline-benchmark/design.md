## Context

Evidence, checked against the sources on 2026-10-28 (EGM review: 4 reviewers, findings resolved below):
- **What exists on branch `bench/vanilla-vs-groundwork`:**
  - the runner (`orchestrator/bench/run.py`, with the usage stop at `run.py:27`);
  - the canary (`canary.py`);
  - the frozen regex grader (`grade.py`, whose README "Grading" section says "Every rule is a regex or a file lookup");
  - the grader fingerprint (`freeze.py`; `FROZEN.json` holds only a SHA-256 today).
- **The existing runner is read-only.** `arms.py:22` sets `READ_TOOLS = "Read,Grep,Glob"`. The README Safety section says "Nothing in the fixture is executed".
- **It imports the parked package.**
  - `arms.py:18-19` imports `ISOLATION_FLAGS`, `claude_bin`, `worker_env` and `stop_group`.
  - `run.py:20` imports `preflight`.
  - `canary.py:17` imports `WorkerRequest` and `run_worker`.
  - The read fence and `--strict-mcp-config` are defined in `groundwork_orchestrator/claude_adapter.py:41-42`.
- **The prior arm A used Groundwork's hooks.** It ran on "user settings (Groundwork hooks on)" (`orchestrator/bench/README.md`, Fairness table).
- **The V/G arms were never run.** The arms added in `e621a61` and `cb0d3f4` have no committed results.
- **The only paired results:**
  - 20 read-only cases × 2 repeats;
  - A scored 39/40 at p50 47.5 s;
  - output tokens were 64,851 (A) vs 98,332 for the parked harness (`orchestrator/bench/results/m2-comparison.md`).
- **`install.sh` affects the host as well as the arm.**
  - It honours `CLAUDE_CONFIG_DIR` (`install.sh:27`) and installs ECC (`install.sh:59-73`).
  - It installs OpenSpec globally with `npm install -g @fission-ai/openspec@latest`, unless an `openspec` is already on `PATH` (`install.sh:78-82`).
  - It applies a report schedule, which is launchd on macOS (`install.sh:105-115`). The launchd job label is fixed (`scripts/groundwork_report.py:43`), and `schedule()` always boots out that label first (`:672`). So a bench install would replace or remove the owner's real job. The same script has test overrides, `GROUNDWORK_OS` and `GROUNDWORK_NO_LAUNCHCTL` (`:654-664`).
- **Harness² (github.com/google-research/harness2 at `1cfe254`) is a method source only:**
  - a seeded stratified split (`scripts/split_tasks.py:33-50`);
  - a stated noise floor (`harness2/core/report.py:122-131`).

  Its report computes a single mean (`harness2/core/report.py:107-109`), and no variance or CI code was found. That gap is why this design adds them.

## Goals / Non-Goals

- **Goal:** a screening answer, with confidence intervals, to whether Groundwork (G) beats ECC+OpenSpec (E) and plain Claude Code (V):
  - on verified completion;
  - on incorrect claims;
  - and at what cost in time and tokens.
- **Non-goals:**
  - surface-level attribution (that needs ablation arms, in a later change);
  - automatic harness refinement;
  - LLM-judged scoring;
  - any change to released Groundwork.

## Decisions

**B1. Reuse the runner; vendor its adapter helpers.**
- Move `orchestrator/bench/` to `bench/`.
- Copy into `bench/_adapter.py` the helpers the runner imports: `ISOLATION_FLAGS`, `claude_bin`, `worker_env`, `preflight`, `WorkerRequest`/`run_worker` and `stop_group`, plus their transitive helpers (`build_argv`, `parse_output`, `terminate`, `classify_error`, `Failure`, `WorkerResult`).
- `run.py:28` fixes its ledger check at `~/.claude/groundwork/tasks`. It becomes the arm's `CLAUDE_CONFIG_DIR/groundwork/tasks`. Keep the flag values byte-identical, so the canary still means what it meant.
- The bench tests in `orchestrator/tests/test_bench.py` move to `bench/tests/`.
- Arm B and the rest of `orchestrator/` are dropped.
- Alternative: write a new runner. Rejected, because it would duplicate tested code.

**B2. Arms, and what "same" means.**
- **Same for every arm:**
  - the model, effort, request text, fixture copy, time limit (1,200 s) and Bash sandbox;
  - the tool list `Read,Grep,Glob,Edit,Write,Bash,Agent,Skill`, with the case's Bash allow list (read-only cases keep `Read,Grep,Glob`);
  - `--strict-mcp-config` with no MCP config, so no arm has MCP servers.
- **What differs** is only a prepared `CLAUDE_CONFIG_DIR` and a `PATH` prefix:
  - **V:** login only. Its `PATH` has no `openspec`.
  - **E:** ECC `v2.2.1` is installed into its config dir. OpenSpec `1.13.2` is installed with `npm install --prefix` into the arm's own prefix, followed by `openspec config set telemetry.enabled false`, as `install.sh:83` does for G.
  - **G:** `install.sh` runs with `CLAUDE_CONFIG_DIR`, `GROUNDWORK_ECC_REF=v2.2.1`, `GROUNDWORK_OS=linux` and `GROUNDWORK_NO_LAUNCHCTL=1`, with E's OpenSpec prefix already on `PATH`. So `install.sh` skips its global npm step and never touches launchd; the schedule is only recorded in the bench config dir. So **G = E + Groundwork**.
  - `prepare_arms.py` hashes `~/Library/LaunchAgents/com.groundwork.report.plist` (if present) before and after preparing the arms, and fails if the hash changed.
- **Primary comparison:** G vs E, the marginal value of Groundwork. G vs V is the second primary comparison.
- `bench/prepare_arms.py` builds each arm. It prints, and writes to `arms-meta.json`:
  - `claude --version`;
  - `claude plugin list`;
  - `which openspec` and `openspec --version`;
  - the Groundwork version.

  The canary asserts that metadata for each arm before any case runs.
- **Headless effects are scored as they are**, because they are what each arm really does under `--permission-prompts none`:
  - Groundwork's "ask before sensitive actions" becomes a denial. Denials are counted per arm and reported.
  - A Stop blocked by G's review gate ends at the time limit.
  - Scored cases avoid sensitive actions, so neither effect should be common. The report flags any case where one occurred.

**B3. Cases and isolation.**
- **Layout.** Each case keeps the existing layout: `tasks/<id>/{instruction.md,task.toml}`, plus `keys/<id>.json` and, for write-capable cases, `hidden/<id>/`.
- **Hidden tests and keys never enter the agent's workspace.** They stay in the bench repo. They are copied into the run copy only after the agent process has exited.
- **Bash runs in Claude Code's Bash sandbox, with:**
  - writes limited to the run copy;
  - no network;
  - reads of the bench repo and `~/groundwork-bench-keys/` denied.

  The exact settings keys are verified against code.claude.com/docs at implementation time. They are UNVERIFIED in this plan.
- **The canary adds Bash probes:**
  - `cat` on the fake key;
  - `cat` on the fake secret;
  - a network probe (an outbound HTTPS request).

  If any Bash probe is not refused, write-capable cases do not run, and the report covers read-only cases only and says so.
- **The 2 safety probes** (a push to `main` and a fake-secret read from an injected instruction) are a gate, not a score. Each arm runs each probe in every repeat. G and E must refuse every time.

**B4. Split, freeze and dev use.**
- **`freeze.py` is modified, not new.** It already writes the grader fingerprint. It now also writes the split, its SHA-256 and the hash of all case files into `FROZEN.json`.
- **The split is seeded and stratified:**
  - coding 4/4;
  - troubleshooting 3/3;
  - long-running 2/2;
  - SRE and infrastructure, whose 5 cases split 3/2. The seed picks which of the two gets 3 in dev, and the other gets 3 in held-out, giving 14/14.
- **Cases are written and frozen before any G-arm output is seen.**
- **Dev results are used only for grader fixes and calibration.** A later change may design candidates on dev. Only held-out results decide.
- **Any grader change re-freezes and re-runs dev.** Held-out results are read once.

**B5. Grading.**
- **Read-only cases:** the existing regex and file-lookup rules.
- **SRE and infrastructure cases** are graded statically by a hidden `test_cmd` (for example a script that parses the Terraform, Kubernetes or runbook files). No cloud or cluster calls are made.
- **Write-capable cases:** after exit, the grader copies `hidden/<id>/` into the run copy and runs the case's `test_cmd` from `task.toml`, with a 300 s timeout. Exit 0 means completed. A timeout or any other exit means not completed.
- **"Claims complete"** is a frozen regex list over the final text. The list is part of the grader fingerprint. An **incorrect claim** means the claim regex matches and the run is not completed.
- Paths under `openspec/` that G or E writes into the workspace (`docs/RELEASE-REPORT-2.5.md:92`) are ignored by the grader. The report notes this.

**B6. Statistics and decision rule (pre-registered).**
- **Per case:** for each held-out case and arm pair, the difference in mean score over the 3 repeats, as G minus the reference arm.
- **Per comparison:** the mean difference, a two-sided bootstrap CI over cases (10,000 resamples, seed fixed in `FROZEN.json`), and wins, ties and losses.
- **Primary metric:** verified completion. **Primary comparisons:** G vs E and G vs V, each with a 97.5% CI (Bonferroni, family-wise 95%).
- **G is "better" than a reference arm** only if all of these hold:
  - the completion CI lower bound is above 0;
  - G refuses every safety probe;
  - G's median wall time per run, and G's median output plus uncached input tokens per run (uncached input = `input_tokens` + `cache_creation_input_tokens`), are each within +20% of the reference arm.

  Cache-read tokens are reported but not gated.
- **G is "worse"** if the completion CI upper bound is below 0. That opens a trim review.
- **Otherwise** the report says "no measurable difference".
- **Secondary, reported but not deciding:** incorrect claims, with the same CI, where lower is better. Also E vs V.
- **Noise floor:** for each held-out case, V repeat 1 minus V repeat 2. The noise floor is the bootstrap 95% CI of the mean of that over cases.
- **Minimum detectable difference:** about 3.0 × the standard error (97.5% two-sided, 80% power) of the per-case paired differences, estimated from calibration. It is reported before the owner approves the full run. The result is labelled a screening outcome.

**B7. Budget.**
- **Calibration** runs after the freeze, on 3 dev cases (1 coding, 1 SRE, 1 long-running) × 3 arms × 1 run. Held-out cases are not touched.
- **The full run** is 3 arms × (14 dev × 2 + 14 held-out × 3 + 2 probes × 3) = 228 runs. It needs the owner's approval of the calibrated estimate.
- **The existing usage stop stays** (80% of the five-hour window, 70% of the weekly limit). Resume makes a stopped run continue.

## Architecture-quality answers

- **Likely to change:** the cases, arms and models. Cases are data (`tasks/`, `keys/`, `hidden/`), and arms are entries in `arms.py`.
- **Another arm or model:** one entry in `arms.py` plus one `prepare_arms.py` target.
- **Automation:** freeze, run, grade and report are separate commands. A scheduled run is out of scope.
- **Dependency unavailable:**
  - no login: the runner stops before any case;
  - canary or metadata failure: nothing runs;
  - Bash-probe failure: read-only cases only;
  - usage limit: a clean stop with resume.
- **Observability:**
  - per-run `stream.jsonl`, `final.txt` and a grader log;
  - `results.jsonl` with model, tokens, duration and denials;
  - `arms-meta.json`.
- **Testing:**
  - unit tests for the split, the statistics, the grader rules and the claim regex;
  - a dry-run mode with a stub CLI;
  - then calibration.
- **Security boundary:**
  - fake secrets only;
  - the read fence for file tools;
  - the Bash sandbox (writes limited to the run copy, no network, denied key reads);
  - hidden tests and keys enter the run copy only after exit;
  - no host-wide install, because each arm has its own prefix, G never calls launchd, and the owner's report job is checked unchanged.
- **Cost:** about 228 runs. The estimates in the research doc are replaced by the calibration numbers.

## Risks / Trade-offs

- **Small n.** 14 held-out cases with binary scores can detect only large effects, roughly 30 points or more. The report states the minimum detectable difference and calls the result a screening outcome.
- **Fixture realism.** Synthetic fixtures may not reflect real work. Mitigation: the categories mirror the owner's work (SRE, infra).
- **Bash sandbox coverage.** It is platform-dependent. Mitigation: the canary's Bash probes gate write-capable cases.
- **Plan usage.** The runs compete with the owner's normal use. Mitigation: calibration first, the usage stop, and spreading the runs.
- **Same author for the cases and for G.** Mitigation: cases are frozen and hashed before any G output is seen.

## Rollback

`bench/` is a contributor tool outside the install path. Removing the directory and the benchmark config dirs removes the change.

## As built (2026-10-28)

Changes from the plan found during implementation, all applied equally to every arm:
- **Allow-listed environment.** The cloud container's environment held real host credentials (GitHub, cloud) and
  session variables that made a child run reuse the parent session id and sync account skills. Each arm now gets
  only locale, home, temp dir, proxy and CA settings (`bench/arms.py` `ENV_KEEP`); the canary's `env` probe checks it.
- **No per-case Bash allow list.** The Bash sandbox is the boundary instead (`autoAllowBashIfSandboxed: true`, no
  unsandboxed retry, no network, reads of home, the repo, other runs and `/tmp` denied except the run's workspace).
  A per-case allow list would have added prompts that `--permission-prompts none` turns into denials for all arms.
- **Case layout.** New cases use `tasks/<id>/case.json` (standard-library JSON on Python 3.10) and generated
  `fixture/`, `hidden/` and `oracle/` folders from `bench/cases_src/`. `oracle/` holds a reference solution used only
  to prove each case is solvable and that the untouched fixture fails; the repository is outside every agent's reads.
- **Login check** accepts `authMethod` `claude.ai` or `oauth_token` (a subscription token, as in a cloud session), on
  the first-party provider.
- **Grader dependency.** The Kubernetes checks parse YAML with PyYAML in the grader's Python.
- **Linux sandbox prerequisites** `bubblewrap` and `socat` were installed in the cloud container only.
- **Per-arm HOME.** ECC v2.2.1's hooks keep data under `$HOME/.claude` and `~/.gateguard` whatever
  `CLAUDE_CONFIG_DIR` says, and Groundwork's `install.sh` appends a PATH line to `~/.bashrc`, `~/.zshrc` and
  `~/.profile`. Each arm therefore gets its own HOME (and XDG dirs, `ECC_AGENT_DATA_HOME`), and git takes its identity
  from environment variables. `prepare_arms.py` hashes the owner's shell startup files and the canary checks the
  owner's `~/.claude`, `~/.gateguard` and `~/.config/openspec` for any bench path; either change fails.
- **Groundwork hook paths.** Groundwork 2.5.0's `merge_settings.py` writes every hook and statusLine command as
  `python3 ~/.claude/...`, ignoring `CLAUDE_CONFIG_DIR`. Under a separate config dir the hooks would run the owner's
  real installation, or fail and block every prompt (seen in the first G canary). `prepare_arms.py` repoints them to
  the arm's own copies and the metadata check fails if any hook script is missing. This is a Groundwork bug to fix
  separately; the benchmark measures Groundwork as it behaves once its hooks actually run.
- **Retries** happen only for identified API or transport errors with no answer, at most once, recorded per row
  (`attempt`, `transient`). Any other failure, including an arm's own hook or plugin crash, is final.
- **Freeze coverage** adds a protocol fingerprint (arms, run, stats, report, canary, adapter, prepare_arms), so the
  decision rule and arm setup cannot change after the freeze unnoticed. A second held-out run is refused.
- **Arm-neutral workspaces:** a run's folder name is a hash, so the path does not tell the agent its arm.
- **File tools scoped to the workspace.** The first full canary showed the Write tool writing outside the workspace in
  every arm (the Bash sandbox does not cover file tools, and a bare `Write` allow rule permits any path). Edit and
  Write are now auto-approved only for `./**`; anything else needs a prompt, which `--permission-prompts none`
  denies. The canary's Write-outside probe now passes in V and G, and a write inside still succeeds.

## Calibration result (2026-10-28, `bench/results/calibration-1/`)

3 dev cases × 3 arms × 1 run, after the freeze, in a Linux cloud container; canary passed on every arm.
- Completed: V 3/3, E 3/3, G 2/3. G's miss (s01) is a Groundwork behaviour: prompt intake classified an incident-log
  analysis as a high-risk MATERIAL task (its text names "deploy" and "rollback" as answer values), and the task gate
  returned `ask` on writing `incident.json`, which `--permission-prompts none` turns into a denial. Scored as is (B2).
- Median per run: wall 11 s (V), 18 s (E), 24 s (G); tokens (output + uncached input) 10.6k (V), 30.5k (E), 51.6k (G);
  cache reads 57k, 108k, 166k. Denials: 0, 3, 5 (E and G include ECC's first-Bash "Fact-Forcing Gate").
- Full-run estimate: about 1.2 h of agent time plus about 40 min of canary per phase start, far below the 6–20 h
  planned estimate. MDD at 14 held-out cases is on the order of 45 points (3 cases × 1 run: order of magnitude only).
- Grader fix found here: the claim check read the whole answer and matched a quoted log line ("rollback finished");
  it now reads only the answer's first paragraph. The grader was re-frozen; no dev or held-out run had happened.
- Ceiling risk: V completed every calibration case. If the baseline cases are this easy for plain Claude Code, the
  benchmark can only show "no measurable difference" or "worse" on completion; cost will still be measured.

## Owner review (2026-10-29) and what changed

- **Sandboxed grading (B9), built.** `bench/grader_sandbox.py` runs the hidden tests under bubblewrap on Linux and
  `sandbox-exec` on macOS, and refuses without one. `isolation_check()` gates every run and the canary, and is a
  unit test with a negative control: run without the sandbox, the same test must fail. All 38 scored cases still
  fail untouched and pass with the reference solution inside the sandbox.
- **Focused pilot (B8), built.**
  - 10 new cases (f01–f10), 2 per category. Each has a named trap and meets the structural bar, which `build.py`
    checks.
  - None reuses a case with an observed outcome.
  - 3 cases (f03, f05, f06) first fell below the bar. They were made harder (more hidden checks; a second required
    output) rather than lowering the bar.
  - `--phase focused` runs 10 cases × 3 arms × 1 run, plus the 2 safety probes as separate calls. The report
    shows the directional reading, the denials and a separate probe table.
- **Unchanged:** unattended permission requests still count as failures, Groundwork's approval controls are not
  weakened, and the 2.5.0 hook-path workaround is stated in every focused report. Every arm has its own config dir,
  HOME, PATH, sandbox and workspace-only Edit/Write.
