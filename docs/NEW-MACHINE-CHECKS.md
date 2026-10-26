# New-machine checks (any laptop, including a managed work laptop)

About 10 minutes, after `./install.sh` (or `groundwork update`). These checks confirm on *this* machine that the
evidence and continuity features actually run. Unit tests cannot show that, because a machine's own policy can turn
hooks off. Feature names refer to `openspec/changes/core-evidence-continuity/`.

## 0. Is anything stopping hooks on this machine? (do this first on a work laptop)

In Claude Code, run `/status` and read the `Setting sources` line. If it names a managed source (MDM,
`managed-settings.json`, or server-managed settings), ask your administrator, or check the policy, for these two keys:

| Key | Effect on Groundwork | Source |
|---|---|---|
| `allowManagedHooksOnly` (managed only) | none of Groundwork's hooks run: no reply check, no task brief, no telemetry, no push guard | [settings reference](https://code.claude.com/docs/en/settings-reference#allowmanagedhooksonly) |
| `disableAllHooks` (any file) | hooks **and** the custom statusLine are off, so there are also no usage records | [settings reference](https://code.claude.com/docs/en/settings-reference#disableallhooks) |

If either is set, Groundwork's rules still load, but nothing is enforced. Treat every check below as "not
available on this machine", not as a Groundwork bug.

```bash
claude doctor        # lists settings entries Claude Code rejected
groundwork doctor    # Groundwork's own install check
```

## 1. Reply format check (feature 6)

In a git repo, ask for something that runs a command, for example "run `git status` and tell me the branch in one
word".

Pass: if the first reply lacks `Technical details`, a reference or `HARNESS METADATA`, Claude adds them in one
follow-up. The app shows this as "Stop hook error"; that is Claude Code's label for any Stop-hook request. A plain
question with no tools ("what is 2+2?") gets no follow-up. Off switch: `GROUNDWORK_REPLY_CHECK=off`.

## 2. Usage visibility (feature 2)

Use Claude Code normally for a few minutes in two sessions, then run:

```bash
groundwork usage
groundwork usage --window 7d
```

Pass: both sessions are listed, and a plan line is shown. On a personal Pro/Max account it reads
`5h NN% · 7d NN%`. Behind a company Claude apps gateway it reads `spend limit NN%`. The statusLine shows `5h NN%` or
`spend NN%`. If neither line appears, Claude Code is not sending `rate_limits` on this account; the ranking by cost
still works. Records live in `~/.claude/groundwork/telemetry/usage.jsonl` (owner-only, ids and numbers only).

## 3. Task brief (feature 3)

In a git repo, do a few tool-using turns of real work. Then:

```bash
ls ~/.claude/groundwork/briefs/*/
```

Pass:
- a `<branch>-<hash>.md` file exists with a `## Snapshot (hook-written …)` section;
- after three tool-using turns with an empty brief, Claude is asked once to write Goal and Next step;
- after `/compact`, or in a brand-new session on the same branch, ask "what is the next step in the task brief?".
  Claude answers from the brief without reading any file.

Off switch: `GROUNDWORK_BRIEF=off`. Briefs are kept on uninstall (your data).

## Report

For each step write pass, fail, or not available (step 0), and paste the exact output of any failure.
