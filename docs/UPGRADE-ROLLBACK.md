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

# Groundwork itself
cd groundwork && git pull
./install.sh                 # idempotent — re-copies rules/hooks, re-merges settings.json
./install.sh --agent-teams   # same, plus opt in to Claude Code's experimental Agent Teams
```

After upgrading ECC specifically, check `claude plugin details ecc@ecc` for changes to its hook list or context cost before assuming nothing else needs attention — see [docs/VALIDATION.md](VALIDATION.md) for what "normal" looks like.

### Upgrading from 1.0.0 (or from the pre-Groundwork personal harness)

`install.sh` now looks for the pre-Groundwork copy of the two rules under `~/.claude/rules/harness/`. If found, they are **moved, not deleted**, to `~/.claude/backups/groundwork-legacy-<timestamp>/`, because Claude Code loads every `*.md` under `~/.claude/rules/` recursively and would otherwise load each rule twice. The installer prints a notice if `~/.claude/CLAUDE.md` still points at `rules/harness` — update that pointer yourself to `~/.claude/rules/groundwork/`; the installer never edits a user-authored file.

Nothing else changes for a 1.0.0 install: the same three keys are merged, plus one new `hooks.SessionStart` entry for the snapshot hook.

## Rolling back

**Groundwork only** (keep ECC and OpenSpec):
```bash
cd groundwork && ./uninstall.sh                 # removes rules/groundwork, the 3 hooks, our settings entries
cd groundwork && ./uninstall.sh --agent-teams   # also removes CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS when it is "1"
```
Removes `~/.claude/rules/groundwork/`, the three hook files, and the specific `settings.json` entries `install.sh` added — leaves everything else in `settings.json` untouched (see `scripts/unmerge_settings.py`). One documented limitation: a value you had set yourself that equals the installer's default — a `permissions.deny` rule that is also one of Groundwork's (for example `Bash(sudo *)`), an env default with the same value, or `pluginConfigs["ecc@ecc"].options.hook_profile: "standard"` — is removed too, because the unmerge is stateless; re-add it afterwards. A migrated legacy copy is not restored automatically — it is in `~/.claude/backups/`.

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
