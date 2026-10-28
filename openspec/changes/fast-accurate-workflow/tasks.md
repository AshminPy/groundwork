## 1. Rules
- [x] 1.1 §2.3 plan fact-check sentence
- [x] 1.2 §2.6 MUST FIX bar in the reviewer's brief
- [x] 1.3 §4 push after each green step

## 2. Cloud session tooling
- [x] 2.1 `.claude/hooks/session-start.sh` (cloud-only, idempotent, pinned OpenSpec)
- [x] 2.2 Register it in `.claude/settings.json`

## 3. Verification
- [x] 3.1 Hook run: tools present, pytest missing, local session; full test suite; `openspec validate --strict`
- [ ] 3.2 Independent review with the MUST FIX bar stated in the brief
