## Context

The open question: *where in the pipeline can "what did I actually just read" be collected deterministically, without hand-maintaining it or having the model re-derive it?* The requirement: a deterministic label, not an LLM confidence percentage, kept separate from validation state and references.

Evidence for the answer (VERIFIED in this repository and on this host):
- A Claude Code transcript records every `tool_use` (name, input) and its matching `tool_result` with a boolean `is_error`, keyed by `tool_use_id`. `hooks/groundwork_telemetry.py` already reads the current turn from it (`current_turn`, `turn_facts`).
- The `PostToolUse` / `PostToolUseFailure` hook events (PR #43) cannot be the source: they are not fired for calls denied or cancelled (https://code.claude.com/docs/en/hooks), and persisting tool inputs there would breach the telemetry privacy rule.

## Architecture-quality §2 answers

- **What is likely to change?** The recognised command patterns (what counts as a test, a runtime check, a repo read) and the label rule. They are constants and one function in one module, with the rule written in its docstring and tested. **Configuration rather than code?** No: a user-editable rule would let the estimate be tuned upward, which defeats it. **Stable interface?** `derive_evidence(entries) -> {confidence, signals, references, references_omitted, reasons}` and `telemetry_summary(entries)`.
- **Another instance / provider / tenant?** Not applicable: it reads one local transcript. Another tool's evidence (a new MCP server) is a new entry in the recognition rules, not a new code path.
- **Manual steps to automate?** The model no longer reconstructs its references from memory; the CLI prints them. Declared-vs-observed comparison is automatic in the Stop hook.
- **Dependency unavailable?** The telemetry hook imports the module fail-open: if it is missing or raises, the record is written without evidence fields. The CLI reports `UNKNOWN` (never a label) when the transcript cannot be read.
- **Observability?** `groundwork evidence [--json] [--transcript PATH]`; telemetry fields; `reasons` explain why an estimate is what it is.
- **Test / deploy / rollback?** Unit tests on synthetic transcripts, mutation checks on the rule's clauses, a real run on a live 83 MB transcript, CLI dispatch and uninstall tests. Deploy = the existing `hooks/*.py` copy; rollback = `groundwork rollback` / uninstall (the module is a file under `~/.claude/hooks/`).
- **Security boundary?** Local read of the user's own transcript only. References are printed to the invoking user, redacted (secret-shaped substrings, URL query strings) and never persisted by Groundwork. The Stop hook persists only the label and counts/booleans.
- **Scaling / cost?** One backward tail read of the current turn (already done by the hook); measured 0.15 s on an 83 MB transcript. Cost is negligible.

## Decisions

DECISION            Derive the receipt and estimate from the transcript, on demand and inside the existing Stop hook; persist only label + counts.
EVIDENCE            Transcript records tool_use/tool_result with is_error (observed on this session's transcript, `/root/.claude/projects/…/*.jsonl`); telemetry privacy requirement in `openspec/specs/usage-telemetry/spec.md`; PostToolUse semantics from https://code.claude.com/docs/en/hooks.
WHY                 Alternatives that lost: (a) PostToolUse hooks — miss denied/cancelled calls and would have to store inputs; (b) asking the model to list its sources — the thing this replaces; (c) storing references in telemetry — breaks "no paths, commands, URLs" and adds a second copy of data the transcript already holds.
TRADEOFFS           The estimate leans cautious but is not a guaranteed bound. Cautious: a check counts only if nothing that could change the tree came after it; a Bash command that is not on a short read-only list counts as a possible change; a test piped through anything but a pass-through filter is not credited; background-agent reviews are not credited (their report arrives as a later message, not a tool_result). Real workflows will therefore often show a lower label than a human would give. Not bounded: environment effects (PATH, aliases, sourced files), wrapper commands, remote state changes and a forged REVIEW RESULT block can still make it too high.
VALIDATION METHOD   Unit + mutation tests; real transcript run; declared-vs-observed comparison in a Stop-hook subprocess test; owner review of labels against sessions they know (RUNTIME VALIDATION REQUIRED — only the owner can judge whether the labels feel right).
UNCERTAINTY         Whether the recognition lists match the owner's real commands (UNVERIFIED beyond this repo's own); whether crediting hand-back messages is worth the fragility (deferred); a forged `REVIEW RESULT` block inside a subagent's own text would be credited (same residual as the review gate).

DECISION            The model's stated `Confidence:` is recorded and compared, not enforced (no Stop-hook block).
EVIDENCE            `require_material_review.py` shows the blocking pattern exists; the owner asked for confidence to be deterministic and for UNKNOWN never to be upgraded, not for a new gate.
WHY                 A block-and-retry loop on a label is heavy for a first version and would be gamed by lowering the label; recording the over-claim makes it auditable and visible via the CLI.
TRADEOFFS           An over-claiming response is not stopped; it is flagged afterwards.
VALIDATION METHOD   Stop-hook subprocess test asserts `declared_confidence_exceeds_observed`.
UNCERTAINTY         Whether the owner wants enforcement later.

## Risks

- Heuristic recognition aims to under-credit, and a differential test against a real bash checks it on ~1,000 compositions, but it cannot be proven free of over-credit: command parsing is quote-aware and rejects heredocs, substitutions, `${…}`, comments, subshells, `exit`/`trap`/`!`, background jobs and unbalanced quotes; `||` and `;` chains are not attributed; pipes are credited only through the runner's own summary or `set -o pipefail`; ordering is enforced (a later change or an unattributable test-shaped run withdraws an earlier pass). An independent security review and a correctness review of the first version found 16 must-fix issues of this kind (stale verification, comment/`${}`/`exit`/`!` constructs, background runs, review parsing, non-running test flags, false references, cross-project transcript, redaction gaps), all fixed; the class is not closed, which is why the label is documented as an estimate.
- Token cost of the rule text: two sentences in `evidence-policy.md`, none net in `output-contract.md`.
