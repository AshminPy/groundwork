# Terminal Copilot — LOCAL EXPERIMENT ONLY

> **This is NOT a Groundwork feature.** It is an unmerged, local-only prototype
> living on branch `experimental/terminal-copilot-mvp`. It is not installed by
> `install.sh`/`setup.sh`, not referenced by any Groundwork CLI command, and
> must not be merged to `main` until the UX and security model are proven on
> real hardware by a human.
>
> **This prototype was designed and written from a remote Linux container
> with no macOS, no microphone, no GUI, and no Hammerspoon runtime.** It has
> NOT been runtime-tested. Every "test" in this directory is a *procedure for
> a human to run on their own Mac*, not a result this session produced. Do
> not treat anything here as validated until you have actually run it.

## What this is

A minimal, local companion that lets you:

1. Press one global hotkey, from any terminal (including one opened after
   the companion started).
2. Speak a short, natural request ("Claude, help me with this error").
3. Have it transcribed locally and sent to Claude together with a small,
   sanitized snapshot of *that specific terminal's* context (cwd, repo, git
   branch, shell, last command).
4. Get back a short explanation and (if applicable) a suggested command,
   copied to your clipboard — **never executed automatically**.

## What this deliberately does NOT do (MVP scope)

- No continuous microphone — recording only starts on hotkey press, stops
  automatically after a short bounded duration.
- No screen recording, no browser automation, no keyboard injection.
- No automatic command execution. "RUN" and "EDIT" both resolve to
  **copy the command to your clipboard** — you paste and run it yourself.
  (See `docs/DECISIONS.md` for why a scripted-send-to-pane mechanism was
  considered and deliberately NOT implemented in this MVP.)
- No capture of command *output* (stdout/stderr), environment variables,
  shell history beyond the single last command line, or credentials. See
  `docs/DECISIONS.md` for why — this was scoped down intentionally, not
  an oversight.
- No Hands-Free mode, no wake words, no TTS, no Take Control, no autonomous
  execution. Those are explicitly out of scope for this MVP.
- Only Terminal.app and iTerm2 are supported. Any other frontmost
  application (including other terminal emulators) is refused with a clear
  message rather than silently guessing.

## Components reused (not reimplemented)

- **Hammerspoon** (macOS automation, you install separately) — global
  hotkey + frontmost-window/application identification.
- **faster-whisper** (local Whisper STT, MIT license, you install
  separately) — speech-to-text, fully local.
- **The `claude` CLI you already have installed** (official, supported
  Claude Code interface) — headless one-shot call in `--permission-mode
  plan` (suggest-only, never executes).

Nothing here reimplements speech recognition, text-to-speech, or Claude's
own reasoning.

## Directory layout

```
experimental/terminal-copilot/
  README.md                        this file
  docs/DECISIONS.md                design decisions and why
  hammerspoon/terminal_copilot.lua Hammerspoon module (hotkey, binding, overlay)
  hammerspoon/local_config.lua.example   copy to local_config.lua, gitignored
  shell/context-hook.sh            sourced from .zshrc/.bashrc
  bin/copilot_orchestrator.py      STT + context + Claude call, invoked by Hammerspoon
  install-local.sh                 symlinks/sources the above (asks before each step)
  uninstall-local.sh               removes everything install-local.sh added
  tests/MANUAL_TEST_PROCEDURE.md   TEST 1-7 + security validation, run by a human on a Mac
```

## Install (on your own Mac — never run this in a CI/remote/shared environment)

See `install-local.sh`. It is interactive and explains each step before
doing it; it does not use `curl | sh`, does not request sudo, and does not
touch anything outside your home directory and your shell rc file (with a
clearly delimited, removable block).

## Status

Code written and statically reviewed (see the independent-review note in
the top-level report for this task). **Not yet runtime-validated.** Follow
`tests/MANUAL_TEST_PROCEDURE.md` on a real Mac before relying on this for
anything, and before considering it for a real Groundwork proposal.
