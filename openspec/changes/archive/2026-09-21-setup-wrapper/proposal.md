## Why

New users had to follow several manual steps (install, profile env, schedule) with no backup or verification. A one-click `setup.sh` should make `git clone … && ./setup.sh` sufficient without replacing the tested installer.

## What Changes

- `setup.sh` (new): prerequisites → complete backup of `~/.claude` to `~/.claude-backups/groundwork-<ts>/` (owner-only, never overwritten) → profile / Agent Teams / schedule questions (or `--non-interactive` flags) → `install.sh` → `merge_settings.py --profile` → `groundwork_report.py schedule` → verification + deterministic tests → first dashboard → summary. Modes `--verify` (read-only), `--rollback [DIR]` (moves the current dir aside, restores the latest unambiguous backup), `--uninstall` (delegates).
- `scripts/merge_settings.py --profile NAME` sets `env.GROUNDWORK_PROFILE` additively; `unmerge_settings.py` removes it.
- README Quick start uses `./setup.sh`; `install.sh` documented under manual/advanced.

## Non-goals

`install.sh`, `uninstall.sh`, hooks, telemetry, reporting, playbooks, routing and security controls are unchanged; setup.sh contains no installation logic.
