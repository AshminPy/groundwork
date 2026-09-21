## Context

Groundwork's always-loaded instructions are the rule files installed to `~/.claude/rules/groundwork/` (Claude Code loads `~/.claude/rules/**/*.md` at launch, docs/en/memory). Groundwork owns no CLAUDE.md and the installer never edits the user's. The installer copies `rules/*.md` and `hooks/*.py`; tests are one custom-runner module also collected by pytest. The CLI is logged in on this machine, so live routing checks are possible.

## Goals / Non-Goals

**Goals:** consistent task shape and answer shape per category; narration suppressed; clarification only when material; low context cost; zero change to existing controls; installable by the existing mechanism.

**Non-Goals:** a Python classifier, a second routing mechanism, new agents/hooks/MCP servers, changing any existing rule, duplicating rules already stated globally.

## Decisions

**D1 — Routing is a fourth rule file, playbooks are plain Markdown outside `rules/`.**
EVIDENCE: rules dir is loaded recursively (docs/en/memory); anything under it costs every session. WHY: reuses the existing install path for the router; a separate `~/.claude/groundwork/playbooks/` directory guarantees on-demand loading with the Read tool and no new mechanism. TRADEOFFS: playbook loading is model-followed (advisory), not enforced. VALIDATION: structural tests + live scenario checker. UNCERTAINTY: adherence in long sessions.

**D2 — Not skills.** EVIDENCE: skills would add ten catalog entries to every session and require the Skill tool; the brief asks for "read only that playbook". WHY: plain files are the smaller mechanism. TRADEOFFS: no `/`-invocation; acceptable, routing is Claude's job.

**D3 — Existing rule wins; IMPLEMENT and DEPLOY outputs embed the completion block.** EVIDENCE: `engineering-workflow.md` §3 makes the completion block mandatory for STANDARD/MATERIAL work. WHY: the user's Status/Changed/Validation/Remaining shape is kept, with `Validation` carrying the block's rows and `Status` equal to its Overall. TRADEOFFS: none material.

**D4 — Tests are structural plus a live checker, not a keyword classifier.** EVIDENCE: routing is model judgment; a Python classifier would be a second, unused router. WHY: `tests/test_playbooks.py` proves the artefacts and install; `scripts/check_routing.py` runs the twelve scenarios through `claude -p` and reports category and question/no-question, skipping when logged out. TRADEOFFS: the live check costs a few cents and is model-behaviour evidence, labelled as such.

## Risks / Trade-offs

- Advisory behaviour: the router cannot be hook-enforced; the SRE pilot and the live checker are the evidence.
- The user's own `response-contract.md` still applies on top; the playbook formats were written to be compatible (answer first, one next action).
