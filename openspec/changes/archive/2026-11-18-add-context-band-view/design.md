## Context

The context % already exists in `usage.jsonl` (written by `scripts/groundwork_statusline.py`, about once a minute per session, trimmed after about 8 days). The per-task record in `events.jsonl` is kept long-term but has no context %.

## Decisions

- **Record at task end, in the hook.** Without it, the join only works for the last about 8 days, so the view would rarely have enough data. Alternative considered: report-side join only. It is simpler, but limited to those 8 days. Both are kept: the hook value is preferred, and the join covers records written before this change.
- **Freshness limit of 15 minutes, in both places.** Older readings do not describe the turn that just ended.
- **Absent, not 0, when unknown.** Reports must tell "unknown" from "empty context".
- **Static panel, not a JS twin.** The bands are computed once in Python for the selected period, and the page filters do not change them. This follows the precedent of the per-call tool section and avoids a second implementation. The panel says so.
- **Same rate rules as the main summary** (`_summarise`), and the existing minimum of 5 known outcomes marks a band as low data.

## Risks / Trade-offs

- **Association, not cause.** Fuller contexts often mean longer, harder tasks. The page says this, and a controlled benchmark is the follow-up for cause.
- **Outcome is self-declared.** Verified outcome (an observed test or deploy) is shown beside it.
- **Missing data.** Headless runs, or a statusLine that is not configured, produce no reading. Such tasks are counted as "not placed".
- **Cost.** One bounded 256 KB tail read per turn in the Stop hook. It is fail-open.
- **Privacy.** Session ids are used only in memory for the join. The page embeds counts and rates only (tested).

## Validation

Unit tests cover band edges, rates, invalid values, the freshness limit, a reading after the task end, the window, and the loader. An end-to-end `generate` run checks the panel, the Markdown section, and that no session id is embedded. Six mutants were all caught. A real-session check (a live statusLine plus Stop) remains RUNTIME VALIDATION REQUIRED.
