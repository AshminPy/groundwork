# Architect coach mode

## Why

The owner often needs advice from a senior principal cloud architect, and waits days or weeks for one. They want
Groundwork to coach them on AWS and Google Cloud design: brainstorm, advise, and teach them to reason like a
senior architect, while keeping Groundwork's evidence rules. The router allows exactly one category per task and
forbids inventing new ones, so coaching cannot be an eleventh category.

## What Changes

- New `modes/coach.md`, installed to `~/.claude/groundwork/modes/coach.md` and removed by `uninstall.sh`.
  It defines a persona, four conversation moves (brainstorm, advise, teach, review), how a principal architect
  thinks (requirements, simplest design, Well-Architected pillars, failure modes, identity and data flow, cost and
  operations, decision record), evidence order, and guardrails.
- `rules/task-routing.md` §1 gains item 7: when the user asks to be coached or to brainstorm, also read the coach
  mode on top of the selected category. It is not a new category and relaxes no rule.
- Tests check the router line, the file's sections and size, install and uninstall.
- README and CHANGELOG describe it.

## Non-Goals

- No new category, playbook, hook, agent or skill.
- No change to evidence, review, authorization or completion rules.
- No voice interface here; the macOS voice coach is a separate tool (`tools/architect-coach/`).
- No impersonation of a real person.

## Compatibility with planned Groundwork 3

Checked 2026-11-07: `main` is at `9f551a0`, the base of this change. The Groundwork 3 plan
(`claude/groundwork-3-redesign`, `openspec/changes/groundwork-3-control-plane/`, not approved or merged) replaces
`install.sh` and the ten-category router with a plugin and tier routing. If it lands, `modes/coach.md` moves into
the plugin as an on-demand skill with the same content; nothing in this change blocks that. No other open branch
edits the router; `claude/accuracy-signals` touches different lines of `uninstall.sh` and `tests/test_playbooks.py`.
