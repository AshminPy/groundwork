# Routines (Groundwork 2.1)

A Routine is recurring, scheduled automation that runs **without an active interactive session** — the fifth of Groundwork's five distinct concepts (`rules/task-routing.md` §4): a Playbook is how Groundwork handles a request *now*, in this session; a Role is a dynamic builder persona; a Skill is specialized invoked knowledge; a Tool is an execution/access mechanism; a Routine is a schedule instead of a user message as the trigger, and a headless, non-interactive `claude -p` session instead of your interactive one as the execution mode. A Routine's own scheduled run still goes through the same router and `rules/engineering-workflow.md` internally — it is not a second rule system.

Routines are entirely optional. `./setup.sh` with no interaction installs Groundwork with zero Routines configured and zero `config.json` written — nothing here changes that path.

**Configure once, run automatically.** Each routine's identity (which Jira site, which GitHub user), scope (which tickets, which repositories, which topics), access mechanism, and mutation permission are collected **once**, during setup or `--configure`, and saved. A scheduled run never re-asks any of it — it loads the saved configuration, resolves the capabilities that specific configuration actually needs, and executes inside that scope. See "Configuration" below for the full schema.

## Why headless `claude -p`, and why not a custom scheduler

No native local (bare CLI) scheduling mechanism exists in Claude Code today (researched live, 2026-09-28, confirmed against current docs): cloud Routines require the hosted product; Desktop's scheduled tasks require the separate GUI app; `/loop` needs a continuously-running interactive session and self-expires after 7 days. Headless mode (`claude -p`) is the documented composition point for external automation, so `scripts/groundwork_routines.py` builds on it rather than inventing an alternative.

Scheduling itself reuses `scripts/groundwork_report.py`'s existing pattern exactly — one launchd plist per job on macOS (`launchctl bootstrap`/`bootout`), with the same "launchd is macOS-only; invoke manually or from cron elsewhere" fallback on other platforms. Nothing new was built for the scheduling mechanism itself; only the plist label changed shape, from `com.groundwork.report` to `com.groundwork.routine.<name>`, one per routine. Reconfiguring a routine's schedule replaces its one plist in place — it never leaves a stale duplicate behind.

## Safety contract for unattended invocation

Every Routine invokes `claude -p` with exactly this flag combination, confirmed live against current Claude Code docs (2026-09-28):

- `--permission-mode dontAsk` — deny anything that would otherwise prompt, rather than hang waiting for a TTY that doesn't exist.
- `--permission-prompts none` — fail closed instead of hanging.
- `--allowedTools <explicit allowlist>` — built fresh for **this routine + its own configured access mechanism + its own configured scope + its own configured mutation permission**, never one shared allowlist across all six. See "Capability grants" below for exactly what each routine can and cannot reach.

**Never** `--dangerously-skip-permissions` — Anthropic's own docs restrict it to containers/VMs and refuse it under root/sudo, which does not describe every environment a Routine might run in. **Never** `--bare` — it would skip Groundwork's own hooks, skills, and MCP configuration, which a Routine needs active to inherit the same evidence and safety discipline as an interactive session.

A routine whose required access is unconfigured reports `BLOCKED` **before `claude` is ever invoked** — confirmed live: a `jira_eod` run with no Jira access configured, and `claude` deliberately made unreachable on `PATH`, still returns `status: blocked` with a clear reason, never a crash from the missing binary, because the binary is never spawned.

## The six shipped Routines

| Routine | Mutates | Default schedule | What it does |
|---|---|---|---|
| `jira_eod` | Yes | daily 17:00 | Reviews the day's evidenced engineering work and drafts a factual Jira comment per in-scope ticket. Dry-run by default (`posting: dry_run`); switches to live posting only when explicitly configured `automatic`. Never invents work; asks via a recorded blocker when work is evidenced but the ticket can't be determined. A live post must be read back before being reported `VERIFIED` — a successful tool call is not evidence of a successful mutation. |
| `news` | No | daily 08:00 | A digest across configured topics (defaults: AI, Claude, Kubernetes, AWS, GCP — arbitrary custom topics supported), from authoritative/reputable sources only, deduplicated, filtered for genuine materiality. Says so plainly and produces no filler when nothing material happened; never stores full article bodies, only its own summary plus the source link. |
| `weekly_status` | No | weekly 08:00 | Summarizes the configured repository/integration scope using `engineering-workflow.md` §3's own completion-facts model — completed/in-progress/blocked/tests/review/merged/deployed/runtime-validated/decisions/next-actions — from evidence only. Merged is not deployed; deployed is not runtime-validated. |
| `pr_followup` | No | daily 08:00 | Identifies the **configured identity's own** PRs awaiting review, with requested changes, with failing CI, with merge conflicts, or requiring action, scoped to the configured repositories — never an unfiltered scan of every PR the account can see. **Merged is not deployed.** |
| `work_digest` | No | daily 08:00 | A TODAY/BLOCKED/FOLLOW-UP digest from git branches and dirty work, open PRs, OpenSpec task state, the investigation-continuity file, failed validation, pending review, and blocked deployments — scoped to the configured repository. Never creates a task from a weak or ambiguous signal. |
| `doc_drift` | No | weekly 08:00 | Compares actual implementation against the configured documentation paths and reports meaningful drift with the exact file/line and mismatch. **Never rewrites documentation itself.** |

Each Routine is a name, a prompt-template function, a `mutates` boolean, and a default schedule in `scripts/groundwork_routines.py`'s `ROUTINES` registry — one generic framework, not six bespoke scripts. `pr_followup`, `news`, `weekly_status`, `work_digest`, and `doc_drift` are structurally incapable of mutating anything — `mutates: False` means no write-shaped tool is ever in their allowlist, regardless of configuration. Only `jira_eod` can mutate, and only when explicitly configured to.

### Deferred, not built this pass

**Task Observer** (detecting repeated manual patterns worth turning into a Routine) was evaluated and declined: every credible current implementation is designed near-always-on and conflicts with the strict no-raw-capture privacy requirement Routines are held to (no raw prompts, source, credentials, or transcripts persisted — see "Telemetry vs. results" below). Six further routine candidates — certificate/PKI expiry, dependency/security advisories, infrastructure drift, cost anomaly review, stale-RCA follow-up, and release readiness — were scored and are recorded as future candidates in `docs/FUTURE-SCOPE.md` §13, not built this pass.

## Configuration

Enabled per the capability profile chosen during `./setup.sh`'s optional capability-selection stage, then **configured** by a short, per-routine interactive wizard that only asks about routines you actually enable — declining a routine asks nothing further about it. Revisit any single routine's configuration any time with `./setup.sh --configure` (menu: change profile / reconfigure one routine / cancel), without reinstalling Groundwork.

Everything lands in one plain, human-readable, pretty-printed JSON file, `~/.claude/groundwork/config.json` (never YAML — see `openspec/changes/groundwork-2.1-context-routines-ux/design.md` §G for why). It is never overwritten by a re-run unless you explicitly reconfigure, and `uninstall.sh` removes it (it's Groundwork's own configuration, not your data — unlike telemetry, reports, or investigation files, which uninstall always keeps).

**Never store passwords, API keys, tokens, cookies, or other credentials here.** Authentication stays owned by whatever MCP/CLI/browser/native mechanism you point a routine at — `config.json` only ever holds capability names, booleans, identities (usernames/emails — not secrets), scope descriptors, and schedule/topic strings. `scripts/groundwork_config.py`'s `set`/`init` actively validate every write and reject anything credential-shaped before it's saved; a rejected write leaves the previously-saved file untouched.

### Per-routine schema (illustrative — the exact shape `config.json`'s `routines` section uses)

```json
{
  "routines": {
    "jira_eod": {
      "enabled": true,
      "site": "https://company.atlassian.net",
      "identity": "user@company.com",
      "access": "jira_mcp",
      "mcp_server": "atlassian",
      "scope": { "type": "assigned_to_me" },
      "posting": "dry_run",
      "schedule": { "frequency": "daily", "time": "17:00" }
    },
    "pr_followup": {
      "enabled": true,
      "identity": "octocat",
      "access": "gh_cli",
      "scope": {
        "repositories": ["current"],
        "authored_by_me": true,
        "requested_changes": true,
        "failing_ci": true,
        "merge_conflicts": true,
        "requires_action": true
      },
      "schedule": { "frequency": "daily", "time": "08:00" }
    },
    "news": { "enabled": true, "topics": ["AI", "PKI"], "schedule": { "frequency": "daily", "time": "08:00" } }
  }
}
```

- **`jira_eod.access`**: `jira_mcp` (needs `mcp_server`, the MCP server name as configured in your own Claude Code `settings.json` — the wizard suggests `atlassian`), `cli`, `browser`, or `unconfigured` ("configure later" — the routine will report `BLOCKED`, never guess).
- **`jira_eod.scope.type`**: `assigned_to_me`, `created_by_me`, `projects` (with a `scope.projects` list), or `custom_jql` (with a `scope.jql` string).
- **`jira_eod.posting`**: `dry_run` (default — drafts only, `RESULT` block confirms nothing was posted) or `automatic` (posts, then reads the result back before reporting `VERIFIED`). An explicit `--dry-run` flag on a manual `run` always overrides `automatic` back to dry-run — a one-off ad hoc test never accidentally posts.
- **`pr_followup.access`**: `gh_cli`, `github_mcp`, or `unconfigured`. `pr_followup` never gets a write-shaped GitHub tool regardless — it structurally cannot mutate.
- **`pr_followup.scope.repositories`**: `["current"]` (default) or an explicit list of `owner/repo` — never "every repository the account can see."
- **`news.topics`**: any list of strings — the suggested set (AI, Claude, Agentic AI, PKI, Cybersecurity, GCP, AWS, Kubernetes, Terraform, SRE) is only a starting offer; arbitrary custom topics persist exactly as entered.
- **`weekly_status`/`work_digest`**: `repository_scope` (defaults to `["current"]`); `use_github`/`use_jira` — when true, the routine **reuses `pr_followup`'s or `jira_eod`'s own already-configured access** rather than asking for a third identity/mechanism for the same external system. If the routine it depends on isn't configured, it reports `BLOCKED` naming which one.
- **`doc_drift`**: `repository` (default `"current"`), `doc_paths` (default `["README.md", "docs/"]`), `impl_paths` (default `[]`, meaning "the implementation as a whole").
- **Every routine's `schedule`**: `{"frequency": "daily"|"weekly"|"monthly"|"disabled", "time": "HH:MM"}` (24-hour).

## Capability grants — built from routine + access + scope + mutation permission

`--allowedTools` is never one shared list. Each routine's own configuration decides exactly what it can reach:

| Routine | Grant |
|---|---|
| `news` | `Bash(git *) Read Grep Glob` + `WebSearch`/`WebFetch`. Never blockable — no external identity needed. |
| `doc_drift` | `Bash(git *) Read Grep Glob` only. Never blockable, never gets web or MCP access. |
| `pr_followup` (`gh_cli`) | Base tools + exact read-only `gh` subcommands (`pr list`/`view`/`checks`/`diff`) — never a mutating one. |
| `pr_followup` (`github_mcp`) | Base tools + real, session-confirmed read-only GitHub MCP tool names (`get_me`, `list_pull_requests`, `pull_request_read`, `search_pull_requests`, `list_commits`, `get_commit`) — chosen explicitly, not a wildcard. |
| `jira_eod` (`jira_mcp`) | Base tools + the configured MCP server's tools at the server level (`mcp__<server>__*`) — BLOCKED if no server name is configured. An arbitrary user-configured server's exact per-tool read/write split isn't knowable in advance without guessing tool names, so the read/write boundary within that grant is enforced by the routine's own prompt instructions (dry-run explicitly forbids calling a write tool) plus your own Claude Code `settings.json` permission scoping for that server — the same "MCP access belongs to the task's own environment" principle Groundwork already applies everywhere else, not a special exception for Routines. |
| `jira_eod` (`cli`/`browser`) | Base tools + a generic `Bash(jira *)` allowance, or the browser MCP tools, respectively. |
| `weekly_status`/`work_digest` | Base tools + whatever `pr_followup`/`jira_eod` already grant, only if `use_github`/`use_jira` is configured true and that routine's own access is actually configured (otherwise `BLOCKED`, naming the dependency). |

Any routine with an unconfigured required access mechanism is `BLOCKED` before `claude` is ever invoked — confirmed via `tests/test_groundwork_routines.py` with `claude` deliberately unreachable on `PATH`.

## Semantic status — never exit-code-only

Every routine's prompt ends with a required structured block:

```
ROUTINE RESULT
Status: COMPLETE|PARTIAL|BLOCKED|FAILED
Summary: <one line>
```

(Same shape/tolerance as `hooks/require_material_review.py`'s proven `REVIEW RESULT` block — not a new format.) `claude -p` exiting 0 is **never by itself** treated as `COMPLETE`:

- A clean exit with a missing or unparseable block is recorded `FAILED` — the routine's own output violated the contract, so its status can't be trusted.
- A clean exit whose block reports `BLOCKED` or `PARTIAL` is recorded as exactly that — never silently upgraded because the process itself didn't crash. (Example: the model tried to reach Jira mid-run and the MCP server was unavailable — `Status: BLOCKED`, recorded as blocked, not complete.)
- A non-zero exit code is always `FAILED`, regardless of anything else — a process crash is a crash.

`SKIPPED` is reserved for off-switches and a disabled-in-config routine, both of which never invoke `claude` at all.

## Telemetry vs. results

Two separate places, by design:

- **Telemetry** (`~/.claude/groundwork/telemetry/routines.jsonl`) — metadata only: `routine`, `mutates`, `dry_run`, `status`, `exit_code`, `duration_s`, `output_chars`. Owner-only (`0600`), append-only, fail-open, same discipline as `hooks/groundwork_telemetry.py`. **Never** the routine's actual output text, confirmed by direct inspection.
- **Results** (`~/.claude/groundwork/routines/results/<name>/run-<timestamp>.json`) — the routine's real, useful output (the digest, the drafted/posted comment text, the status summary) — what you'd actually want to read. Owner-only (`0600` files, `0700` directory), retained to the 10 most recent runs per routine, older ones pruned automatically.

## Commands

```
./setup.sh --configure               # menu: change profile / reconfigure one routine / cancel
./setup.sh --doctor                   # read-only: core health + configured capabilities + every Routine's real detail
./setup.sh --routines                 # list configured Routines and their last-run status
./setup.sh --routines NAME            # print that Routine's most recent stored result
python3 ~/.claude/groundwork/bin/groundwork_routines.py run <name> [--dry-run] [--repo PATH] [--offline-work "..."]
python3 ~/.claude/groundwork/bin/groundwork_routines.py schedule <name> <daily|weekly|monthly|disabled> [--hour H] [--minute M]
python3 ~/.claude/groundwork/bin/groundwork_routines.py list
python3 ~/.claude/groundwork/bin/groundwork_routines.py latest <name>
python3 ~/.claude/groundwork/bin/groundwork_routines.py doctor
python3 ~/.claude/groundwork/bin/groundwork_config.py get <routine> <dotted.key>
python3 ~/.claude/groundwork/bin/groundwork_config.py set <routine> key=value [key=value ...]
```

## Off-switches

`GROUNDWORK_ROUTINES=off` disables the whole subsystem — no `claude` process is ever spawned, even if `claude` is unreachable on `PATH`. `GROUNDWORK_ROUTINES_<NAME>=off` (e.g. `GROUNDWORK_ROUTINES_JIRA_EOD=off`) disables one routine without affecting the others.

## `--doctor`: CONFIGURED ≠ AVAILABLE ≠ CONNECTED ≠ VERIFIED

`--doctor` never reports a mechanism as `CONNECTED` just because `config.json` names it. It does what it can safely check, and says plainly when it can't:

- `gh_cli`: checks `gh` is on `PATH` (AVAILABLE) and `gh auth status` (CONNECTED — a real, safe, read-only check).
- `jira_mcp`/`github_mcp`: checks `claude mcp list` for the configured server name (AVAILABLE, if found) — actual connectivity isn't probed from a shell command, so this is honestly reported as "not checked here" rather than asserted.
- `cli`/`browser` access: not checked from `--doctor` at all — verified at first live run instead.

No credential or other sensitive value is ever printed — Jira identity shows as `configured`/`not configured` rather than the literal email; GitHub identity (a public username) is shown plainly.

## Live validation evidence

See `docs/VALIDATION.md`'s "Groundwork 2.1.0" entries for real `claude -p` invocations of `work_digest` and `jira_eod --dry-run` against this repository, and the full interactive wizard → doctor → reconfigure → result-retrieval cycle exercised through `tests/test_setup.py::test_routine_configuration_wizard`.
