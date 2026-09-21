# Troubleshooting

**`./setup.sh` says prerequisites are missing.**
It lists each one with the exact official command for your OS and installs them after you answer `y` (Homebrew on macOS; apt, dnf or apk on Linux with `sudo`). Two things it will not do: install Claude Code (install it from https://code.claude.com/docs/en/setup and sign in once with `claude`), and install Homebrew (run the printed one-liner yourself, it needs your password). A Node.js that exists but is older than 18 is left to your version manager — upgrade with nvm/asdf/volta or from nodejs.org. In `--non-interactive` mode nothing is installed unless you pass `--install-prereqs`, and Linux needs passwordless `sudo` for that. After installing, open a new terminal if the tools are still not found.

**`./setup.sh --verify` shows FAIL or NOT CONFIGURED.**
Each row names the missing piece and its path. `NOT CONFIGURED` for the dashboard or schedule just means nothing has been generated or scheduled yet (`python3 ~/.claude/groundwork/bin/groundwork_report.py generate`, `… schedule weekly`). A FAIL on rules, playbooks, hooks or the generator means files were removed or the install is partial: run `./setup.sh` (or `./install.sh`) again — both are idempotent. `--verify` never changes anything.

**`./setup.sh --rollback` refuses to run.**
It refuses on purpose when: there is no backup under `~/.claude-backups/`, the newest one has no `BACKUP-INFO.txt` (not made by setup.sh), two backups share the same timestamp (pass the one you mean: `./setup.sh --rollback <dir>`), or the backup was taken from a different config directory. Nothing is moved until those checks pass; when they do, the current `~/.claude` is moved aside, never deleted.

**The dashboard is empty, says "insufficient data", or the schedule does not run.**
The dashboard only counts tool-using tasks; a fresh install has none. `N/A` and "insufficient data" are deliberate — no metric is ever shown as 0% without data, and trends need at least five known outcomes in both the current and the previous period. Regenerate any time with `python3 ~/.claude/groundwork/bin/groundwork_report.py generate --snapshot`; check the schedule with `… status` and `launchctl print gui/$(id -u)/com.groundwork.report`. The launchd job exists only on macOS; on Linux run the generate command from cron. The generator never runs inside a hook, so a reporting failure cannot affect Claude Code.

**Telemetry records show `profile: unknown`.**
`GROUNDWORK_PROFILE` is not set in your `settings.json` `env`. `./setup.sh` sets it from the profile question; by hand: `python3 scripts/merge_settings.py --profile work ~/.claude/settings.json`. Profile is observed from that variable, never taken from the model's text.


**A Node-based CLI (`openspec`, `npx ...`) prints its output and then never returns control — Claude Code eventually reports it "moved to the background."**
Node 22.x on macOS can block at process exit while loading CA certificates from the system keychain (`SecTrustSettingsCopyTrustSettings`). `install.sh` sets `NODE_USE_SYSTEM_CA=0` in `settings.json`'s `env` block to work around this — it's harmless on Linux/Windows and only affects processes Claude Code itself launches. If you still see this outside Claude Code (e.g. running `openspec` directly in your own shell), add `export NODE_USE_SYSTEM_CA=0` to your shell profile, or set `NODE_EXTRA_CA_CERTS=<path>` if you need a corporate CA specifically.

**GateGuard blocks the first edit of a file, or the first Bash command of a session, asking for facts.**
This is ECC's own hook, not Groundwork's — it's asking you (or the agent) to state what's being changed and why before the first touch of something new. State the requested facts and retry the identical operation; it won't ask again for that file this session. For scratch/generated trees where this is pure friction, add a glob to `GATEGUARD_EXEMPT_GLOBS` (Groundwork's installer already exempts `*.md`/`*.txt`/`*.rst`). For setup or repair sessions where you want it off entirely, run with `ECC_GATEGUARD=off`.

**`require_material_review.py` is blocking and I don't understand why.**
It only fires when: an `openspec/changes/*/tasks.md` under the current directory has every box checked, AND `git status` shows that change directory as uncommitted/untracked. If both are true, dispatch any reviewer-shaped agent or skill against the diff — an `Agent`/`Task` call whose `subagent_type` or `name` contains "review" (a free-text `description` does not count) (an ECC reviewer, a project/user reviewer subagent, or an Agent Team reviewer teammate), or a `Skill` with "review" in its name — and the gate clears itself as soon as one runs, regardless of the verdict. If you believe this change genuinely doesn't need review, dispatch a reviewer anyway and let it say so; the gate enforces that review happened, not what it concluded. Claude Code itself stops re-running any Stop hook after 8 consecutive blocks, so a session can never be trapped.

**The session snapshot is missing, wrong, or too noisy.**
`groundwork_session_snapshot.py` runs at every SessionStart (startup, resume, clear, compact, fork) and only reports what it can read from the repository: git facts, `openspec/changes/*/tasks.md` checkbox counts, signal files, and verification commands declared in Makefile / package.json / pyproject / tox / nox / Go / Rust / Terraform / CI files. It emits nothing outside a git repo without `openspec/`, is capped at 2,500 characters, and fails open. Run it by hand to see exactly what it would inject:
```bash
echo '{"cwd":"'"$PWD"'"}' | python3 ~/.claude/hooks/groundwork_session_snapshot.py
```
Set `GROUNDWORK_SNAPSHOT=off` (shell or `settings.json` `env`) to disable it. A discovered command is a hint, not an instruction — the rules tell Claude to confirm it against the README before use.

**Claude formed an Agent Team for something small — or never forms one.**
Agent Teams are Claude Code's experimental feature and are off unless `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set (`./install.sh --agent-teams` sets it; the default install never does). With it on, any subagent Claude *names* launches as a teammate, so teams can form during ordinary delegation; set the variable to `0` to stop that. Teams never spawn in `-p` (non-interactive) sessions. Groundwork's rule (engineering-workflow.md §6) tells Claude when a team is justified and to fall back to subagents otherwise — that part is guidance, not a hook.

**`/opsx:*` commands aren't available in a project.**
Run `openspec init --tools claude` in that project's root once. `openspec update` refreshes the generated `.claude/commands/opsx/` and `.claude/skills/openspec-*/` files after an OpenSpec CLI upgrade.

**Hooks seem to fire twice, or rules seem to be applied twice.**
Never copy ECC's `hooks/hooks.json` content into your own `settings.json` — the plugin already registers it. Check with `claude --debug` and look for `Registered N hooks from M plugins`; Groundwork's own three hooks live only in `settings.json`, ECC's live only in its plugin manifest. For rules: if you upgraded from the pre-Groundwork harness, make sure `~/.claude/rules/harness/` no longer contains `engineering-workflow.md` / `evidence-policy.md` (the installer moves them to `~/.claude/backups/`) — Claude Code loads every `*.md` under `~/.claude/rules/` recursively.

**Session context feels heavy.**
Run `/context` to see the breakdown. ECC's agent/skill catalog is the dominant cost (roughly 20K tokens at session start, see [VALIDATION.md](VALIDATION.md)) and is paid whether or not any of it is used this session. Groundwork adds three rule files (~230 lines) plus at most 2.5 KB of snapshot. The only big lever is disabling the plugin for sessions that don't need it (`claude plugin disable ecc@ecc`, `claude plugin enable ecc@ecc` to bring it back) — `skillOverrides` in settings does not affect plugin-provided skills.

**A push was denied unexpectedly.**
`block_protected_push.py` resolves the target branch from an explicit refspec if you gave one, otherwise from the current branch. If you're on `main` locally and run a bare `git push`, it's denied for that reason even without a remote branch named in the command. Push a feature branch explicitly (`git push -u origin your-branch`) and open a PR instead.
