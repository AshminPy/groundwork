# DOCUMENT playbook

## Goal
Produce a document that its intended audience can use, grounded in the actual code, configuration, runtime or findings — never in what the system was meant to do.

## Workflow
1. Identify the audience and the format they asked for (README, runbook, report, executive summary, incident write-up, implementation doc); the audience decides depth and language.
2. Gather the source of truth before writing: the repository, configuration, tests, CI, runtime evidence, or the findings being reported. A document that describes features that do not exist in the code is wrong.
3. Reuse an existing template or convention in the repository if there is one; otherwise use the simplest structure the format implies.
4. Write for the audience: answer first, simple English, one idea per sentence, commands and paths exact and runnable, no filler.
5. Mark anything not verified as such inside the document rather than smoothing it over; distinguish implemented from planned.
6. Check every link, path and command you wrote.

## Evidence
- Each factual statement traces to something inspected; the "Source" line in the output says what that was.

## Ask Before Acting When
- The audience or format is unknown and the two plausible choices produce different documents (an executive summary vs an engineer's runbook). Otherwise pick from context and state the choice.

## Completion Criteria
- The document exists at the agreed location, matches the audience and format, contains no unverified claim presented as fact, and its links/commands work.

## Output Format
Main response headings: **Deliverable** (path or artifact) · **Important gaps or assumptions** (only when relevant). The document itself follows the requested audience and format — do not force status fields into it.
Then, per `output-contract.md`: `Technical details` and `Evidence & references` when they add something.
