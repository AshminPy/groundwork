## Why

The owner asked whether answer quality drops once the context window is about 70% full, and whether the dashboard can show it. It cannot today: the statusLine logs the context % about once a minute per session (kept about 8 days), and the per-task record logs the outcome, but nothing joins the two and the usage log expires.

## What Changes

- The telemetry hook's per-task record gains an optional `observed.ctx_pct`: the context-window % from the session's latest statusLine reading, taken when the turn ends. It is absent, never 0, when there is no reading or the latest one is older than 15 minutes.
- The health dashboard and the dated Markdown snapshot gain one section, "Outcome by context fill at task end". It shows completion, verified outcome and gap rate in five bands (0–30, 30–50, 50–70, 70–85, 85–100%). For older records it matches the statusLine reading at or just before the task ended.
- The section states its limits on the page: it shows association, not cause; outcome is self-declared; low-data bands are marked; tasks without a reading are counted but not placed.

## Capabilities

### New Capabilities

### Modified Capabilities
- `usage-telemetry`: per-task record may carry the context-window % at task end.
- `health-dashboard`: outcome rates by context-fill band.

## Impact

- `hooks/groundwork_telemetry.py`: reads the end of `usage.jsonl` once per turn; fail-open.
- `scripts/groundwork_report.py`: new section; no change to existing metrics or the JS filters.
- New test file `tests/test_context_bands.py`.
