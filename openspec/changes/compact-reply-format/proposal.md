# Compact reply format

## Why

Replies after tool use are hard to scan in the Claude desktop app (owner report, 2026-10-31, with a screenshot):

- The same facts appear up to three times: in the main response, again in `Technical details`, and again in the
  app's own recap/next-step box under the message.
- The four-line fenced `HARNESS METADATA` block is the largest box on screen and gives the reader no decision.
  It exists for the telemetry hook, not for the reader.
- `rules/output-contract.md` says `Evidence & references` appears only "when the conclusion depends on sources",
  but `hooks/groundwork_reply_check.py` demands it after every tool turn, including read-only turns. Rule and hook
  disagree, and the hook wins, so every reply gets the section.

## What Changes

- **Metadata becomes one line.** New default form, last line of the reply:
  `` `Harness metadata · Groundwork <version> · <PLAYBOOK> · <execution> · evidence: <types> · validation: <state>` ``.
  `groundwork_telemetry.parse_metadata` reads it into the same fields as the block. The old four-line block is
  still accepted, so older sessions and saved transcripts keep working.
- **The reply check asks for `Evidence & references` only when the turn changed files** (Edit, Write,
  MultiEdit, NotebookEdit). The reply then points at what changed. Read-only and command-only turns follow the
  contract's existing "when the conclusion depends on sources" rule, which the hook no longer overrides.
  This deliberately reverses the earlier owner decision "links in every reply"; the owner approved the reversal
  on 2026-10-31.
- **No repeated facts.** The contract states that `Technical details` holds evidence only (commands, files, PR,
  commit), never a restated result, and that when the host app shows its own recap box the message does not
  repeat that recap.
- The prompt-time reminder text and the README describe the new form.

## Non-Goals

- No change to what is verified, which completion facts are reported, or the evidence policy.
- No change to telemetry's record schema: same fields, read from a shorter line.
- No removal of `Technical details` (still required when Bash ran) or of the plain-language result first.
