# Design decisions — Terminal Copilot MVP

Each decision below trades some UX polish for a materially simpler, safer,
or more honestly-scoped implementation. This file exists so a reviewer (or
a future session) can see the reasoning, not just the code.

## 1. Terminal identity: TTY device path, captured at activation time

**Decision**: the binding key between "which terminal did this request come
from" and "which terminal should the answer go to" is the terminal's **TTY
device path** (e.g. `/dev/ttys003`), not a focus-polling mechanism.

**Why**: both Terminal.app and iTerm2 can report, via their own scripting
interfaces, which TTY the frontmost window/tab is connected to (Terminal.app:
AppleScript `tty of front window`; iTerm2: the `tty` property on the current
session, available via AppleScript or the Python API). Every shell can
report its own TTY via the `tty` builtin. This means:

- The shell hook (`shell/context-hook.sh`) writes a context file *named by
  its own TTY* on every prompt.
- Hammerspoon, at the instant the hotkey fires, asks the frontmost terminal
  app "what TTY is your front window/tab on" and passes that TTY string as
  a fixed argument to the orchestrator.
- The orchestrator never re-queries "what's focused now" — it only ever
  acts on the TTY it was told at the start. If the user switches focus to
  another terminal while Claude is thinking, it has no effect: the TTY was
  already fixed before any work began.

This satisfies "capture terminal identity AT ACTIVATION TIME" exactly,
without needing continuous focus-polling or risking a race condition at
delivery time.

**Rejected alternative**: polling `hs.application.frontmostApplication()`
again when the response arrives. This would silently misroute if focus
changed in between — exactly the bug the task explicitly called out to
avoid.

## 2. Delivery mechanism: clipboard only, no scripted send, no keystroke injection

**Decision**: "RUN" and "EDIT" both resolve to the same action — the
suggested command is copied to the system clipboard, and the overlay shows
which terminal (by TTY + cwd) it belongs to, so you can visually confirm
before pasting it into the right window yourself.

**Why**: the task explicitly says "if placing the command directly into the
shell input buffer requires fragile keystroke injection, STOP and evaluate a
safer alternative." Two real, non-"fragile" mechanisms do exist — Terminal.app's
`do script "<cmd>" in window id <id>` and iTerm2's Python API
`session.async_send_text()` — and the OSS research (see the research report
from the prior task) confirmed these are reliable, not UI-level keystroke
simulation. They were deliberately **not implemented in this MVP** anyway,
for a different reason: adding a second code path that can inject text into
a live shell is a meaningfully larger trust surface than a read-only
suggestion tool, and the MVP's job is to prove the *harder* problem (correct
binding across concurrent terminals) first. Clipboard-copy has zero
injection risk, is trivially auditable, and fully satisfies "execution must
remain OFF by default" with no judgment calls about edge cases.

**If the MVP proves out**: a scripted-send-to-pane "RUN" action, gated by
re-confirming the target terminal is still open and re-verifying the TTY
match at the moment of the click (not assumed from activation time), is the
natural next increment — explicitly deferred, not forgotten.

## 3. Context scope: no automatic command-output capture

**Decision**: captured context is limited to: TTY, cwd, repo root (if any),
git branch (if any), shell name, the single last command line, and its exit
code. **Command output (stdout/stderr) is not captured automatically.**

**Why**: reliably capturing a command's output without unbounded risk means
either wrapping the entire shell session in a PTY logger (`script(1)`-style)
from login, which changes how the user's whole terminal behaves and makes
bounding/sanitizing output much harder to guarantee, or doing fragile
redirection tricks (`exec > >(tee ...)`) that can break interactive programs
and still risk capturing secrets printed to the terminal. Both conflict
directly with "do not capture unbounded terminal buffers" and "sanitize
context before sending it." The safer, honest MVP choice: let the user's own
spoken request carry the error context ("I just ran terraform plan and got
an AWS auth error, help me fix it") — Claude can usually do a great deal
with the last command + exit code + repo context + a verbal description,
without the system ever touching the user's terminal output stream.

This is a real, documented limitation (see the top-level report's "remaining
material limitations"), not an oversight.

## 4. Claude interface: the installed `claude` CLI, one-shot, suggest-only

**Decision**: the orchestrator shells out to the user's own already-installed
`claude` CLI headlessly: `claude -p "<prompt>" --permission-mode plan`.

**Why**: "no custom Claude reasoning/runtime, reuse existing mature
components." A one-shot headless call with plan-mode (suggest-only, no tool
execution) is the officially supported, simplest integration point for
exactly this "one request, one answer" shape — no SDK dependency, no session
lifecycle to manage, inherits whatever auth the user's own `claude` CLI
already has configured. A persistent Agent-SDK-owned session (as Backtalk
uses) is the right architecture for a *conversational* Hands-Free mode later,
but is unnecessary complexity for a single-turn suggestion tool.

## 5. Supported terminals: Terminal.app and iTerm2 only

**Decision**: any other frontmost application is refused with a clear
message, not silently guessed at.

**Why**: "do not claim support for a terminal unless routing is reliable."
Only these two expose a scriptable, queryable TTY-for-frontmost-window
mechanism that this design depends on. Extending to tmux panes, or to other
terminal emulators that expose a comparable mechanism, is a documented
future increment, not a silent gap.
