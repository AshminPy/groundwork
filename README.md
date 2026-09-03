# Groundwork

**A small, evidence-first governance layer on top of [ECC](https://github.com/affaan-m/ECC) and [OpenSpec](https://github.com/Fission-AI/OpenSpec) for Claude Code.**

Groundwork is not a fork or a redistribution of ECC or OpenSpec — it installs both from their own official sources and adds three small things on top: a workflow rule that routes work by risk tier, an evidence policy that stops completion claims from outrunning proof, and a deterministic Stop hook that makes independent review of material changes non-optional. That's the whole product: two rule files, two hooks, and an installer. No new agents, no new skills, no new plugin ecosystem.

Built and validated by **Ashmin** ([@AshminPy](https://github.com/AshminPy)) — see [CREDITS.md](CREDITS.md) for exactly what's original here versus what's installed from upstream.

## Why this exists

ECC ships 68 agents and 286 skills that are excellent once invoked — but nothing invokes them on its own. Left alone, a plain request to "add X" gets implemented without a plan, without tests, without review, and the final report says it's done regardless. OpenSpec gives you a real spec-driven change lifecycle, but only when you run `/opsx:*` — and even then, nothing stops an agent from claiming a change is complete with a failing test still in the suite.

Groundwork closes exactly those three gaps, and nothing else:

1. **Route by risk, not by ceremony.** A one-line fix shouldn't get a spec. A production-facing change should. `rules/engineering-workflow.md` defines three tiers and what each one requires.
2. **Evidence beats intuition, always.** Every material technical decision cites a real source; every completion claim shows the command and the result. `rules/evidence-policy.md` sets the rules and the labels (VERIFIED / UNVERIFIED / ASSUMPTION / INFERENCE / RUNTIME VALIDATION REQUIRED).
3. **Independent review is enforced, not requested.** `hooks/require_material_review.py` is a Stop hook that will not let a session end if a spec-driven change is fully implemented and nothing that looks like a reviewer ever ran against it — even if you were explicitly told to skip review. See [docs/VALIDATION.md](docs/VALIDATION.md) for the actual test that proves this.

## Architecture

```
                    USER GOAL
                        │
                        ▼
   rules/engineering-workflow.md  ──  classifies TRIVIAL / STANDARD / MATERIAL
                        │
        ┌───────────────┴───────────────┐
        ▼                                ▼
     OpenSpec                          ECC
  WHAT / WHY / acceptance        HOW: agents, skills,
  criteria as scenarios          GateGuard, session
  (per-repo, file-based)         persistence, learning
        │                                │
        └───────────────┬───────────────┘
                         ▼
         rules/evidence-policy.md — decisions cited,
              claims proven, labels honest
                         ▼
       hooks/require_material_review.py — Stop hook,
         blocks completion without independent review
                         ▼
              COMPLETION STATUS block
   Code / Tests / Merged / Deployed / Live validated
      → COMPLETE / PARTIAL / BLOCKED / PLANNED / FAILED
```

Full detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

Requirements: Claude Code ≥ 2.1, Node ≥ 18, npm, Python 3, git.

```bash
git clone https://github.com/AshminPy/groundwork.git
cd groundwork
./install.sh
```

This installs ECC (official plugin path), the OpenSpec CLI (official npm package), and Groundwork's two rule files and two hooks into `~/.claude/`, merging into your existing `settings.json` without touching anything else you've configured (see [scripts/merge_settings.py](scripts/merge_settings.py) for exactly what it changes).

Per project, once, if you want spec-driven work there:
```bash
cd your-project
openspec init --tools claude
```

That's it. Start a normal Claude Code session and give it an engineering task.

## What each tier actually requires

| Tier | Example | Process |
|---|---|---|
| TRIVIAL | typo, one-line config value | Just do it, run the narrowest check |
| STANDARD | bug fix, small feature | Inline plan → tests → self-review → verify → status |
| MATERIAL | architecture, security, production behavior, external interfaces | Investigate → OpenSpec spec → evidence-backed decisions → implement → tests → **independent review (enforced)** → verify → deploy/live-validate if in scope → status |

Full text: [rules/engineering-workflow.md](rules/engineering-workflow.md).

## The completion status block

Every STANDARD/MATERIAL task ends with:
```
STATUS
Code:           ✅ / ❌ / N/A
Tests:          ✅ / ❌ / N/A
Merged:         ✅ / ❌ / N/A
Deployed:       ✅ / ❌ / N/A
Live validated: ✅ / ❌ / N/A
Overall: COMPLETE / PARTIAL / BLOCKED / PLANNED / FAILED
```
Hard rules: merged ≠ complete, tested ≠ deployed, deployed ≠ live validated. A failing test — including one that was already failing before you started — makes `Tests: ❌` and `Overall: PARTIAL`, never COMPLETE. `N/A` is only legitimate when the step genuinely doesn't apply, stated why; it is never used to reach COMPLETE by omission.

## Does it actually work?

[docs/VALIDATION.md](docs/VALIDATION.md) is the real evidence: the actual test prompts, the actual transcripts, and what happened — including the times it didn't work on the first try and what was fixed. Groundwork does not ask you to trust marketing copy about itself.

## Repository layout

```
groundwork/
├── install.sh / uninstall.sh      installer, idempotent, reversible
├── rules/
│   ├── engineering-workflow.md    tiers, autonomy rule, completion block
│   └── evidence-policy.md         evidence priority, decision format, labels
├── hooks/
│   ├── block_protected_push.py    denies push to main/master/production + force-push
│   └── require_material_review.py denies finishing a complete-but-unreviewed change
├── scripts/
│   ├── merge_settings.py          settings.json merge (used by install.sh)
│   └── unmerge_settings.py        settings.json cleanup (used by uninstall.sh)
├── tests/
│   └── test_hooks.py              the actual test suite the hooks were built against
└── docs/
    ├── ARCHITECTURE.md
    ├── VALIDATION.md              real test transcripts and results
    ├── TROUBLESHOOTING.md
    └── UPGRADE-ROLLBACK.md
```

## License and attribution

Groundwork's own files (rules, hooks, scripts, docs) are MIT-licensed, © Ashmin — see [LICENSE](LICENSE). ECC and OpenSpec are separate, independently MIT-licensed projects installed from their own official sources, not modified or redistributed here. Full attribution: [CREDITS.md](CREDITS.md).
