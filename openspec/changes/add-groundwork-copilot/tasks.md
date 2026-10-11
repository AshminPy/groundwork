## 1. Implementation
- [x] 1.1 `scripts/groundwork_copilot.py`: terminal resolution (tmux pane + controlling-tty proof), bounded capture, ANSI strip, invocation-line cut, secret redaction, project facts, fenced prompt, contained model call (`--safe-mode --tools ""`, prompt on stdin, scratch cwd), `--stdin`, `--dry-run`, `--json`
- [x] 1.2 `scripts/groundwork_cli.py`: `groundwork copilot` pass-through; `install.sh` copies the module
- [x] 1.3 README, ARCHITECTURE, CHANGELOG

## 2. Verification
- [x] 2.1 Unit tests (text handling, prompt/call flags, refusals, stdin path, project facts)
- [x] 2.2 Real tmux test: two panes/projects/failures, isolation both ways, hostile instruction not executed, secret redacted, spoofed pane id refused, dry-run sends nothing
- [x] 2.3 Mutation checks of the safety clauses: 53 mutants of the safety clauses, all caught by the tests (`tests/mutation/mutate_copilot.py` mutates a copy of the tree); one further mutant, removing `core.fsmonitor=false`, is classed equivalent because the tool no longer runs `git status`, the only one of its git calls that reads the index, so the flag is defence in depth and the fsmonitor canary test passes without it
- [x] 2.4 Real model call on a genuine traceback in a real pane (answer grounded in the pane; cause the output could not show reported UNKNOWN)
- [x] 2.5 CLI dispatch test
- [x] 2.6 Full suite and `openspec validate --all --strict` against the main baseline
- [x] 2.7a Independent security + correctness reviews (13 MUST FIX: tools not inert, redaction after cutting, redaction gaps, ReDoS, unredacted facts outside the fence, fsmonitor, prompt in argv, non-UTF-8 stdin, multi-line errors, unproven clauses); all fixed
- [x] 2.7b Confirmation reviews (security and correctness): 4 + 4 MUST FIX, overlapping: `git status` started a repository filter program, a tab in the pane's directory skipped the ancestor check, an unquoted password containing `;` or `,` and escaped JSON were not fully redacted, `--json` lacked the notice, spec clauses without a failing-if-removed test; all fixed
- [ ] 2.7c Fresh confirmation review of the 2.7b fixes
- [x] 2.9 Live containment check against the real claude (project hook + MCP server canary; tool and MCP lists empty with `--safe-mode`, 30 tools / 2 servers without)
- [ ] 2.8 Owner trial on macOS terminals (RUNTIME VALIDATION REQUIRED); iTerm2 / Terminal.app readers not built

## 3. Deferred by design
- [ ] 3.1 Authorized command execution (needs a validated approval flow and session proof first)
- [ ] 3.2 Optional, path-scoped read access for the model (needs its own prompt-injection review)
