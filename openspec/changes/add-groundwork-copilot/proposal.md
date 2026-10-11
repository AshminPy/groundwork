## Why

A developer whose command just failed in one terminal has two options today: copy the output into a Claude Code session by hand, or re-run the command through a pipe. Neither uses what Groundwork already knows (which project, which branch) and neither is safe by default: pasted output can carry secrets and hostile instructions, and a Claude Code session that can run tools is more power than "explain this failure" needs. Phase 4 of the owner's programme asks for context-aware terminal assistance that starts read-only, keeps simultaneous sessions apart, avoids copying whole histories, and does not add another agent runtime.

## What Changes

- New `groundwork copilot explain`: reads a bounded slice of the recent output of **the terminal it is typed in** (a tmux pane, proven by `$TMUX_PANE`, the process's own controlling tty and the pane's process being an ancestor), adds project facts from git, removes invisible characters, redacts secret-shaped text before cutting to the window, and asks Claude once through `claude -p --safe-mode --tools ""` with the prompt on stdin in an empty scratch directory. `--tools ""` alone was found to leave plugin MCP tools in the model's tool list and to let a project's hooks and MCP servers run; `--safe-mode` empties the tool and MCP lists and runs neither (verified, Claude Code 2.1.296). It prints the answer, states that no command was run, and warns that a suggested command comes from untrusted output.
- `--stdin` serves any terminal that is not tmux (`some_cmd 2>&1 | groundwork copilot explain --stdin`); `--dry-run` prints the exact prompt and sends nothing; `--question` asks something specific; `--lines` bounds the slice.
- Pass-through `groundwork copilot …` in the CLI; installer copies the module; nothing else is installed or started.

Not in this change: executing any command (explicitly deferred until the mechanism and its safety boundary have been validated), iTerm2/Terminal.app readers (no macOS here), voice (Phase 5 will call this command), file access by the model, any stored state.

## Capabilities

### New Capabilities
- `groundwork-copilot`: read-only, session-bound explanation of what happened in a terminal.

## Impact

`scripts/groundwork_copilot.py` (new), `scripts/groundwork_cli.py` (one pass-through), `install.sh` (one copy), README / ARCHITECTURE / CHANGELOG, tests. No new dependency, no daemon, no persisted file, no new credential: it uses the `claude` the user already has. Data flow added: bounded, redacted terminal text and git facts → the user's own Claude Code session (on stdin, not argv) → Anthropic API, only when the user runs the command.
