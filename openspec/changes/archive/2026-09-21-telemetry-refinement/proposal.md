## Why

Three refinements to 1.3.x telemetry before the weekly report: profile was `unknown` on this machine; outcome was `unknown` for clearly completed tasks; responses carried a Status line, body validation, a STATUS completion block and the metadata block — redundant.

## What Changes

- Profile recorded from `GROUNDWORK_PROFILE` (user settings env; machine-specific, not shipped) — observed, never model-declared.
- Outcome classifier reads the response's status language (contract + playbook vocabularies, `Overall:`, bold verdict openers, result headings of non-status playbooks); precedence failed > blocked > partial > complete; `unknown` when nothing recognisable.
- Record schema 2: `observed` vs `declared`.
- engineering-workflow §3 "Completion facts": reported once inside Validation / Technical details; aligned STATUS block only on request. Metadata block reduced to four lines.

## Non-goals

Routing, playbooks, evidence rules, security controls, other hooks, Git protections, fail-open and privacy behaviour — unchanged.
