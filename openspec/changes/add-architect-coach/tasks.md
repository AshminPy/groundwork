## 1. Implementation

- [x] 1.1 `modes/coach.md` with persona, moves, reasoning steps, evidence and guardrails
- [x] 1.2 Router item 7 (coaching modifier) in `rules/task-routing.md`
- [x] 1.3 `install.sh` copies `modes/`; `uninstall.sh` removes it
- [x] 1.4 README and CHANGELOG

## 2. Validation

- [x] 2.1 Tests for the router line, coach file, install and uninstall; full suite green
- [ ] 2.2 `openspec validate add-architect-coach --strict` (OpenSpec CLI not available in the build environment)
- [ ] 2.3 Live check: a fresh session given "teach me how to design the CloudAMQP connection setup; coach me" reads the coach mode and asks for the user's proposal first
- [ ] 2.4 Independent review with zero MUST FIX
