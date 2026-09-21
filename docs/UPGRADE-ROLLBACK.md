# Upgrade and rollback

## Upgrading

```bash
# ECC
claude plugin update ecc@ecc
# then restart Claude Code, or run /reload-plugins in an active session

# OpenSpec CLI (global)
npm install -g @fission-ai/openspec@latest
# then, per project that uses it:
cd your-project && openspec update

# Groundwork itself — recommended: the wrapper backs up ~/.claude first, then re-installs and verifies
cd groundwork && git pull
./setup.sh                   # asks profile / Agent Teams / schedule again (answers are idempotent)
./setup.sh --non-interactive --profile work --schedule weekly   # scripted; add --agent-teams if you use it

# or the installer alone (no backup, no questions)
./install.sh                 # idempotent — re-copies rules/hooks/playbooks/generator, re-merges settings.json
./install.sh --agent-teams   # same, plus opt in to Claude Code's experimental Agent Teams
```

Every `./setup.sh` run leaves a new complete backup under `~/.claude-backups/groundwork-<timestamp>/` (owner-only, never overwritten). Check the result any time with `./setup.sh --verify`. Prerequisites that went missing (git, Node 18+, npm, Python 3.10+) are offered for installation by `setup.sh`; Claude Code itself is never installed by it.

After upgrading ECC specifically, check `claude plugin details ecc@ecc` for changes to its hook list or context cost before assuming nothing else needs attention — see [docs/VALIDATION.md](VALIDATION.md) for what "normal" looks like.

### Upgrading from 1.0.0 (or from the pre-Groundwork personal harness)

`install.sh` now looks for the pre-Groundwork copy of the two rules under `~/.claude/rules/harness/`. If found, they are **moved, not deleted**, to `~/.claude/backups/groundwork-legacy-<timestamp>/`, because Claude Code loads every `*.md` under `~/.claude/rules/` recursively and would otherwise load each rule twice. The installer prints a notice if `~/.claude/CLAUDE.md` still points at `rules/harness` — update that pointer yourself to `~/.claude/rules/groundwork/`; the installer never edits a user-authored file.

Nothing else changes for a 1.0.0 install: the same keys are merged, plus the `hooks.SessionStart` snapshot entry (1.1.0), the `hooks.Stop` telemetry entry (1.3.0), the report generator and its launchd schedule (1.4.0), and `env.GROUNDWORK_PROFILE` when a profile is chosen (1.5.0).

## Rolling back

**Back to exactly the `~/.claude` you had before Groundwork** (time machine):
```bash
cd groundwork && ./setup.sh --rollback                                   # latest setup.sh backup
cd groundwork && ./setup.sh --rollback ~/.claude-backups/groundwork-20260921-144500   # a specific one
```
The current `~/.claude` is moved to `~/.claude-groundwork-disabled-<timestamp>/` first (never deleted), the launchd report job is removed, the backup is copied back and checked for readability, and the script prints exactly what it restored. It refuses to guess when two backups share a timestamp or when a backup was taken from a different config directory. Restart Claude Code afterwards. Anything written to `~/.claude` after the backup — newer telemetry, session history — is in the disabled copy, not lost.

**Groundwork only, keep everything else as it is now** (eraser):
```bash
cd groundwork && ./setup.sh --uninstall           # same as ./uninstall.sh
cd groundwork && ./uninstall.sh                   # removes rules/groundwork, playbooks, the 4 hooks, the report generator and its launchd job, our settings entries
cd groundwork && ./uninstall.sh --agent-teams     # also removes CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS when it is "1"
```
Removes `~/.claude/rules/groundwork/`, `~/.claude/groundwork/playbooks/`, `bin/` and `VERSION`, the four hook files, the `com.groundwork.report` launchd job, and the specific `settings.json` entries `install.sh`/`setup.sh` added (including `env.GROUNDWORK_PROFILE`); keeps `~/.claude/groundwork/telemetry/` and `reports/` (your data) — leaves everything else in `settings.json` untouched (see `scripts/unmerge_settings.py`). One documented limitation: a value you had set yourself that equals the installer's default — a `permissions.deny` rule that is also one of Groundwork's (for example `Bash(sudo *)`), an env default with the same value, or `pluginConfigs["ecc@ecc"].options.hook_profile: "standard"` — is removed too, because the unmerge is stateless; re-add it afterwards. A migrated legacy copy is not restored automatically — it is in `~/.claude/backups/`.

**Everything** (ECC and OpenSpec too):
```bash
./uninstall.sh
claude plugin uninstall ecc@ecc
claude plugin marketplace remove ecc
npm uninstall -g @fission-ai/openspec
```

None of this touches your projects' own `openspec/` directories or their committed history — those are ordinary files in your repos, not managed by any of the above.

## If something's actually broken, not just unwanted

1. Confirm which layer is responsible: `claude --debug` shows `Registered N hooks from M plugins` at startup — Groundwork's three hooks appear as plain `settings.json` entries (not attributed to a plugin), ECC's appear attributed to the `ecc` plugin.
2. Temporarily disable just one Groundwork hook without uninstalling: remove its entry from `hooks.PreToolUse` / `hooks.Stop` / `hooks.SessionStart` in `settings.json` by hand, or set `GROUNDWORK_SNAPSHOT=off` for the snapshot hook. If the issue is actually an ECC hook, use `ECC_DISABLED_HOOKS` (see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — the two projects' hooks are easy to mistake for each other).
3. File Groundwork-specific issues (rules/hooks/scripts/docs under this repo) against this repository. File ECC or OpenSpec issues against their own repositories — this project has no ability to fix bugs upstream.
