# Manual test procedure — run this on your own Mac

**None of these tests have been run.** They were written by a session with no
macOS, no microphone, and no Hammerspoon runtime available. This document is
a procedure for a human to execute, not a report of results. Fill in the
"Result" line under each test yourself.

## Before you start

- Use a disposable environment if possible: a spare machine, a VM, or a
  fresh scratch macOS user account — not your primary work account, per the
  task's isolation requirement.
- Use throwaway scratch repos, never a real project:
  ```sh
  mkdir -p ~/scratch/repo-a ~/scratch/repo-b ~/scratch/repo-c
  (cd ~/scratch/repo-a && git init -q && git commit -q --allow-empty -m init)
  (cd ~/scratch/repo-b && git init -q && git commit -q --allow-empty -m init)
  (cd ~/scratch/repo-c && git init -q && git commit -q --allow-empty -m init)
  ```
- **Read `install-local.sh` and `uninstall-local.sh` in full before running
  them.** They are not curl-pipe-bash and do not need to be, but read any
  install script before running it as a matter of habit.
- Grant microphone/Accessibility permissions only when macOS actually
  prompts for them during use, not preemptively.
- Do not use real/work Claude credentials if you have a disposable account
  available; otherwise be aware real API usage will occur.

## TEST 1 — Basic

1. Open Terminal A, `cd ~/scratch/repo-a`.
2. Press the activation hotkey, say: "Tell me what repository I'm in."
3. **Expected**: the response correctly identifies `repo-a`.
4. **Result**: _____________________________________________

## TEST 2 — Multi-terminal isolation

1. Open three terminals: A → `~/scratch/repo-a`, B → `~/scratch/repo-b`,
   C → `~/scratch/repo-c`.
2. Activate independently from each, asking the same basic question.
3. **Expected**: A gets repo-a's context, B gets repo-b's, C gets repo-c's.
   Zero cross-routing.
4. **Result**: _____________________________________________

## TEST 3 — Focus change mid-processing

1. Activate from Terminal A.
2. Immediately (before the response appears) click into Terminal B.
3. **Expected**: the response, when it arrives, is still labeled as
   belonging to Terminal A (check the TTY/cwd shown in the overlay).
4. **Result**: _____________________________________________

## TEST 4 — Fresh terminal, never registered

1. With the companion already running (Hammerspoon loaded, hotkey live),
   open a brand-new Terminal window D — do not configure anything for it.
2. Activate from D immediately.
3. **Expected**: it works without any manual setup step for D specifically
   (the shell hook applies automatically via the already-edited `.zshrc`/
   `.bashrc`, and the TTY-binding mechanism needs no per-terminal setup).
4. **Result**: _____________________________________________

## TEST 5 — Error context

1. In a scratch repo, generate a harmless, known error — e.g.
   `ls /definitely/does/not/exist`.
2. Activate and say: "I just got a file-not-found error, explain it and
   tell me what to check."
3. **Expected**: Claude's explanation reflects the actual repo/cwd context
   and gives a sensible response given the *verbal* description (remember:
   command output is NOT auto-captured in this MVP — see docs/DECISIONS.md
   #3 — so the spoken description is what carries the error detail).
4. **Result**: _____________________________________________

## TEST 6 — Safety: no automatic execution

1. Activate and ask for a harmless sentinel command, e.g.: "Give me a
   command that creates an empty file called copilot-test-sentinel.txt in
   the current directory."
2. **Expected**: the file does NOT appear until you manually paste the
   clipboard contents into the terminal and press enter yourself. Confirm
   with `ls` before and after.
3. **Result**: _____________________________________________

## TEST 7 — Concurrency

1. Activate from Terminal A; before its response arrives, activate from
   Terminal B.
2. **Expected**: each response stays associated with its own terminal
   (check both overlays' labeled TTY/cwd). If the architecture serializes
   requests instead of truly running them concurrently, that is an
   acceptable MVP limitation — but note it in the result, since the task
   asked this to be proven "where architecture supports it."
3. **Result**: _____________________________________________

## Security validation checklist

Verify each of these directly, not by trusting the code comments:

- [ ] Microphone is active only during activation, not continuously —
      check Activity Monitor / the menu-bar mic indicator before and after
      a request completes.
- [ ] No environment variables appear in `~/.groundwork-copilot/sessions/*.json`
      — inspect a context file directly after visiting a terminal with a
      distinctive env var set (e.g. `export CANARY_SECRET=abc123`) and
      confirm `CANARY_SECRET`/`abc123` never appears in any context file.
- [ ] No secrets captured — same test as above, with something that looks
      like a credential in a command's text (not output) — e.g. run
      `echo "token=ghp_FAKE1234"` as the "last command" and confirm that
      literal string doesn't propagate anywhere persisted beyond the
      context file's `last_command` field (which is expected, bounded, and
      user-visible — the point is to confirm nothing ELSE leaks it).
- [ ] Bounded terminal output — confirm no file anywhere under
      `~/.groundwork-copilot/` ever exceeds a few KB; nothing should be
      logging unbounded output.
- [ ] No automatic execution — re-confirm via TEST 6.
- [ ] No unexpected network destinations — run with a network monitor
      (Little Snitch, or `sudo lsof -i` right after an activation) and
      confirm the only outbound connection is whatever the `claude` CLI
      itself makes (Anthropic's API) — nothing from faster-whisper, nothing
      from the orchestrator itself.
- [ ] No persistent credentials — confirm `~/.groundwork-copilot/` contains
      no API keys, tokens, or `claude` auth material; it should only ever
      contain the orchestrator script, the shell hook copy, and per-TTY
      context JSON files.
- [ ] No background privileged service — confirm no `launchctl` entries or
      systemd-equivalent were installed; this is Hammerspoon triggering a
      one-shot Python process per activation, nothing resident beyond
      Hammerspoon itself (which you already run for other reasons or chose
      to install).
- [ ] No sudo — confirm `install-local.sh`/`uninstall-local.sh` never
      prompted for your password.
- [ ] No cross-terminal context leakage — re-confirm via TEST 2.

## After testing

Run `uninstall-local.sh` and confirm: the Hammerspoon symlinks are gone,
the marked blocks are removed from your shell rc files and `init.lua`, and
`~/.groundwork-copilot/` no longer exists (if you chose to delete it).
