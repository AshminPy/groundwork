## Context

Owner requirements for this milestone: identify the active project and authorized terminal context; observe selected terminal output; explain failures and suggest the next action; reuse evidence already collected; support simultaneous sessions without mixing context; avoid copying full histories into model context; preserve permissions; never execute in a different session; begin read-only; no new agent runtime.

Facts established on this host (VERIFIED, Claude Code 2.1.296, tmux 3.4):
- `claude --tools ""` disables all tools (`claude --help`).
- Inside a tmux pane `$TMUX_PANE` names the pane, `tty` is the pane's tty, `tmux capture-pane -p -J -t %N` returns its scrollback retroactively, and `tmux display-message -p -t %N '#{pane_tty}'` maps pane to tty.
- A process started in a pane has that pane's tty as its controlling terminal (`ps -o tty= -p $$`).

## Architecture-quality §2 answers

- **What is likely to change?** Which terminals can be read (tmux now; iTerm2 / Terminal.app / others later) and the redaction patterns. Terminal readers sit behind one function, `resolve_terminal()`, plus one capture function; a new reader is a new branch there, not a new layer. **Configuration rather than code?** Nothing is configurable beyond flags (`--lines`, `--question`): a setting that widened what is read or re-enabled tools would be a security downgrade. **Stable interface?** The command line.
- **Another provider / environment / tenant?** A macOS reader is the foreseeable one; deliberately not built because it cannot be validated here (RUNTIME VALIDATION REQUIRED). Phase 5 (voice) reuses the command by calling it with `--question`.
- **Manual steps automated?** Copy-paste of output, of project facts, and of redaction.
- **Dependency unavailable?** No tmux → a readable refusal pointing at `--stdin`; no `claude`, a non-zero exit, or a 120 s timeout → a readable error and exit 1; `ps`/`git` failures degrade to fewer facts or a refusal, never a traceback.
- **Observability?** `--dry-run` prints the exact prompt; every answer ends with the source, line count, character count and number of redactions, and "No command was run".
- **Test / deploy / rollback?** Unit tests; a real two-pane tmux test with a spoofed-pane case; mutation checks of ten safety clauses; one real model call on a genuine traceback. Deploy = the existing script copy in `install.sh`; rollback = the existing `groundwork rollback` / uninstall (the file lives in `~/.claude/groundwork/bin/`).
- **Security boundary?** Per-process binding to one pane (no flag reads another); no tools in the model call; terminal text fenced as untrusted data; secret-shaped text redacted before it leaves the machine; egress only through the user's own `claude`. See the DECISION below for what was rejected.
- **Scaling / cost?** One call per invocation, capped by `--max-budget-usd 0.25`, input capped at 400 lines / 16,000 characters.

## Decisions

DECISION            Read-only: one tool-less `claude -p --tools ""` call over a bounded, redacted slice of the invoking pane's output; no execution of any kind.
EVIDENCE            `claude --help` (`--tools ""`, `--no-session-persistence`, `--max-budget-usd`); tmux behaviour observed on this host (see Context); real run: a KeyError traceback in a pane was explained from the pane alone and the cause the output could not show was reported UNKNOWN.
WHY                 Alternatives that lost: (a) a read-only tool set (Read/Grep) — better answers (it could have opened the data file) but terminal text is untrusted, so an injected instruction could steer file reads whose contents then leave the machine inside the next request; a path-scoped tool permission model would need its own validation first. (b) a shell wrapper that records every command's output — copies full histories, which the owner excluded, and needs per-shell setup. (c) AppleScript readers for macOS terminals — unvalidated here.
TRADEOFFS           The model cannot open files, so it often ends at "UNKNOWN, show me X" (observed). It works retroactively only in tmux; elsewhere the user pipes the output. The user must act on any suggestion themselves.
VALIDATION METHOD   Tests and mutation checks above; an independent security review of the prompt/redaction/binding; owner trial on macOS terminals (RUNTIME VALIDATION REQUIRED).
UNCERTAINTY         Redaction is best effort (a secret with no recognisable shape can survive; `--dry-run` shows what would be sent); behaviour in iTerm2 / Terminal.app / tmux control mode / `screen` is untested; answer quality depends on the model.

DECISION            Authorized command execution is NOT built here.
EVIDENCE            Owner's instruction: add it "only when the mechanism and safety boundaries have been validated".
WHY                 Execution needs a per-command approval flow, deny-list integration and a way to prove the target session, none of which is validated.
TRADEOFFS           The assistant can suggest but not do.
VALIDATION METHOD   Not applicable until proposed.
UNCERTAINTY         Whether the owner wants it at all.

## Risks

- Prompt injection through terminal output: contained by construction (no tools), so the residual risk is a wrong or misleading answer, which the prompt counters by requiring a quoted line and an explicit UNKNOWN.
- A stale or inherited `TMUX_PANE` (for example through `ssh` env forwarding): refused because the pane's tty must equal the process's own controlling tty.
