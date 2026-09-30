# Design — Groundwork CLI foundation

## Architecture-quality §2 answers (MATERIAL tier: touches the installer, a user's PATH/shell rc
files, and introduces a new top-level entry point)

- **What is likely to change?** Which subcommands exist (today: `version`, `doctor`; Phase 2-4
  add `integrations`/`routines`/`update`/`rollback`) — kept as one dispatch table, one place, so
  adding a subtree later means adding a dispatch entry, not restructuring. Which script backs
  each subcommand — unchanged by this phase; the CLI only dispatches to existing, already-tested
  code.
- **How would another instance be added?** A 7th subcommand is a new entry in the CLI's dispatch
  table plus (if needed) a new argparse subparser mirroring the pattern the audit found already
  works well for `groundwork_config.py`/`groundwork_integrations.py`/`groundwork_report.py`/
  `groundwork_routines.py` — their existing subcommand names/args become the new CLI's
  subcommand names near-verbatim (see DECISION 1's evidence).
- **Which manual operational steps can reasonably be automated?** None newly identified — this
  phase is a discoverability/UX layer over existing automation, not new automation.
- **What fails if a dependency is unavailable, and how is that surfaced?** `groundwork` itself
  needs only Python 3 stdlib (same footprint as every other Groundwork script). If the PATH
  registration hasn't taken effect yet in the current shell (a new terminal wasn't opened, or the
  rc file wasn't sourced), `groundwork` simply isn't found — the same `command not found` any
  shell gives for any uninstalled tool; `install.sh` prints the exact remedy (source the rc file
  or open a new terminal), matching how `rustup`/`uv`/`nvm` already handle this (see DECISION 2).
- **How will an operator observe/troubleshoot this?** `groundwork doctor` dispatches to the exact
  same `verify_install`/capability/integration/routine-status code path `./setup.sh --doctor`
  already uses — no new diagnostic surface, same one.
- **How will it be tested?** Deterministic: `groundwork --help`/`version` need no subprocess to
  `claude`; `groundwork doctor`'s dispatch is tested by diffing its output against calling
  `setup.sh --doctor` directly on the same fixture `$CLAUDE_CONFIG_DIR`. Runtime: a real
  `install.sh` run in a disposable `$CLAUDE_CONFIG_DIR`, confirming `groundwork --help` works
  after sourcing the installed PATH helper, then a real `uninstall.sh` confirming clean removal.
- **What security boundary exists?** None new. `groundwork` runs with the same privileges as
  every other Groundwork script (no sudo, writes only under `$CLAUDE_CONFIG_DIR` and the user's
  own shell rc files — the same files/mechanism `install.sh` already touches for settings.json).
- **Scaling/cost implications?** None — a CLI dispatch is O(1), no new subprocess beyond what the
  dispatched command already spawns, no new network call.

## DECISION 1 — Command-surface audit and Phase 1 scope (Product Value Gate)

EVIDENCE: A full audit of the current repository (every flag `setup.sh`/`install.sh`/
`uninstall.sh` support, every `argparse` subcommand in `scripts/*.py`, every hook, every
documented command in README.md/docs/*.md) found: no single discoverable entry point exists
today; users must know which of ~6 scripts/shell-entry-points owns a given task, the exact
installed path, and that script's own flag dialect (some `argparse`, some raw `sys.argv`;
`uninstall.sh` has no `--help` at all). The audit also found two **hard compatibility
requirements** that constrain this and every later phase: (1) the literal installed paths
`~/.claude/hooks/*.py` and `~/.claude/groundwork/bin/groundwork_statusline.py` are written into
every installed user's own `settings.json` (`hooks.*`, `statusLine.command`) — they must keep
existing at those exact paths regardless of any new wrapper; (2) `~/.claude/groundwork/bin/
groundwork_report.py` and `groundwork_routines.py`'s literal installed paths are embedded in
already-scheduled macOS `launchd` plists' `ProgramArguments` — same constraint. No CI workflow
exists in this repository, so "compatibility requirement: CI depends on it" does not apply
anywhere; the only hard dependencies are already-installed users' settings.json/launchd state and
`setup.sh`'s own internal delegation to these scripts by path.

PRODUCT VALUE GATE:
- USER PROBLEM: no single discoverable command; inconsistent flag dialects; installed-path
  knowledge required.
- CURRENT WORKFLOW: know which of 6 scripts, know the installed path, know that script's own
  argument syntax.
- PROPOSED WORKFLOW: `groundwork <noun> <verb>`, discoverable via `groundwork --help`.
- FREQUENCY: high for `doctor`/`version` (the commands most cross-referenced across
  docs/TROUBLESHOOTING.md, docs/ROUTINES.md, docs/INTEGRATIONS.md as the first thing a user or
  session reaches for); lower for one-shot lifecycle commands (out of scope this phase).
- EXISTING CAPABILITY: none — the audit found no existing single entry point; `setup.sh`'s flags
  only cover a subset and don't reach integrations directly. Genuine gap.
- TRUTHFULNESS: the wrapper adds no new truth claims — it dispatches to scripts that already
  compute real, evidence-backed state.
- COMPLEXITY: low for the four `argparse`-based scripts (subcommand names/args translate
  near-verbatim); the wrapper must not duplicate their logic, only dispatch to it.
- ACTIONABILITY: `groundwork doctor` instead of remembering `./setup.sh --doctor`; `groundwork
  --help` instead of reading README's scattered command list.
- SUCCESS CRITERIA: see `proposal.md`'s Acceptance Criteria.

CLASSIFICATION: **BUILD**, scoped to **BUILD REDUCED SCOPE** for this phase specifically —
`groundwork --help`/`version`/`doctor` only (per the release program's own §1E "at minimum
evaluate and implement if justified" list and its phase-gating discipline: Phase 2 does not begin
until Phase 1's acceptance criteria hold). `integrations`/`routines` subtrees are evidence-ready
(the audit shows their backing scripts are already well-suited to direct dispatch) but are
explicitly Phase 2/4, not built here, to keep this PR reviewable and to give the program a real
checkpoint before committing to the rest of the tree.

WHY dispatch, not reimplement: `groundwork_config.py`/`groundwork_integrations.py`/
`groundwork_report.py`/`groundwork_routines.py` already have correct, tested `argparse` parsers.
Reimplementing their argument handling in a new wrapper would duplicate logic and risk behavior
drift (the same risk `groundwork_shared.py`'s existing `TEST_CMD`-sharing pattern already exists
to avoid elsewhere in this codebase). `groundwork doctor` therefore calls `setup.sh`'s own
`verify_install`/doctor code path (via subprocess, matching how `setup.sh` itself already
delegates to the Python scripts) rather than reimplementing health-check logic in Python.

TRADEOFFS: `groundwork doctor` shells out to `setup.sh --doctor` rather than being pure Python —
accepted, because `setup.sh`'s doctor output already aggregates bash-side checks (ECC, OpenSpec,
Node version) that would otherwise need re-implementing in Python, and the acceptance criteria
require byte-for-byte parity with the existing command, which calling it directly guarantees by
construction.

VALIDATION METHOD: diff `groundwork doctor`'s output against `./setup.sh --doctor`'s output on
an identical fixture config (must be identical); `groundwork version` against the installed
`VERSION` file's content; `groundwork --help`/no-args both print the same help and exit 0.

UNCERTAINTY: none material for this phase's scope.

## DECISION 2 — PATH registration mirrors the `uv`/`rustup` idempotent-env-script pattern

EVIDENCE: Tested directly in this environment (not assumed): `~/.profile` sources
`"$HOME/.local/bin/env"`, a small POSIX-sh script that conditionally prepends `~/.local/bin` to
`PATH` only if not already present (`case ":${PATH}:" in *:"$HOME/.local/bin":*) ;; *) export
PATH=... ;; esac`). This is the exact convention modern installers (`uv`, `rustup`) already use
and that this sandbox's own toolchain already relies on. No `/etc/profile.d` script or
`/etc/environment` entry provides this — it is installer-written, not OS-provided, confirming it
is a portable *pattern* to copy, not an environment-specific given.

WHY this over alternatives: (a) a `pip`-installed console-script entry point would require
packaging (`pyproject.toml`, a wheel/sdist, `pip`/`pipx` as a new hard dependency) — a "large
runtime dependency" and "unnecessary package manager" the program explicitly rules out, and a
real philosophy change from Groundwork's existing direct-file-copy installer (`install.sh` simply
`cp`'s scripts into `$CLAUDE_CONFIG_DIR/groundwork/bin/` today); (b) symlinking into
`/usr/local/bin` can require `sudo` depending on ownership — violates the explicit "no sudo"
requirement and cannot be assumed safe across machines; (c) mutating the *current* shell's `PATH`
from within the installer process is not possible (each process has its own environment) — every
comparable tool (`rustup`, `uv`, `nvm`, `pyenv`) has this same limitation and handles it the same
way: write the idempotent env script, add one guarded sourcing line to whichever rc files already
exist (`~/.bashrc`, `~/.zshrc`, `~/.profile`), and tell the user to open a new terminal or
`source` it.

IMPLEMENTATION: `install.sh` writes `$CLAUDE_CONFIG_DIR/groundwork/env` (same conditional-prepend
shape as `~/.local/bin/env`, targeting `$CLAUDE_CONFIG_DIR/groundwork/bin`) and appends one
guarded line — `[ -f "$CLAUDE_CONFIG_DIR/groundwork/env" ] && . "$CLAUDE_CONFIG_DIR/groundwork/env"`
wrapped in a Groundwork-marker comment, matching the exact additive/idempotent/exact-match-
removal philosophy `merge_settings.py`/`unmerge_settings.py` already establish for settings.json
— to every rc file that already exists among `~/.bashrc`, `~/.zshrc`, `~/.profile` (never
creating a shell config file that doesn't already exist, never touching one for a shell the user
evidently doesn't use). `uninstall.sh` removes exactly that guarded block (exact-string match,
same limitation already documented for the settings.json keys: a byte-identical block a user
happened to add independently would also be removed — accepted, same as the existing pattern).

TRADEOFFS: `groundwork` is not available in the *current* shell immediately after `install.sh`
finishes — the same limitation every comparable installer has; `install.sh` prints the exact
remedy. Multiple rc files can be touched (bash and zsh both, if both exist) — intentional,
defensive, matches real-world users who have more than one shell config present even if `$SHELL`
names only one.

VALIDATION METHOD: real `install.sh` run in a disposable `$CLAUDE_CONFIG_DIR` + disposable `HOME`
(so the real rc files are never touched by a test), confirm the env script and rc-file line
appear, `source` the env script in a subshell and confirm `groundwork` resolves on `PATH`; real
`uninstall.sh` run, confirm both are removed and the rest of the rc file is untouched.

UNCERTAINTY: ASSUMPTION — a user with a shell other than bash/zsh (e.g. fish) gets no PATH
registration and must add it manually; `install.sh`'s final message states this explicitly rather
than silently doing nothing. Low risk: fish is a small minority of Groundwork's target audience
(Claude Code's own supported/documented shells), and the underlying executable still works when
invoked by full path regardless.

TEST-HARNESS FINDING (not a production bug — found and fixed during this change's own runtime
validation): `install.sh` writing to `$HOME/.bashrc`/`.zshrc`/`.profile` directly (rather than
`CLAUDE_CONFIG_DIR`-relative) exposed that three existing test files invoking `install.sh`/
`uninstall.sh` (`tests/test_setup.py`'s `Box` class and two of its test-local scenarios, `tests/
test_playbooks.py`'s `test_install_copies_playbooks`/`test_install_node_version_check`) never
isolated `HOME` — only `CLAUDE_CONFIG_DIR`, which was sufficient for everything install.sh/
setup.sh touched *before* this change. Running the real test suite during this change's own
validation appended real marked blocks into this sandbox's actual `~/.bashrc`/`.zshrc`/`.profile`
twice (confirmed via `md5sum` before/after and direct inspection), cleaned up immediately each
time, then fixed at the root by isolating `HOME` in all three call sites (mirroring the same
`CLAUDE_CONFIG_DIR`/`GROUNDWORK_BACKUP_DIR` isolation pattern those tests already used). Re-ran
the full suite twice more after the fix with `md5sum` checks before and after each run: zero
further changes to the real dotfiles. This was never a production-code defect — a real user's own
`install.sh` run was always going to write to their own real `$HOME` correctly, on purpose; the
defect was solely in pre-existing test isolation that predated this change's introduction of the
first `$HOME`-touching behavior in Groundwork's installer.

## DECISION 3 — Git autonomy / protected-branch safety: USE EXISTING CAPABILITY, no code change

EVIDENCE: Read `hooks/block_protected_push.py` directly (not assumed). It already: resolves the
actual destination ref for every push form (bare `git push`, `HEAD`, `@`, `src:dst`, `:dst`
deletion, `+refs/heads/dst`), not literal text matching; recurses into `sh|bash|zsh|dash|ksh -c`
and `eval`; strips `sudo`/`env`/`command`/`nice`/`time` wrappers and leading env-assignments;
denies `--force`/`-f`/`--force-with-lease`/`--force-if-includes` and `--all`/`--mirror`/
`--branches` unconditionally (not only against protected branches); fails open on any parse
error so a broken guard can never become a silent bypass of Claude Code's own normal Bash
permission prompts. Its own existing test, `tests/test_hooks.py::test_push_guard`, already
covers the exact PASS/BLOCK matrix the release program's §12J requires — re-run live for this
change: 25/25 checks pass, including every case named in §12B ("git push -u origin
feat/groundwork-cli-foundation"-shaped feature-branch pushes → allow) and §12A/§12E (`git push
origin main`, `HEAD:main`, `feature-x main` (second refspec protected), `:main` deletion,
`+HEAD:refs/heads/main`, `--all`, `--mirror`, nested `bash -c`/`eval` forms, a `-C` global option
→ all deny).

Separately, this very session has already exercised the desired autonomous workflow for real,
repeatedly, without any Groundwork settings change: created feature branches, staged named files
(never blind `git add -A`), committed, pushed feature branches and subsequent commits, created
PRs via the GitHub MCP server — all without per-action approval prompts — while every attempted
or hypothetical protected-branch mutation remains hook-blocked per the test evidence above. This
is the exact layered model §12G itself describes as correct: Claude Code's own permission
mode/configuration governs ordinary Bash (a user/session-level choice Groundwork does not own or
need to touch) → `block_protected_push.py` deterministically blocks the protected-destination
case regardless of that mode → GitHub's own server-side branch protection is the final backstop.
`merge_settings.py` already adds `permissions.deny` glob patterns for the literal force-push/
push--force cases (`Bash(git push --force*)`, `Bash(git push -f *)`) as a first-layer native
Claude Code permission rule; it does not and should not add a `permissions.allow` list for
ordinary git commands, since that already works via the ambient session permission
mode — adding one would be exactly the "giant unrestricted Bash allowlist" the program's §12H
explicitly warns against building.

WHY no change: every requirement in §12A-12J of the release program is already met by existing,
tested code, confirmed by direct evidence rather than assumption. Per §12L's own instruction
("If existing Claude Code + Groundwork already provides this exact behavior: USE EXISTING
CAPABILITY and do not add unnecessary code"), building anything here would be unjustified
architecture the codebase does not need.

TRADEOFFS: none — no code changes means no new surface to maintain or regress.

VALIDATION METHOD: the existing `test_push_guard` re-run live (25/25 pass, shown above) plus this
session's own observed git workflow across this task and the prior `feat/quiet-interaction-
routine-readiness` PR as corroborating evidence.

UNCERTAINTY: none material. The one narrow gap the audit's own command-surface investigation
separately surfaced — `./setup.sh --uninstall` cannot forward `--agent-teams` to `uninstall.sh`
— is a pre-existing, unrelated bug in flag-forwarding, not a git-autonomy/protected-branch gap;
noted here for completeness but left out of this change's scope (it doesn't affect Phase 1's
CLI work and fixing it would broaden this PR beyond its stated purpose).
