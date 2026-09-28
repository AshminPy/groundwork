# Routines (Groundwork 2.1)

A Routine is recurring, scheduled automation that runs **without an active interactive session** — the fifth of Groundwork's five distinct concepts (`rules/task-routing.md` §4): a Playbook is how Groundwork handles a request *now*, in this session; a Role is a dynamic builder persona; a Skill is specialized invoked knowledge; a Tool is an execution/access mechanism; a Routine is a schedule instead of a user message as the trigger, and a headless, non-interactive `claude -p` session instead of your interactive one as the execution mode. A Routine's own scheduled run still goes through the same router and `rules/engineering-workflow.md` internally — it is not a second rule system.

Routines are entirely optional. `./setup.sh` with no interaction installs Groundwork with zero Routines configured and zero `config.json` written — nothing here changes that path.

## Why headless `claude -p`, and why not a custom scheduler

No native local (bare CLI) scheduling mechanism exists in Claude Code today (researched live, 2026-09-28, confirmed against current docs): cloud Routines require the hosted product; Desktop's scheduled tasks require the separate GUI app; `/loop` needs a continuously-running interactive session and self-expires after 7 days. Headless mode (`claude -p`) is the documented composition point for external automation, so `scripts/groundwork_routines.py` builds on it rather than inventing an alternative.

Scheduling itself reuses `scripts/groundwork_report.py`'s existing pattern exactly — one launchd plist per job on macOS (`launchctl bootstrap`/`bootout`), with the same "launchd is macOS-only; invoke manually or from cron elsewhere" fallback on other platforms. Nothing new was built for the scheduling mechanism itself; only the plist label changed shape, from `com.groundwork.report` to `com.groundwork.routine.<name>`, one per routine.

## Safety contract for unattended invocation

Every Routine invokes `claude -p` with exactly this flag combination, confirmed live against current Claude Code docs (2026-09-28):

- `--permission-mode dontAsk` — deny anything that would otherwise prompt, rather than hang waiting for a TTY that doesn't exist.
- `--permission-prompts none` — fail closed instead of hanging.
- `--allowedTools <explicit allowlist>` — scoped to exactly what that routine needs (read-only routines get `Bash(git *) Read Grep Glob WebSearch WebFetch`; `jira_eod`'s live-post path gets the same list — Routines never widen Jira write access beyond whatever the user already configured and already permitted).

**Never** `--dangerously-skip-permissions` — Anthropic's own docs restrict it to containers/VMs and refuse it under root/sudo, which does not describe every environment a Routine might run in. **Never** `--bare` — it would skip Groundwork's own hooks, skills, and MCP configuration, which a Routine needs active to inherit the same evidence and safety discipline as an interactive session.

An under-configured environment fails closed (the routine reports `BLOCKED`/`failed` with a reason) rather than guessing at what it's allowed to do.

## The six shipped Routines

| Routine | Mutates | Default schedule | What it does |
|---|---|---|---|
| `jira_eod` | Yes | daily | Reviews the day's evidenced engineering work (git, PRs, OpenSpec task checkboxes, investigation-continuity state, tests, reviews) and drafts a factual Jira comment per ticket with real work. Supports `--dry-run` (drafts only, never posts) and `--offline-work "..."` (folds in work you separately report, rewritten concisely). Never invents work; asks via a recorded blocker when work is evidenced but the ticket can't be determined. A live post must be read back before being reported `VERIFIED` — a successful tool call is not evidence of a successful mutation. |
| `news` | No | daily | A digest across configured topics (defaults: AI, Claude, Kubernetes, AWS, GCP — arbitrary custom topics supported), from authoritative/reputable sources only, deduplicated, filtered for genuine materiality. Says so plainly and produces no filler when nothing material happened; never stores full article bodies, only its own summary plus the source link. |
| `weekly_status` | No | weekly | Summarizes the repository's status using `engineering-workflow.md` §3's own completion-facts model — completed/in-progress/blocked/tests/review/merged/deployed/runtime-validated/decisions/next-actions — from evidence only. Merged is not deployed; deployed is not runtime-validated. |
| `pr_followup` | No | daily | Identifies PRs awaiting review, with requested changes, with failing CI, stale branches, merge conflicts, and complete-but-unmerged work, using `gh` (or the repo's own equivalent). **Merged is not deployed** — only reports a deployment with direct evidence, never inferred from a merge alone. |
| `work_digest` | No | daily | A TODAY/BLOCKED/FOLLOW-UP digest from git branches and dirty work, open PRs, OpenSpec task state, the investigation-continuity file, failed validation, pending review, and blocked deployments. Never creates a task from a weak or ambiguous signal. |
| `doc_drift` | No | weekly | Compares actual implementation against README/architecture docs/runbooks/OpenSpec artifacts and reports meaningful drift with the exact file/line and mismatch. **Never rewrites documentation itself** — a routine that silently rewrites docs on a schedule is exactly the kind of unreviewed automation Groundwork's evidence discipline exists to prevent. |

Each Routine is a name, a prompt-template function, a `mutates` boolean, and a default schedule in `scripts/groundwork_routines.py`'s `ROUTINES` registry — one generic framework, not six bespoke scripts.

### Deferred, not built this pass

**Task Observer** (detecting repeated manual patterns worth turning into a Routine) was evaluated and declined: every credible current implementation is designed near-always-on and conflicts with the strict no-raw-capture privacy requirement Routines are held to (no raw prompts, source, credentials, or transcripts persisted — see the telemetry section below). Six further routine candidates — certificate/PKI expiry, dependency/security advisories, infrastructure drift, cost anomaly review, stale-RCA follow-up, and release readiness — were scored and are recorded as future candidates in `docs/FUTURE-SCOPE.md` §13, not built this pass; six real, tested routines was already the right scope for one release, not fourteen built shallowly.

## Configuration

Routines are enabled per the capability profile chosen during `./setup.sh`'s optional capability-selection stage, or via `./setup.sh --configure` afterward (see `README.md`/`docs/ARCHITECTURE.md` for the full profile list). The result lands in one plain, human-readable, pretty-printed JSON file, `~/.claude/groundwork/config.json` (never YAML — see `openspec/changes/groundwork-2.1-context-routines-ux/design.md` §G for why), written and validated by `scripts/groundwork_config.py`. It is never overwritten by a re-run unless you explicitly reconfigure, and `uninstall.sh` removes it (it's Groundwork's own configuration, not your data — unlike telemetry, reports, or investigation files, which uninstall always keeps).

`config.json` never contains credentials — `groundwork_config.py validate` actively scans for token/password/secret/api_key/credential-shaped keys and flags them as a problem, not a warning.

## Commands

```
./setup.sh --configure          # revisit capability/Routine selection — no backup, no reinstall
./setup.sh --doctor              # read-only: core health + configured capabilities + every Routine's status
./setup.sh --routines            # list configured Routines and their last-run status
python3 ~/.claude/groundwork/bin/groundwork_routines.py run <name> [--dry-run] [--repo PATH] [--offline-work "..."]
python3 ~/.claude/groundwork/bin/groundwork_routines.py schedule <name> <daily|weekly|monthly|disabled>
python3 ~/.claude/groundwork/bin/groundwork_routines.py list
```

## Off-switches

`GROUNDWORK_ROUTINES=off` disables the whole subsystem — no `claude` process is ever spawned, even if `claude` is unreachable on `PATH`. `GROUNDWORK_ROUTINES_<NAME>=off` (e.g. `GROUNDWORK_ROUTINES_JIRA_EOD=off`) disables one routine without affecting the others.

## Telemetry

Each run appends one structured JSON line to `~/.claude/groundwork/telemetry/routines.jsonl` — same owner-only (`0600`), append-only, fail-open discipline as `hooks/groundwork_telemetry.py`'s own event log, in a sibling file (a routine run has no transcript to parse the same way a Claude Code hook does). Recorded fields: `routine`, `mutates`, `dry_run`, `status`, `exit_code`, `duration_s`, `output_chars`. **Never** the routine's actual prompt or output text, and never credentials — only enough to answer "did it run, when, how long, did it succeed" honestly. A telemetry write failure never fails the routine run itself.

## Live validation evidence

See `docs/VALIDATION.md`'s "Groundwork 2.1.0" entry for real `claude -p` invocations of `work_digest` and `jira_eod --dry-run` against this repository, including the exact telemetry record produced and its file permissions.
