## 1. Implementation
- [x] 1.1 `scripts/groundwork_copilot.py`: terminal resolution (tmux pane + controlling-tty proof), bounded capture, ANSI strip, invocation-line cut, secret redaction, project facts, fenced prompt, tool-less model call, `--stdin`, `--dry-run`, `--json`
- [x] 1.2 `scripts/groundwork_cli.py`: `groundwork copilot` pass-through; `install.sh` copies the module
- [x] 1.3 README, ARCHITECTURE, CHANGELOG

## 2. Verification
- [x] 2.1 Unit tests (text handling, prompt/call flags, refusals, stdin path, project facts)
- [x] 2.2 Real tmux test: two panes/projects/failures, isolation both ways, hostile instruction not executed, secret redacted, spoofed pane id refused, dry-run sends nothing
- [x] 2.3 Mutation checks of ten safety clauses (all caught)
- [x] 2.4 Real model call on a genuine traceback in a real pane (answer grounded in the pane; cause the output could not show reported UNKNOWN)
- [x] 2.5 CLI dispatch test
- [x] 2.6 Full suite and `openspec validate --all --strict` against the main baseline
- [ ] 2.7 Independent fresh-context review; fix MUST FIX; confirmation review
- [ ] 2.8 Owner trial on macOS terminals (RUNTIME VALIDATION REQUIRED); iTerm2 / Terminal.app readers not built

## 3. Deferred by design
- [ ] 3.1 Authorized command execution (needs a validated approval flow and session proof first)
- [ ] 3.2 Optional, path-scoped read access for the model (needs its own prompt-injection review)
