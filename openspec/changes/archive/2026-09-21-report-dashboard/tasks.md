## 1. Generator
- [x] 1.1 `scripts/groundwork_report.py`: load/normalise (schema 1+2), bounded read, aggregate, compute, HTML (inline SVG, filters), Markdown, CLI
- [x] 1.2 launchd schedule (5 frequencies, replacement without duplicates, disabled removes), config, status
## 2. Install
- [x] 2.1 install.sh copies to `~/.claude/groundwork/bin/`, applies configured schedule; uninstall.sh removes job + script, keeps telemetry and reports
## 3. Verify
- [x] 3.1 `tests/test_report.py`: empty, malformed, missing fields, 7/30/90/365/all, profile/playbook/version filters, health + gap calculations, trends, insufficient data, HTML generation, manual generation, schedules, Python↔JS parity
- [x] 3.2 Live: install, generate from real telemetry, render preview, schedule weekly, docs, review
