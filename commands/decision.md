---
description: Create a task's decision record, or append an owner-approved entry to it (Groundwork)
argument-hint: <KEY> [decision|rejected|rule|state|waiting|close] [text]
---

Groundwork decision record request: $ARGUMENTS

The record CLI is `python3 ~/.claude/hooks/groundwork_decisions.py` (also `groundwork decision`). Follow these steps
exactly:

1. Find the task key in the request (for example `COR-12850`). With no key, ask the owner for it and stop.
2. If `python3 ~/.claude/hooks/groundwork_decisions.py path <KEY>` reports no record, create one:
   `python3 ~/.claude/hooks/groundwork_decisions.py create <KEY> --title "<short title>"` (add `--jira <url>` and
   `--task-note <path>` when known). Creating the empty record needs no approval.
3. For a decision, rejected option or standing rule:
   - Draft the entry as one line: what was decided or rejected, why, and its evidence (a link or `file:line`).
     For a rejected option, say what would have to change to reconsider it.
   - Show the owner the exact line and the kind (decision, rejected or rule), and stop for their approval.
   - Only after the owner approves, write it:
     `python3 ~/.claude/hooks/groundwork_decisions.py add <KEY> <decision|rejected|rule> "<approved text>"`.
     Claude Code will also ask the owner to approve this write. To replace an earlier entry, add a new one with
     `--supersedes <id>`; never edit or delete an existing entry.
4. For `state`, `waiting` or `close`, run the matching subcommand
   (`state <KEY> "<one line>"`, `waiting <KEY> "<who> — <what is needed>"` or `waiting <KEY> --clear`,
   `close <KEY>`). These are bookkeeping and need no approval.
5. Report the record path and what changed in one or two lines.
