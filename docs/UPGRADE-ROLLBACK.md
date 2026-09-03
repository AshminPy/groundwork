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
./install.sh    # idempotent — re-copies rules/hooks, re-merges settings.json
```

After upgrading ECC specifically, check `claude plugin details ecc@ecc` for changes to its hook list or context cost before assuming nothing else needs attention — see [docs/VALIDATION.md](VALIDATION.md) for what "normal" looks like.

## Rolling back

**Groundwork only** (keep ECC and OpenSpec):
```bash
cd groundwork && ./uninstall.sh
```
Removes `~/.claude/rules/groundwork/`, the two hook files, and the specific `settings.json` entries `install.sh` added — leaves everything else in `settings.json` untouched (see `scripts/unmerge_settings.py`).

**Everything** (ECC and OpenSpec too):
```bash
./uninstall.sh
claude plugin uninstall ecc@ecc
claude plugin marketplace remove ecc
npm uninstall -g @fission-ai/openspec
```

None of this touches your projects' own `openspec/` directories or their committed history — those are ordinary files in your repos, not managed by any of the above.

## If something's actually broken, not just unwanted

1. Confirm which layer is responsible: `claude --debug` shows `Registered N hooks from M plugins` at startup — Groundwork's two hooks appear as plain `settings.json` entries (not attributed to a plugin), ECC's appear attributed to the `ecc` plugin.
2. Temporarily disable just Groundwork's hooks without uninstalling: remove the two `hooks.PreToolUse`/`hooks.Stop` entries from `settings.json` by hand, or set `ECC_DISABLED_HOOKS` if the issue is actually an ECC hook (see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — the two projects' hooks are easy to mistake for each other).
3. File Groundwork-specific issues (rules/hooks/scripts/docs under this repo) against this repository. File ECC or OpenSpec issues against their own repositories — this project has no ability to fix bugs upstream.
