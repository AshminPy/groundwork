# Output contract (Groundwork — inherited by every playbook; applies to every substantive response)

Progressive disclosure: the reader must understand the result from the main response alone; engineers find traceability below it. The investigation may be deep — the write-up is not. This changes presentation only; routing, tiers, OpenSpec use, hooks, evidence rules and completion criteria are untouched.

## Layer 1 — Main response (always)
Lead with the result. Write for the person reading, not the system that did the work: translate evidence into meaning ("verified that all existing critical files remained unchanged", not "SHA-256 baseline 9/9 unchanged"; "all 12 routing tests selected the expected task type", not "12/12 headless scenarios passed"; "a test-command issue was found and fixed; all tests now pass", not "pipe masked exit 1").
Default shape — the selected playbook's Output Format names the exact headings for its category:
- **Status** — one sentence stating the result, opening with its state — `Complete.` / `Partial.` / `Blocked.` / `Failed.` or the playbook's own status word (fixed, root cause found, deployed, pass, fail, not verified) — then the result ("Complete. The change is implemented and validated." / "Root cause found. The service account is missing the required IAM role." / "Validation failed. The deployment completed, but the health check still fails.").
- **What matters** — a few concise bullets: only findings that affect understanding or a decision, in understandable language; implementation internals only when they change the decision.
- **What changed / Fix / Recommendation** — whichever heading fits the task; material actions only.
- **Validation** — whether the result was actually verified and what was not ("Configuration validated and automated tests pass. Live production behaviour was not tested."). Never imply verification that did not happen. For IMPLEMENT and DEPLOY this states the completion facts (engineering-workflow.md §3) in plain words; their evidence goes in Technical details as compact bullets. Never append a separate STATUS block — one status per response — unless the user asks for a release/deployment completion checklist.
- **Next action** — one best action, only when something still needs to happen.
The main response is written in user language and answers only: what happened, did it work, what matters to the user, is anything still risky, broken or unverified, and what should happen next. By default it contains no implementation mechanics — no file names or paths, rule or test filenames, commit hashes, PR numbers, checksums, internal harness architecture, implementation history, reviewer or tool names, backup paths, internal wording changes ("this heading was restored"), or low-level validation mechanics. Say "all task types now share one output format" rather than naming the rule file; "verified that existing behaviour was not changed" rather than citing a checksum; "one issue found in review was fixed before completion" rather than describing the edit. Every one of those specifics still appears, exact and complete, in Technical details or Evidence & references — this separates evidence, it never removes it.
Rules: short sections, concise bullets, short paragraphs, direct conclusions. No introductions, no restating the request, no repeated conclusions, no narration of commands run, files inspected or hypotheses considered, no generic best-practice commentary, no implementation history. Omit any section that has nothing useful — never print empty headings such as "Risks: none". A complex investigation does not justify a long response; expand only when the user asks for details, a deep dive, a full review or full steps.

## Layer 2 — Technical details (when useful technical evidence exists)
Heading `Technical details`, then compact `Key: value` bullets, only the fields that apply, in this order: Error · Root cause · Evidence · Log path · Fix · Command · Files changed · Tests · Validation · Resource / environment · PR · Commit · Version · Remaining technical risk. The exact error and the few log lines that prove a finding go here while the human explanation stays in Layer 1; give the log path or retrieval command rather than dumping logs. Commands the reader may copy (reproduce, apply, verify, roll back, investigate) go in fenced code blocks, never inside paragraphs — and never every command that was executed internally. Files: list those that matter for understanding or review; when many changed, give the count plus key files. Traceability (PR, commit, deployment/resource, environment, version) lives here, not in Layer 1.

## Layer 3 — Evidence & references (when the conclusion depends on sources)
Heading `Evidence & references`: the strongest references that let the reader verify why the conclusion holds, in this order — runtime/live-system evidence · tests/validation results · repository code or configuration (path and line range) · official product documentation (the direct relevant page, never a homepage) · standards/specifications · PRs, issues, tickets, commits · trusted secondary sources only when no authoritative primary exists. Every reference must materially support a conclusion, recommendation or validation result; omit the section when none does; do not repeat a Technical-details line unless the reference adds traceability; show evidence and concise rationale only, never hidden reasoning.

## Checklist style (all three layers, every category)
Plain Markdown headings and light checklist bullets; no emojis or decorative symbols. Markers, used only where they improve scanability — never on every sentence:
- `[x]` completed or verified — only when the item was actually verified or completed.
- `[ ]` pending, not completed, or not yet verified — never to imply failure; a failure is stated in words (and under Risk when material).
- `[!]` an important risk or issue.
- `[-]` not applicable or intentionally skipped, only when saying so helps.
Typical shape: `Status` (one sentence) · `What matters` (checklist of the few facts that decide the result, with their real states) · `What changed` / `Fix` / `Recommendation` (as the playbook names it) · `Risk` (`[!]` items, only when material) · `Next` (`[ ]` one action, only when needed) · then `Technical details` and `Evidence & references` when they add something. Uncertainty is stated in words where it applies. Omit empty sections; do not repeat the same information across sections.

## Harness metadata (substantive Groundwork tasks only)
End every response that used a playbook with a small `Harness metadata` block. Any task in which you ran a command, a test, an edit or an agent is substantive and gets the block — however small; omit it only for conversational answers with no tool use. Fenced code block, aligned lines, same shape as STATUS — never as bullets; keep it to these four lines by default:
```
HARNESS METADATA
Groundwork <version> · <PLAYBOOK>
Execution:   single agent | <N> subagents | agent team
Evidence:    <source types: repo / tests / runtime / docs>
Validation:  verified | partial | not verified
```
Add `Profile:`, `Environment:`, `Agents:` (roles) or `Tools:` (MCPs) only when materially relevant, and never repeat information shown elsewhere in the response. Only known values — never invented, "unknown" when unsure; no reasoning. This block is what the telemetry hook records as *declared* metadata (with the Status sentence for the outcome); tools, files, tests, agent calls, version and profile it *observes* itself — so state the declared fields accurately.

## Always
- Priority order never changes: accuracy · security · evidence · correct execution · validation · easy to understand · concise · traceability. Clean output never hides a security risk, a failed test, a failed validation, a blocker, important uncertainty, a destructive consequence, or material evidence.
- Formatting: consistent Markdown, one heading level for sections, minimal bolding, no decorative noise; code formatting for commands, paths, error codes, resource names, commit hashes and configuration keys.
- Uncertainty is stated where it applies; the VERIFIED / INFERENCE / ASSUMPTION / UNVERIFIED labels of `evidence-policy.md` still apply.
- Do not print routing or playbook debug lines ("Routing: …", "Playbook: …") unless the user asks or Groundwork itself is being tested.
