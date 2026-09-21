## Why

The 1.2.0 router and playbooks made task shape consistent, but the answer shape still mixed plain results with raw evidence ("SHA-256 baseline 9/9 unchanged", "12/12 headless scenarios") and printed routing debug lines. Readers had to parse engineering traceability to find the result. A global, inherited output model fixes this once instead of ten times.

## What Changes

- **New always-loaded rule `rules/output-contract.md`** (25 lines): three layers — plain-language main response (result first, only material findings, validation stated honestly, one next action when needed), `Technical details` when useful evidence exists (errors, log paths, copyable commands, key files, tests, PR/commit/version, technical risk), `Evidence & references` when the conclusion depends on sources — plus the priority order, omit-empty-sections rule, language rule, and no routing debug lines unless asked.
- **`rules/task-routing.md` §4** becomes a pointer to the contract.
- **Each playbook's Output Format** shrinks to its category's main-response headings plus one inheritance line; the global rules are not duplicated.
- **Tests** pin the contract's presence, size and key rules, the router pointer, and that no playbook restates the layers.

Presentation only. Routing, tiers, OpenSpec, hooks, evidence rules and completion criteria are unchanged.

## Capabilities

### Modified Capabilities
- `task-routing`: the universal output contract requirement now specifies the three-layer progressive-disclosure model and its rules.

## Impact

One more ~25-line rule in every session; the router shrinks by ~3 lines. No settings, hook or installer logic changes (the installer already copies `rules/*.md`).
