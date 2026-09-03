# Troubleshooting

**A Node-based CLI (`openspec`, `npx ...`) prints its output and then never returns control — Claude Code eventually reports it "moved to the background."**
Node 22.x on macOS can block at process exit while loading CA certificates from the system keychain (`SecTrustSettingsCopyTrustSettings`). `install.sh` sets `NODE_USE_SYSTEM_CA=0` in `settings.json`'s `env` block to work around this — it's harmless on Linux/Windows and only affects processes Claude Code itself launches. If you still see this outside Claude Code (e.g. running `openspec` directly in your own shell), add `export NODE_USE_SYSTEM_CA=0` to your shell profile, or set `NODE_EXTRA_CA_CERTS=<path>` if you need a corporate CA specifically.

**GateGuard blocks the first edit of a file, or the first Bash command of a session, asking for facts.**
This is ECC's own hook, not Groundwork's — it's asking you (or the agent) to state what's being changed and why before the first touch of something new. State the requested facts and retry the identical operation; it won't ask again for that file this session. For scratch/generated trees where this is pure friction, add a glob to `GATEGUARD_EXEMPT_GLOBS` (Groundwork's installer already exempts `*.md`/`*.txt`/`*.rst`). For setup or repair sessions where you want it off entirely, run with `ECC_GATEGUARD=off`.

**`require_material_review.py` is blocking and I don't understand why.**
It only fires when: an `openspec/changes/*/tasks.md` under the current directory has every box checked, AND `git status` shows that change directory as uncommitted/untracked. If both are true, dispatch any reviewer-shaped agent or skill (anything with "review" in its name) against the diff — the gate clears itself as soon as one runs, regardless of the verdict. If you believe this change genuinely doesn't need review, dispatch a reviewer anyway and let it say so; the gate enforces that review happened, not what it concluded.

**`/opsx:*` commands aren't available in a project.**
Run `openspec init --tools claude` in that project's root once. `openspec update` refreshes the generated `.claude/commands/opsx/` and `.claude/skills/openspec-*/` files after an OpenSpec CLI upgrade.

**Hooks seem to fire twice.**
Never copy ECC's `hooks/hooks.json` content into your own `settings.json` — the plugin already registers it. Check with `claude --debug` and look for `Registered N hooks from M plugins`; Groundwork's own two hooks live only in `settings.json`, ECC's live only in its plugin manifest.

**Session context feels heavy.**
Run `/context` to see the breakdown. ECC's agent/skill catalog is the dominant cost (roughly 20K tokens at session start, see [VALIDATION.md](VALIDATION.md)) and is paid whether or not any of it is used this session. The only lever is disabling the plugin for sessions that don't need it (`claude plugin disable ecc@ecc`, `claude plugin enable ecc@ecc` to bring it back) — `skillOverrides` in settings does not affect plugin-provided skills.

**A push was denied unexpectedly.**
`block_protected_push.py` resolves the target branch from an explicit refspec if you gave one, otherwise from the current branch. If you're on `main` locally and run a bare `git push`, it's denied for that reason even without a remote branch named in the command. Push a feature branch explicitly (`git push -u origin your-branch`) and open a PR instead.
