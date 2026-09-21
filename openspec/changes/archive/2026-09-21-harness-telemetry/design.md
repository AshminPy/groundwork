## Context

Groundwork has three hooks and no logging. Claude Code's Stop hook receives `last_assistant_message`, `transcript_path`, `session_id`, `prompt_id`, `cwd` (docs/en/hooks §Stop); human turns in the transcript are `user` entries without `tool_result` blocks (verified on a real transcript). ECC keeps its own `skill-runs.jsonl` and cost tracker; those are ECC's, not Groundwork's.

## Goals / Non-Goals

**Goals:** honest visible metadata; one deterministic record per task; fields that support the listed future reports; zero effect on task execution; no sensitive content.
**Non-Goals:** dashboards, a report script, token/cost capture (not available to hooks), changing any existing hook or rule semantics.

## Decisions

**D1 — A fourth Stop hook, not rule-driven logging.** EVIDENCE: a rule asking the model to run a logging command each task would be model-dependent and add a Bash call per task; the Stop hook sees the finished response and the transcript deterministically. WHY: same pattern as the review gate; nothing to forget. TRADEOFFS: fields the transcript cannot show (execution mode as intended, evidence types, validation) come from the model's own block — recorded as stated, not verified. VALIDATION: unit tests on constructed transcripts. UNCERTAINTY: the block may be omitted or misfilled by the model; a missing block simply yields no record.

**D2 — Trigger on the visible block.** WHY: one mechanism decides both "was this a substantive task" and "what did the model claim"; trivial replies produce nothing.

**D3 — Current turn only.** WHY: per-task counts, not per-session; turn boundary = last human prompt. TRADEOFFS: a task that spans several human turns produces several records (one per response with a block) — acceptable for frequency reporting; `session_id` allows grouping.

**D4 — Privacy by construction.** Only tool names, MCP server names, counts, labels and a 12-char cwd hash. Command text is pattern-matched for test/deploy shape and discarded. Free text from the model's block is kept only when it is a short label (≤32 chars, letters/digits/space/`_`/`-`, no slash, no long digit-bearing word); playbook must be one of the ten categories; otherwise the field is `unknown`/dropped (review finding, fixed). Records are owner-only (0600/0700).

**D5 — Records survive uninstall; version from CHANGELOG at install time.** WHY: usage data is the user's; `VERSION` avoids a second source of truth.

## Risks / Trade-offs

- Heuristics (test/deploy command patterns, clarification = trailing question) are approximate and documented as such.
- One more process per Stop: the transcript is read backwards from the end and parsing stops at the last human prompt, so cost follows the current turn, not the session (0.17 s on a 16 MB real transcript; capped at 32 MB read). A turn longer than the cap contributes only its tail.
