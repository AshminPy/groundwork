## Context

1.3.0/1.3.1 telemetry worked but three things were off on this machine: profile `unknown`, outcome `unknown` for clearly finished tasks, and responses carrying a Status line, body validation, a STATUS completion block and the metadata block.

## Decisions

**D1 — Profile is observed, from `GROUNDWORK_PROFILE`, never from the model's block.** EVIDENCE: the snapshot hook already reads that variable; a fresh `claude -p` session's snapshot showed `profile: work` after adding it to the user's `settings.json` `env`. WHY: a machine fact should not depend on what the model writes. TRADEOFFS: unset → `unknown`. VALIDATION: test + fresh session.

**D2 (revised) — Trigger = block present OR tool use in the turn.** EVIDENCE: four fresh `claude -p` sessions on small tasks completed correctly but omitted the block despite two rule clarifications; observed facts were lost. WHY: observed facts must not depend on model compliance; `declared.block_present` makes compliance itself measurable. TRADEOFFS: turns that used a tool in a non-Groundwork context also produce a record with declared fields `unknown`. VALIDATION: tests (no block + tools → record; no block + no tools → nothing) and fresh sessions.

**D3 — Outcome from status language only.** Sources in order: `Overall:`; the Status / Result paragraph (whole paragraph classified — a failure stated after a leading "Complete." wins: failed > blocked > partial > complete, negations count as partial); a bold or plain state-word opener; an explicit "Next action: none" (the model declaring nothing remains); the result heading of a non-status playbook (Answer / Recommendation / Deliverable / Plan — `blocked` when the reply ends with a question). Nothing recognisable → `unknown`; a response's mere existence never yields `complete`. EVIDENCE: 30 classifier cases incl. the contract's own examples and the reviewer's counter-examples. TRADEOFFS: regex heuristics, documented as declared (not verified) data.

**D4 — Record schema 2: `observed` vs `declared`.** WHY: reports must never present model claims as measured facts. Older lines (no `schema` key) are schema 1, flat.

**D5 — One status per response.** engineering-workflow §3 becomes "Completion facts": established with evidence, reported once inside Validation / Technical details; the aligned STATUS block only on request. The private behaviour rules (`~/.claude/rules/behavior.md`, `troubleshooting.md`, mirrored to claude-toolkit) now defer to the Groundwork contract for any tool-using task, and `~/.claude/CLAUDE.md` gained one line asking for the block. Playbooks untouched.

## Risks

- Block emission by the model in short non-interactive tasks remained inconsistent through this change; D2 makes the data robust to it and measurable.
