# Claude Code mods and Groundwork

Evaluated 2026-10-11. **Status: PARTIAL.** The source, licence, dependency and security review is
done (static only). Runtime checks (coexistence with Groundwork's statusLine and hooks, overhead,
rollback) need a real terminal session on a disposable machine and were **not** run: this
evaluation ran in a cloud container whose environment holds live session credentials, and a mod
runs with the user's permissions, so no third-party mod was loaded into a Claude Code session or run
there. The only thing run on a mod directory was Claude Code's own `claude plugin validate` (Flightdeck
and redgreen), which the docs describe as listing a mod's events and calls "without running it".

Nothing here installs, vendors or auto-enables a mod. Groundwork ships no mod code.

## What a mod is, and what it means for Groundwork (VERIFIED against the official docs)

Sources read 2026-10-11: https://code.claude.com/docs/en/plugins/mods/overview and
https://code.claude.com/docs/en/plugins/mods/events.

- A mod is a plugin of JavaScript/TypeScript event handlers that run inside Claude Code. Mods need
  Claude Code 2.1.287 or later and are on by default.
- "A mod is code that runs with your permissions." It can read your files and environment
  variables, start processes, make network requests, rewrite a prompt or tool call, and approve a
  tool call before you are asked. Mods are not sandboxed.
- **Order matters for Groundwork.** `PreToolUse` hooks from *managed settings* run before any mod
  and a block there is final. `PreToolUse` hooks from every *other* settings file, which is where
  Groundwork registers `block_protected_push.py`, run **after the last mod calls `next`**. A mod that
  answers a tool call without calling `next` keeps them from running, and a mod's `tool.check`
  handler can approve a call that such a hook blocked.
- Consequence: Groundwork's settings-file hooks do not defend against an installed mod. Treat
  installing a mod as installing trusted code. The same ordering applies to any other settings-file
  `PreToolUse` hook, including ECC's (INFERENCE: how ECC registers its hooks was not checked).
  `Stop` hooks (review gate, telemetry): the docs' own `classic.Stop` example ends "Pass the event on,
  so Stop hooks in your settings files still run", so a mod that does not pass it on probably keeps
  them from running (INFERENCE; not stated explicitly and not tested).
- **`permissions.deny` rules** (Groundwork installs several, such as `Bash(git push --force*)` and
  `Bash(sudo *)`): per https://code.claude.com/docs/en/plugins/mods/admin ("Know what happens by
  default"), a user's mod can't approve a call that a `deny` rule refuses *where the built-in guard
  loads*, which is a machine with managed settings or a Team/Enterprise sign-in. For an API-key or
  cloud-provider login the guard loads only with managed settings; for a personal plan that page does
  not say (UNVERIFIED). Where the guard does not load, this protection does not apply. Deny rules
  also do not constrain a mod's own `$.fs` / `$.process` calls.
- Controls the docs name: disable one mod in `/plugin` → Installed; `--safe-mode` (one session,
  all customizations off); `"disableAllHooks": true` (stops every installed mod, **and also
  Groundwork's hooks and statusLine**); `allowManagedModsOnly`, an option of the built-in guard that is read from **managed settings only**:
  `pluginConfigs["cc-plugin-sec-default@builtin"].options.allowManagedModsOnly`. The same entry in a
  user, project or local settings file, or via `--settings`, "changes nothing", so an individual user
  cannot enforce it on their own machine. `claude plugin validate <dir>` lists a mod's events and API calls "without running
  it".

## Evaluation

Commits pinned below were the remote `HEAD` of each repository when checked (`git ls-remote`,
2026-10-11) and match what was reviewed. All five are MIT-licensed (LICENSE files read).

| Project | Pinned commit | Calls beyond UI/state | Effect on execution or authorization | Verdict |
|---|---|---|---|---|
| Flightdeck (scasella/claude-flightdeck) | `f31daca523d36c501cd0df23a737a44c7dc56ad6` | `claude plugin validate` listed only `$.clock.now`, `$.command.register`, `$.session.usage`, `$.state.get/set`, `$.ui.*`; no `fs`, `http` or `process` calls; source has no Node built-ins, `eval` or network references | Registers hooks in the permission path (`tool.check`, `tool.call`, `agent.spawn`, `agent.offer`, …). The `tool.check` and `tool.call` handlers were read by hand: both call `next(e)` and return its result unchanged (`hooks/register.tsx:357-376`, `379-421`). Its own status line shows only `ctx N%`, agent count, architect state and a denial count (cost and model appear only in its pane; `register.tsx:131-145`). Overlaps Groundwork's statusLine on context % (and on cost when `show_cost` is on); Groundwork's statusLine has no model field | **ADOPT-AFTER-TEST** |
| redgreen (hellosverre/redgreen) | `cdc4fa37ec707f3d9c7fa88810128ed96b8d73e5` | validator listed `$.fs.read` (reads the persisted test output) plus clock, command, state, `$.ui.*` | `tool.call` hooks for Bash/PowerShell have `.catch` and pass through; adds a "tests ✗" status line that overlaps Groundwork's validation field. Marginal value | **ADOPT-AFTER-TEST** (optional) |
| mdview (xuanji86/claude-mdview) | `da646556714507acf5d41610605b9911eb9aa42a` | `$.prompt.submit` (`hooks/register.tsx:400`), `$.tool.register` (`:439`), `$.process.run` (`:134,176,381`), `$.config.set` (`:514`), `$.env.get('HOME')` (`:84`), `$.fs.stat`/`$.fs.read` of local files (`:106,142,175,226`) | Submits prompts as the user and registers a tool Claude can call: not visual-only | **DEFER** |
| Skins (hellosverre/claude-skins) | `dccf562424e4633c94e158978d467080c62c889d` | `$.http.fetch` (`hooks/register.tsx:433`), `$.tool.register` (`:506`), `prompt.compose` system-prompt text (`:934`), `$.process.run`, `$.env.get` of terminal variables (`:149-151,239-244`) | Network access, model-facing text, and it replaces how tool rows and results render (reported to fold long shell output by default) | **REJECT** (violates the selection rules) |
| ClaudePanel (adripoli/ClaudePanel) | `f9ade14e0607e39ba99a83ee0f133a6cc4669ce6` | Not a Claude Code mod: a standalone Python TUI. Dependency `textual>=0.80` is unpinned (`pyproject.toml:16`) | Reads session transcripts (reported); can launch sessions. Not listed in the awesome-claude-code-mods index (0 matches) | **DEFER** |

Selection rules applied (from the owner): visual/observability only; no approval, policy bypass,
hidden execution or unsafe network access; audited source, dependencies and licences; pinned
commits; keep third-party mods separate from Groundwork's core.

### How much of this I checked myself

- Checked directly: the official docs text above; pinned SHAs against the remote; licences; the
  `claude plugin validate` output for Flightdeck and redgreen (both "Validation passed"); the
  Flightdeck `tool.check`/`tool.call` handlers; the call sites and line numbers cited for mdview,
  Skins and ClaudePanel.
- Confirmed by a second, independent reviewer reading the source (not re-read by me): Flightdeck's
  other hooks and redgreen's `tool.call` hooks pass events through; Skins' vendored diagram library
  is 83,909 bytes and its README documents shell-output folding; ClaudePanel reads
  `~/.claude/projects/*/<id>.jsonl` and launches `claude` through `osascript`.
- Reported only, UNVERIFIED: repository age, star counts, release status, and the awesome index's
  third-party scan badges.
- `claude plugin validate` is documented as static. Its output also flagged "gating hook without
  .catch" on Flightdeck's permission-path hooks: if one of them threw, Claude Code would skip it
  and continue (fail-open), which is acceptable for an observer.

## Trial procedure (owner's disposable machine, not a company environment)

A company environment needs separate security approval first (`allowManagedModsOnly` may forbid
user mods there anyway).

1. Clone the repository, check out the pinned commit, run `claude plugin validate <dir>`, and
   compare the `hooks:` and `calls:` lines with the table. Any `fs.write`, `http`, `process` or
   `env` call you did not expect means stop.
2. Baseline with Groundwork installed and no mod: hash of `~/.claude/settings.json`, the statusLine
   output, time to first prompt, and confirm Groundwork's guard blocks `git push origin main`.
3. Load for one session only: `claude --plugin-dir <dir>` (session-only, so nothing is written to
   settings). `/plugin` should show "1 mod active".
4. Observe: does Groundwork's statusLine still render, and does the mod's own status line appear
   as a second row (the docs are silent, so this is RUNTIME VALIDATION REQUIRED); startup and
   per-call overhead against the baseline; the push guard, review gate and telemetry still behave
   as in step 2; network egress is zero from the mod (use a proxy or `tcpdump`).
5. Rollback: end the session and confirm the settings hash is unchanged. Do not use
   `disableAllHooks` as a rollback, because it also disables Groundwork.
6. Run the mod's own tests (`claude plugin test <dir>`) only on this machine; that command runs the
   mod's code.

## Not done

- No runtime test of any mod (the ordering above is documented behaviour, not observed), so the milestone's acceptance ("improves readability in a real
  session, preserves safety behaviour, can be disabled independently") is **not demonstrated**.
- No Groundwork code change: no integration was justified without that evidence. A future
  `groundwork doctor` warning for installed non-built-in mods is possible but would need a
  reliable way to tell a mod from an ordinary plugin; not built.
