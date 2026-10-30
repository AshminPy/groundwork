## Why

PR #62 delivered a Phase 1 orchestrator: one linear LangGraph workflow, four categories, deterministic checks, and a subscription-only `claude -p` adapter. The owner's updated requirements (2026-10-25) ask for more:
- a Meta-Harness with a parent graph and six specialised subgraphs;
- shared context with provenance;
- an automatic session manager;
- an evidence and decision engine.

This change is **discovery and design only**. It records the gap analysis, the target architecture and the smallest safe build order, for owner review before any code changes.

## What Changes

- No code changes. `design.md` holds all eight discovery deliverables.
- Revision 2 (same day) adds the SRE Agent reuse findings, the Evidence Engine with per-claim statuses, the session-manager comparison with context-aware handoff, and a mandatory benchmark.
- After approval, implementation follows `design.md` §7 as separate changes. The first milestone is M1: a benchmark harness and a plain-Claude-Code vs PR #62 baseline, with no change to PR #62 code.

## Capabilities

### New Capabilities
- `meta-harness`: parent/subgraph routing, shared context, session lifecycle, and evidence/decision records. Specs are written per build step, once the design is approved.

### Modified Capabilities
- `orchestrator` (PR #62): extended, not replaced. Its approvals, worktrees, checkpoints, operation IDs and bounded repairs stay.

## Impact

- Code: none in this change.
- Owner decisions (see `design.md`, Owner decisions): approve M1; allow M1b (stop host-run checks on worker-modified code in PR #62). Personal Max profile only; VERIFIED reserved for objective checks.
