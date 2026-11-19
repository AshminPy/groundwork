# Decision records

A decision record keeps what was decided on a task, what was rejected, what the task is waiting on and what the
owner said. It lives outside the session, so a long wait, a compaction or a new session cannot lose it. Hooks enforce
it; nothing depends on Claude remembering.

Code: `hooks/groundwork_decisions.py` (hook and CLI). Tests: `tests/test_decision_records.py`.

## The record

One Markdown file per task key: `<KEY> - <short title> - decisions.md`.

| Setting (`decision_records` in `~/.claude/groundwork/config.json`) | Default |
|---|---|
| `work_dir` | `~/SectigoSRE/CloudOps-Knowledge/Decisions` |
| `personal_dir` | `~/Documents/Obsidian/Personal/Decisions` |
| `work_roots` | `["~/SectigoSRE"]`: a session whose folder is under one of these uses `work_dir`, otherwise `personal_dir` |

`GROUNDWORK_DECISIONS_DIR` replaces both folders with one. `GROUNDWORK_DECISIONS=off` turns every part off.

Frontmatter: `task_id`, `title`, `status` (open, waiting, closed), `waiting_on`, `waiting_since`, `jira`, `repos`,
`task_note`, `last_updated` (UTC, set whenever Claude updates the record).

Sections:

| Section | Written by | Rule |
|---|---|---|
| Current state | `state` | replaced each time |
| Decisions | `add … decision` | `D-n`, append-only; replace one with `--supersedes D-n` |
| Rejected (do not re-propose) | `add … rejected` | `R-n`, append-only |
| Waiting on | `waiting` | replaced; `--clear` empties it |
| Standing rules | `add … rule` | `S-n`, append-only |
| Owner messages (raw, auto-captured, unreviewed) | the hook | the owner's prompts as quotes, secret-shaped text redacted |

## The task key

A key in the branch name wins when it is written in capitals (`feat/COR-12850-fix`). A lower-case one
(`feat/cor-12850-fix`) counts only when the key already has a record or a task in the repository's ledger, so
branches such as `bump-node-18` or `feat/k8s-1` are not tickets. Otherwise the latest key a prompt in this session
named as work (`COR-12850: …`, or an engineering request that names it). A question that only mentions a key does
not count. When a prompt made the key active, only owner messages from that point on are captured for it.

## What the hooks enforce

| # | When | What happens |
|---|---|---|
| 1 | Stop | A turn on a task key with no record is blocked once, with the `create` command. |
| 2 | SessionStart (startup, resume, clear, compact), and the first prompt naming a key | The record loads as context: Rejected first, then Standing rules, Waiting on, Current state, latest decisions. |
| 3 | PreCompact (all owner prompts in the transcript) and Stop (the latest) | Owner messages are copied into the record once each. PreCompact creates the record if it is missing. |
| 4 | PreToolUse | `groundwork decision add`, and any Claude Edit/Write of a record, ask the owner through Claude Code's permission prompt. An edit that changes or removes an existing `D-`, `R-` or `S-` entry is denied. |
| 5 | PreToolUse | `git push`, `gh pr create/edit/merge/comment/review/close/ready`, `gh issue create/comment/edit/close`, Jira CLIs and Jira MCP tools that change something, email and chat send tools, and browser clicks or typing after the session last navigated to an Atlassian host are denied when the record is missing or was last updated before the owner's latest message. The denial lists Rejected, Waiting on and Standing rules. |
| 6 | Stop | A reply that says it is waiting on someone other than the owner (or a record with status waiting) needs a filled Waiting on; blocked once. |
| 7 | `/decision` | Create a record, or draft an entry, get the owner's approval, then append it with a timestamp. |
| 8 | PostToolUse | A Jira action whose input mentions "Good for review" sets status closed. Closed records do not gate. |
| 9 | Brief and task note | The branch brief's snapshot lists `decision record: <path>`. `create --task-note PATH` links the record and the note both ways. |

Text written through the CLI (`add`, `state`, `waiting`, titles) is redacted the same way as owner messages; when
the redactor cannot be loaded the CLI refuses to write.

The hook's own writes (captured messages, closing, stamping `last_updated` after an approved edit) need no approval.
`create`, `state` and `waiting` are bookkeeping and do not ask. Only an update by Claude after the owner's latest
message unlocks step 5; the hook's capture does not.

## CLI

```bash
groundwork decision create COR-12850 --title "Replication setup" [--jira URL] [--task-note PATH] [--work|--personal]
```

```bash
groundwork decision add COR-12850 rejected "Debezium: no Oracle licence (https://…)"
```

```bash
groundwork decision state COR-12850 "Schema sent to the DBA team; plan unchanged"
```

```bash
groundwork decision waiting COR-12850 "DBA team — schema approval"
```

Also `waiting KEY --clear`, `close KEY`, `show KEY`, `path KEY`, `list`.

## Limits

- Not a sandbox: a program such as Python writing the file is not inspected, as with the task gate.
- "Waiting on someone" is detected from phrases in the final reply; it is a heuristic pinned by tests.
- Browser-driven Jira is recognised by the session's last navigation; a Jira page opened another way is not.
- Closing on "Good for review" needs that text in the tool input: a transition by name, or a browser action whose
  `action_summary` says it. A transition by id, or a click with no summary, leaves the record open; run
  `groundwork decision close KEY`.
- Jira, Slack or mail reached through `curl` or another HTTP client is not recognised as an outward action.
- The per-tool checks run inside the task gate, so `GROUNDWORK_TASK_GATE=off` also turns them off.
- Owner messages are redacted with the copilot redactor; a secret with no recognisable shape can survive.
