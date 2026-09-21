## Why

Groundwork telemetry (schema 2, `~/.claude/groundwork/telemetry/events.jsonl`) exists but nothing reads it. The user wants a local, self-contained health dashboard regenerated on a schedule, with Markdown as a secondary export — no server, no LLM, no network.

## What Changes

- `scripts/groundwork_report.py` (installed to `~/.claude/groundwork/bin/`): `generate` aggregates events into bounded day-level buckets, computes the metrics (Python), embeds the buckets in `dashboard.html` whose JavaScript recomputes the same metrics for client-side filters (period 7/30/90/365/all, profile, playbook, version, environment), and writes dated `YYYY-MM-DD.html` / `.md` snapshots with `--snapshot`. `schedule disabled|daily|weekly|monthly|yearly` writes/replaces one launchd agent (`com.groundwork.report`); `status` prints config.
- Config `~/.claude/groundwork/report.json`: schedule (default weekly) and health window (default 30 days) are separate.
- Installer copies the script and applies the configured schedule; uninstall removes the job and script but keeps telemetry and reports.

## Non-goals

No change to routing, playbooks, output behaviour, evidence/security controls, hooks, Git protections or task execution. No rework rate or accuracy score without ground truth (shown as N/A).
