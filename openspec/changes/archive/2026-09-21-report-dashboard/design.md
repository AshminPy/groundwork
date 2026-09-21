## Architecture-quality §2 answers

- **Likely to change / configuration:** schedule and window are config (`report.json`); metric definitions are code, documented in the page footer. Stable interface: the schema-2 record and the bucket JSON embedded in the page.
- **Another instance:** another profile/machine is another `CLAUDE_CONFIG_DIR`; the script takes `--events/--out` for ad-hoc runs.
- **Automation:** launchd runs `generate --snapshot`; manual run is the same command.
- **Dependency failure:** missing/unreadable telemetry → empty dashboard, exit 0; launchd failure → no report, nothing else affected (the generator never runs inside a hook).
- **Observability:** launchd stdout/stderr to `reports/logs/`; `status` prints config, plist and dashboard presence; the page header shows record and skipped counts.
- **Testing:** unit tests on synthetic events (empty, malformed, missing fields, filters, trends, insufficient data), Python-vs-JS parity via node, CLI generation, all schedule frequencies with launchctl stubbed, install/uninstall.
- **Security boundary:** local files only, 0600/0700; no network; the page makes no requests; only counters and short labels are embedded.
- **Scaling/cost:** reads at most the last 64 MB; buckets capped at 4000 (collapse to weeks); one small process per schedule tick.

## Decisions

**D1 — Aggregate in Python, recompute in JS from buckets.** The browser never sees raw events; filters stay client-side and offline. The two implementations are kept in parity by a test that runs the JS under node against the same buckets.
**D2 — Inline SVG, no charting library.** Seven small charts do not justify a dependency; offline and CDN-free by construction.
**D3 — Honest metrics only.** Rates carry numerator/denominator; unknown outcomes are excluded from denominators; rework and accuracy show N/A (not collected) rather than 0%; trends only when both periods have ≥5 known outcomes.
**D4 — launchd, one job.** `schedule` always boots out the previous job before writing the plist, so replacement never duplicates.
