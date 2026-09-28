#!/usr/bin/env python3
"""Groundwork 2.1 Routines — recurring/scheduled automation, distinct from a Playbook (task-routing.md §4).

Each routine is a name + a prompt template + a mutates flag + a default schedule: one generic
framework, not six bespoke scripts. A scheduled run invokes a real, separate, non-interactive
`claude -p` session per routine (never the interactive session's own context — routines are
isolated by construction, docs/CONTEXT-ENGINEERING.md).

Configure once, run automatically (owner requirement, added after the first release candidate):
a routine's identity, scope, access mechanism, and mutation permission are collected ONCE by the
setup/configure wizard and saved in config.json (scripts/groundwork_config.py) — a scheduled run
never re-asks which Jira site, which GitHub user, which repositories, or which topics. If a
routine that needs an access mechanism (jira_eod, pr_followup) has none configured, it reports
BLOCKED without ever invoking `claude` — never guesses, never falls back to a broader scope.

Safe unattended invocation (confirmed live against code.claude.com, 2026-09-28 — see design.md §C):
NEVER --dangerously-skip-permissions (restricted to containers/VMs, refused under root/sudo).
NEVER --bare (would skip Groundwork's own hooks/skills/MCP config that routines should inherit).
Uses --permission-mode dontAsk + --permission-prompts none + an explicit --allowedTools allowlist
built from routine + configured access mechanism + configured scope + configured mutation
permission (never one flat global allowlist — see _capabilities_for() and design.md §D.3):
anything not pre-configured is safely denied, not guessed at — an under-configured environment
fails closed (BLOCKED), never fabricates success. The allowlist decides whether a mechanism is
reachable at all; fine-grained read/write authorization *within* a granted MCP server is still the
user's own Claude Code settings.json, per Groundwork's existing capability-ownership principle
("MCP/external tool access belongs to the task's own environment") — documented, not hidden.

Scheduling extends the exact pattern already proven for the health dashboard
(groundwork_report.py's launchd-on-macOS/cron-elsewhere scheduler) — no new scheduler.

Semantic status (owner requirement): a routine's own `claude -p` output must end with a
structured `ROUTINE RESULT` block (Status: COMPLETE|PARTIAL|BLOCKED|FAILED, Summary: ...) — same
shape/tolerance as require_material_review.py's proven `REVIEW RESULT` parser. Exit code 0 alone
is never treated as COMPLETE; a missing or malformed block on an otherwise-successful process is
FAILED, not silently upgraded.

Result delivery (owner requirement): the routine's own useful output (digest/report/status) is
stored separately from telemetry, under routines/results/<name>/, bounded retention, owner-only —
retrieve with `latest <name>`. Telemetry stays metadata-only, exactly as before.

Disable a specific routine with GROUNDWORK_ROUTINES_<NAME>=off. Disable the whole subsystem with
GROUNDWORK_ROUTINES=off. Path override: GROUNDWORK_ROUTINES_TELEMETRY_PATH.
"""
import argparse
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import groundwork_config as gcfg  # noqa: E402

LABEL_PREFIX = "com.groundwork.routine"
DEFAULT_TIMEOUT_S = 600
RESULT_RETENTION = 10
BASE_REPO_READ = ["Bash(git *)", "Read", "Grep", "Glob"]

# Real, session-confirmed GitHub MCP tool names (github/github-mcp-server, official) — read-only,
# deliberately excluding every write-shaped tool (create/merge/update/push/*_write, etc.), since
# pr_followup never mutates (ROUTINES["pr_followup"]["mutates"] is False, unchanged by this pass).
GITHUB_MCP_READ_TOOLS = [
    "mcp__github__get_me", "mcp__github__list_pull_requests", "mcp__github__pull_request_read",
    "mcp__github__search_pull_requests", "mcp__github__list_commits", "mcp__github__get_commit",
]
GH_CLI_READ_TOOLS = ["Bash(gh pr list*)", "Bash(gh pr view*)", "Bash(gh pr checks*)", "Bash(gh pr diff*)"]

# Same "ROUTINE RESULT" shape/tolerance as hooks/require_material_review.py's proven
# "REVIEW RESULT" parser — not a new format.
ROUTINE_RESULT_HEADING = re.compile(r"^\s*(?:#+\s*|\*\*)?ROUTINE RESULT(?:\*\*)?\s*$", re.MULTILINE | re.IGNORECASE)
ROUTINE_RESULT_FIELD = re.compile(r"^\s*(?:[-*]\s*)?\**\s*([A-Za-z][A-Za-z -]*?)\s*\**\s*:\s*\**\s*(.+?)\s*$")
KNOWN_SEMANTIC_STATUS = {"complete", "partial", "blocked", "failed", "skipped"}

RESULT_CONTRACT = (
    "End your response with a structured block, exactly:\n\n"
    "ROUTINE RESULT\n"
    "Status: COMPLETE|PARTIAL|BLOCKED|FAILED\n"
    "Summary: <one line>\n\n"
    "Status meanings: COMPLETE = everything in scope was actually done and verified where this "
    "routine's own instructions require verification. PARTIAL = some of the scope succeeded, some "
    "didn't (say what, in Summary). BLOCKED = you could not proceed at all (e.g. a required tool "
    "was denied or unavailable) — never silently do nothing and call it COMPLETE. FAILED = a real "
    "error occurred. Never report COMPLETE for something you could not actually verify happened."
)


def _telemetry_path() -> Path:
    override = os.environ.get("GROUNDWORK_ROUTINES_TELEMETRY_PATH")
    if override:
        return Path(override)
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    return base / "groundwork" / "telemetry" / "routines.jsonl"


def _config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))


def _results_dir(name: str) -> Path:
    return _config_dir() / "groundwork" / "routines" / "results" / name


def _record(event: dict) -> None:
    """Append one JSON line, owner-only, fail-open — mirrors hooks/groundwork_telemetry.py's own
    pattern exactly. Metadata only: never the routine's actual output text (that's stored
    separately by _store_result(), never here — owner requirement, §12)."""
    try:
        path = _telemetry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, sort_keys=True) + "\n"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except Exception:
        pass  # telemetry must never break a routine run


def _store_result(name: str, status: str, summary: str, content: str, dry_run: bool, mutates: bool) -> None:
    """The routine's own useful output — the actual digest/report/status a user can consume —
    kept separate from telemetry, owner-only, bounded retention. Fail-open: a storage failure
    must never fail (or be conflated with) the routine run itself."""
    try:
        d = _results_dir(name)
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        ts = int(time.time())
        record = {"routine": name, "started_at": ts, "status": status, "summary": summary,
                   "content": content, "dry_run": dry_run, "mutates": mutates}
        path = d / f"run-{ts}.json"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, json.dumps(record, indent=2).encode("utf-8"))
        finally:
            os.close(fd)
        runs = sorted(d.glob("run-*.json"))
        for old in runs[:-RESULT_RETENTION]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception:
        pass


def latest_result(name: str) -> dict | None:
    d = _results_dir(name)
    runs = sorted(d.glob("run-*.json")) if d.is_dir() else []
    if not runs:
        return None
    try:
        return json.loads(runs[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def parse_routine_result(text: str) -> dict:
    """Fields of a routine's own 'ROUTINE RESULT' block, if it emitted one. Returns {} when no
    block is found or nothing in it parses — callers must treat that as unknown/FAILED, never as
    an implicit COMPLETE (owner requirement §13)."""
    if not text:
        return {}
    m = ROUTINE_RESULT_HEADING.search(text)
    if not m:
        return {}
    fields = {}
    for line in text[m.end():].splitlines():
        if not line.strip():
            if fields:
                break
            continue
        f = ROUTINE_RESULT_FIELD.match(line)
        if not f:
            if fields:
                break
            continue
        fields[f.group(1).strip().lower()] = f.group(2).strip().strip("*")
    result: dict = {}
    status = fields.get("status", "").strip().lower()
    if status in KNOWN_SEMANTIC_STATUS:
        result["status"] = status
    if "summary" in fields:
        result["summary"] = fields["summary"]
    result["block_start"] = m.start()
    return result


def _jira_scope_desc(scope: dict) -> str:
    t = (scope or {}).get("type", "assigned_to_me")
    if t == "assigned_to_me":
        return "tickets currently assigned to the configured identity"
    if t == "created_by_me":
        return "tickets created by the configured identity"
    if t == "projects":
        projects = ", ".join(scope.get("projects", [])) or "(no projects listed — treat as none in scope)"
        return f"tickets in these projects only: {projects}"
    if t == "custom_jql":
        return f"tickets matching this exact JQL only: {scope.get('jql', '')}"
    return "tickets currently assigned to the configured identity"


def _jira_tools(rc: dict) -> tuple[list, str | None]:
    access = rc.get("access", "unconfigured")
    if access == "unconfigured":
        return [], "Jira access not configured — run ./setup.sh --configure"
    if access == "browser":
        return ["mcp__Claude_Browser__*", "mcp__claude-in-chrome__*"], None
    if access == "cli":
        return ["Bash(jira *)"], None
    if access == "jira_mcp":
        server = (rc.get("mcp_server") or "").strip()
        if not server:
            return [], "Jira MCP server name not configured — run ./setup.sh --configure"
        return [f"mcp__{server}__*"], None
    return [], f"unknown Jira access mechanism: {access}"


def _github_tools(rc: dict) -> tuple[list, str | None]:
    access = rc.get("access", "unconfigured")
    if access == "unconfigured":
        return [], "GitHub access not configured — run ./setup.sh --configure"
    if access == "gh_cli":
        return list(GH_CLI_READ_TOOLS), None
    if access == "github_mcp":
        return list(GITHUB_MCP_READ_TOOLS), None
    return [], f"unknown GitHub access mechanism: {access}"


def _pr_scope_desc(scope: dict) -> str:
    repos = scope.get("repositories", ["current"])
    repo_desc = "the current repository only" if repos == ["current"] else f"exactly these repositories: {', '.join(repos)}"
    filters = []
    if scope.get("authored_by_me"):
        filters.append("authored by the configured identity")
    if scope.get("requested_changes"):
        filters.append("with requested changes on the configured identity's PRs")
    if scope.get("failing_ci"):
        filters.append("with failing CI on the configured identity's PRs")
    if scope.get("merge_conflicts"):
        filters.append("with merge conflicts on the configured identity's PRs")
    if scope.get("requires_action"):
        filters.append("requiring the configured identity's action")
    return f"{repo_desc}; only: {'; '.join(filters) if filters else 'authored by the configured identity'}"


def _jira_eod_prompt(rc: dict, dry_run: bool, offline_work: str) -> str:
    posting = rc.get("posting", "dry_run")
    effective_dry_run = dry_run or posting != "automatic"
    site = rc.get("site") or "(no site configured)"
    identity = rc.get("identity") or "(no identity configured)"
    scope_desc = _jira_scope_desc(rc.get("scope", {}))
    dry_run_line = (
        "This is a DRY RUN: draft the exact Jira comment(s) you would post, and print each one "
        "clearly labeled with its ticket key, but do NOT call any tool that would actually write "
        "to Jira. End with 'DRY RUN — nothing was posted.' before the ROUTINE RESULT block."
        if effective_dry_run else
        "This is a LIVE run: after drafting each comment, post it via whatever Jira write "
        "mechanism is already configured and already permitted — if none is available or "
        "permitted, say so plainly and treat that ticket as BLOCKED rather than inventing a post. "
        "After posting, read the ticket/comment back to confirm it actually landed before "
        "reporting it VERIFIED in your summary — a successful tool call is not evidence of a "
        "successful mutation."
    )
    offline_block = (
        f"\n\nThe user separately reported this work, which may not be visible in git/PR/OpenSpec "
        f"evidence — fold it into the relevant ticket's update, rewritten concisely and "
        f"professionally, only if it's genuinely relevant:\n{offline_work}\n"
        if offline_work else ""
    )
    return f"""You are running Groundwork's Jira end-of-day routine, a scheduled Routine (not an interactive session) — see rules/task-routing.md's Playbook/Routine distinction and engineering-workflow.md's evidence and completion rules, which still apply.

Configured scope (do not go outside it, and do not ask the user to restate it — this was configured once during setup): Jira site {site}, identity {identity}, scope: {scope_desc}.

Goal: review today's engineering work in the current repository and prepare a factual, concise Jira ticket update for each in-scope ticket that had real, evidenced work today.

Evidence sources, in order: git log/diff for commits made today, open/updated PRs, OpenSpec task-checkbox changes, the investigation-continuity file for this repo if one exists, test results, review outcomes, deployment/runtime validation actually observed today. Never invent work: if evidence suggests work happened but you cannot determine which in-scope ticket it belongs to, say so explicitly as a blocker rather than guessing a ticket key.

For each ticket with real evidenced work, draft a comment covering only what's relevant and actually true: work completed, evidence/validation (command + result, not just "tests pass"), blockers, remaining work, next action. Never claim deployment or live/runtime validation without direct evidence you observed yourself today. Keep it concise and professional — this is read by humans, not a raw evidence dump.
{offline_block}
{dry_run_line}

If no in-scope ticket had meaningful evidenced work today, say so plainly and do not post or draft anything — avoid comments when nothing meaningful changed.

{RESULT_CONTRACT}"""


def _news_prompt(rc: dict) -> str:
    topics = rc.get("topics", [])
    topic_list = ", ".join(topics) if topics else "AI, Claude, agentic AI, cybersecurity, SRE"
    return f"""You are running Groundwork's daily technical-news routine, a scheduled Routine (not an interactive session).

Configured topics (set once during setup, not re-asked here): {topic_list}.

Research current news for these topics using authoritative, reputable sources only (official vendor blogs/docs, established technical press — not random forum posts). Deduplicate across sources. Filter for genuine materiality — skip routine/minor updates. For each item worth including: a concise summary, the source link, and why it matters when that's not obvious.

If nothing material happened across these topics since the last run, say so plainly in one line — do not manufacture filler content to make the digest look substantial. Do not store or reproduce full article bodies, only your own summary plus the source link.

{RESULT_CONTRACT}"""


def _jira_evidence_note() -> str:
    """weekly_status/work_digest never get a live Jira tool (they're mutates: False — see
    _capabilities_for()'s comment). Instead they're pointed at jira_eod's own already-stored,
    already-evidenced result file: zero additional capability, since Read/Glob are already granted
    to every routine via BASE_REPO_READ."""
    d = _results_dir("jira_eod")
    return (
        f"For Jira status, do NOT call any live Jira tool — none is granted to this "
        f"routine. Instead, use Read/Glob to check {d}/run-*.json for the most recent file "
        f"(sort by filename/timestamp) — it holds jira_eod's own last stored result (status, "
        f"summary, content) as JSON. If no such file exists, say plainly that no Jira EOD run "
        f"has produced evidence yet rather than fabricating Jira status."
    )


def _weekly_status_prompt(rc: dict) -> str:
    repo_scope = rc.get("repository_scope", ["current"])
    repo_desc = "the current repository only" if repo_scope == ["current"] else ", ".join(repo_scope)
    period = rc.get("period_days", 7)
    parts = [f"the repository scope: {repo_desc}, over the last {period} days"]
    if rc.get("include_openspec", True):
        parts.append("OpenSpec task progress")
    jira_projects = rc.get("jira_projects") or []
    if jira_projects:
        parts.append(f"Jira project(s) {', '.join(jira_projects)}")
    body = [
        "You are running Groundwork's weekly status routine, a scheduled Routine (not an interactive session).",
        f"Configured scope (set once during setup, not re-asked here): {'; '.join(parts)}. Do not pull in unrelated projects or repositories simply because they happen to be accessible.",
        "Using engineering-workflow.md §3's own completion-facts model (code written, tests run, independent review, merged, deployed, live validated — plus completed/in-progress/blocked), summarize the in-scope repository's status from real evidence: git history, PR state, OpenSpec task progress, test results, review outcomes, deployment/runtime validation actually observed.",
        "Cover: completed, in progress, blocked, decisions made, next actions. Do not invent status for anything you lack evidence for — state it as unknown rather than guessing. Merged is not deployed; deployed is not runtime-validated; keep those distinctions exact.",
    ]
    if jira_projects:
        body.append(f"{_jira_evidence_note()} Only the ticket(s)/project(s) {', '.join(jira_projects)} are in scope — ignore anything else in that file.")
    body.append(RESULT_CONTRACT)
    return "\n\n".join(body)


def _pr_followup_prompt(rc: dict) -> str:
    identity = rc.get("identity") or "(no identity configured)"
    scope_desc = _pr_scope_desc(rc.get("scope", {}))
    return f"""You are running Groundwork's PR/review follow-up routine, a scheduled Routine (not an interactive session).

Configured scope (set once during setup, not re-asked here): GitHub identity {identity}; {scope_desc}. This is the user's OWN pull requests, never an unfiltered scan of every PR the account can see or every PR in an organization — use the configured identity as an explicit filter in every query (e.g. `gh pr list --author {identity} ...`, or the equivalent parameter on whatever tool is available), never an unscoped `gh pr list`.

Using the tools available (scoped to read-only — this routine never mutates GitHub), identify only what the configured scope above asks for: PRs awaiting review, PRs with requested changes, PRs with failing CI, stale branches, PRs with merge conflicts, work that is complete but not yet merged — filtered to the configured identity and repository scope. Report each with the evidence (exact command + result), not a guess.

MERGED IS NOT DEPLOYED — only report something as deployed if you have direct evidence of a deployment, never inferred from a merge alone. If nothing in scope needs attention, say so plainly.

{RESULT_CONTRACT}"""


def _work_digest_prompt(rc: dict) -> str:
    repo_scope = rc.get("repository_scope", ["current"])
    repo_desc = "the current repository only" if repo_scope == ["current"] else ", ".join(repo_scope)
    wants_jira = bool(rc.get("use_jira"))
    sources = ["git branches and dirty work", "open PRs" if rc.get("use_github", True) else None,
               "OpenSpec task state" if rc.get("include_openspec", True) else None,
               "Jira ticket state (via jira_eod's stored result, see below)" if wants_jira else None,
               "the investigation-continuity file if one exists", "failed validation", "pending review",
               "blocked deployments"]
    sources = [s for s in sources if s]
    body = [
        "You are running Groundwork's daily work/TODO digest routine, a scheduled Routine (not an interactive session).",
        f"Configured scope (set once during setup, not re-asked here): {repo_desc}. Do not search repositories outside this scope.",
        f"From real evidence only — {', '.join(sources)} — produce three short sections: TODAY (concrete next actions with real evidence behind them), BLOCKED (what's blocking, and on what), FOLLOW-UP (loose ends worth revisiting).",
        "Do not create a task from a weak or ambiguous signal — a real task needs real evidence, not a guess dressed up as one.",
    ]
    if wants_jira:
        body.append(_jira_evidence_note())
    body.append(RESULT_CONTRACT)
    return "\n\n".join(body)


def _doc_drift_prompt(rc: dict) -> str:
    repo = rc.get("repository", "current")
    doc_paths = rc.get("doc_paths", ["README.md", "docs/"])
    impl_paths = rc.get("impl_paths", [])
    impl_desc = f" against implementation paths {', '.join(impl_paths)}" if impl_paths else " against the implementation as a whole"
    return f"""You are running Groundwork's documentation-drift routine, a scheduled Routine (not an interactive session).

Configured scope (set once during setup, not re-asked here): repository {repo if repo != 'current' else '(current)'}, documentation paths {', '.join(doc_paths)}{impl_desc}.

Compare the actual current implementation (code, configuration, tests, CI) against the configured documentation paths. Report only meaningful drift — a documented claim that no longer matches what the code does, a missing capability that's documented as shipped, or vice versa.

Do NOT rewrite documentation yourself in this routine — report the drift found, with the exact file/line and the exact mismatch, for a human or a follow-up session to fix. A routine that silently rewrites documentation on a schedule is exactly the kind of unreviewed automation Groundwork's evidence discipline exists to prevent.

{RESULT_CONTRACT}"""


ROUTINES = {
    "jira_eod": {"mutates": True, "default_schedule": "daily", "prompt": _jira_eod_prompt, "needs_offline_work": True},
    "news": {"mutates": False, "default_schedule": "daily", "prompt": _news_prompt, "needs_offline_work": False},
    "weekly_status": {"mutates": False, "default_schedule": "weekly", "prompt": _weekly_status_prompt, "needs_offline_work": False},
    "pr_followup": {"mutates": False, "default_schedule": "daily", "prompt": _pr_followup_prompt, "needs_offline_work": False},
    "work_digest": {"mutates": False, "default_schedule": "daily", "prompt": _work_digest_prompt, "needs_offline_work": False},
    "doc_drift": {"mutates": False, "default_schedule": "weekly", "prompt": _doc_drift_prompt, "needs_offline_work": False},
}


def _capabilities_for(name: str, cfg: dict) -> tuple[list, str | None]:
    """Builds the runtime capability set from routine + configured access mechanism + configured
    scope + configured mutation permission — never one flat global allowlist (owner requirement
    §10). Returns (tools, blocked_reason); blocked_reason is set when the routine cannot run at
    all with its current configuration — the caller must not invoke `claude` in that case."""
    rc = cfg.get("routines", {}).get(name, {})
    tools = list(BASE_REPO_READ)
    if name == "news":
        return tools + ["WebSearch", "WebFetch"], None
    if name == "jira_eod":
        jtools, reason = _jira_tools(rc)
        return tools + jtools, reason
    if name == "pr_followup":
        gtools, reason = _github_tools(rc)
        return tools + gtools, reason
    if name == "doc_drift":
        return tools, None
    if name in ("weekly_status", "work_digest"):
        wants_github = rc.get("use_github", name == "weekly_status")
        if wants_github:
            pr_rc = cfg.get("routines", {}).get("pr_followup", {})
            if pr_rc.get("access", "unconfigured") == "unconfigured":
                return [], f"{name} is configured to use GitHub, but no GitHub access is configured (configure pr_followup or run ./setup.sh --configure)"
            gtools, reason = _github_tools(pr_rc)
            if reason:
                return [], reason
            tools += gtools
        # Jira cross-referencing (weekly_status's `jira_projects`, work_digest's `use_jira`) never
        # grants a live Jira tool: weekly_status/work_digest are declared mutates: False, and none
        # of the configured Jira access mechanisms (jira_mcp/cli/browser) can be safely narrowed to
        # read-only — granting jira_eod's own wildcard here would hand a structurally non-mutating
        # routine the same write-shaped surface as jira_eod's live-posting mode, which
        # specs/routines/spec.md's non-mutating-routine requirement forbids regardless of
        # configuration. Instead these routines read jira_eod's own already-stored, already-
        # evidenced result file (see _jira_evidence_note() below) — Read/Glob are already in
        # BASE_REPO_READ, so this needs no additional tool grant at all.
        return tools, None
    return tools, None


def is_macos() -> bool:
    override = os.environ.get("GROUNDWORK_OS")
    if override:
        return override.strip().lower() == "darwin"
    return sys.platform == "darwin"


def launch_agents_dir() -> Path:
    return Path(os.path.expanduser(os.environ.get("GROUNDWORK_LAUNCH_AGENTS_DIR") or "~/Library/LaunchAgents"))


def _label(name: str) -> str:
    return f"{LABEL_PREFIX}.{name}"


def _plist_path(name: str) -> Path:
    return launch_agents_dir() / f"{_label(name)}.plist"


def _calendar(freq: str, hour: int, minute: int = 0) -> dict:
    return {"daily": {"Hour": hour, "Minute": minute}, "weekly": {"Weekday": 1, "Hour": hour, "Minute": minute},
            "monthly": {"Day": 1, "Hour": hour, "Minute": minute}}[freq]


def _launchctl(*argv) -> int:
    if os.environ.get("GROUNDWORK_NO_LAUNCHCTL"):
        return 0
    try:
        return subprocess.run(["launchctl", *argv], capture_output=True, text=True, timeout=30).returncode
    except Exception:
        return 1


def _enabled(name: str, cfg: dict) -> bool:
    return bool(cfg.get("routines", {}).get(name, {}).get("enabled", False))


def build_command(name: str, dry_run: bool, repo: str, model: str, offline_work: str) -> tuple[list | None, str | None]:
    """Returns (cmd, blocked_reason). cmd is None when blocked_reason is set — the caller must
    not spawn `claude` at all in that case (owner requirement: BLOCKED means no subprocess)."""
    if name not in ROUTINES:
        raise ValueError(f"unknown routine: {name}")
    spec = ROUTINES[name]
    cfg = gcfg.load_config()
    rc = cfg.get("routines", {}).get(name, {})
    tools, blocked = _capabilities_for(name, cfg)
    if blocked:
        return None, blocked
    if spec.get("needs_offline_work"):
        prompt = spec["prompt"](rc, dry_run, offline_work)
    else:
        prompt = spec["prompt"](rc)
    cmd = ["claude", "-p", prompt, "--permission-mode", "dontAsk", "--permission-prompts", "none",
           "--allowedTools", " ".join(tools), "--model", model]
    return cmd, None


def run_routine(name: str, dry_run: bool = False, repo: str = ".", model: str = "sonnet",
                 timeout_s: int = DEFAULT_TIMEOUT_S, offline_work: str = "") -> dict:
    if os.environ.get("GROUNDWORK_ROUTINES", "").strip().lower() == "off":
        return {"routine": name, "status": "skipped", "reason": "GROUNDWORK_ROUTINES=off"}
    if os.environ.get(f"GROUNDWORK_ROUTINES_{name.upper()}", "").strip().lower() == "off":
        return {"routine": name, "status": "skipped", "reason": f"GROUNDWORK_ROUTINES_{name.upper()}=off"}
    spec = ROUTINES.get(name)
    if spec is None:
        return {"routine": name, "status": "failed", "reason": f"unknown routine: {name}"}
    cfg = gcfg.load_config()
    if not _enabled(name, cfg):
        result = {"routine": name, "mutates": spec["mutates"], "dry_run": dry_run, "status": "skipped",
                   "reason": "routine not enabled in config.json"}
        _record(result)
        return result
    started = time.time()
    cmd, blocked_reason = build_command(name, dry_run, repo, model, offline_work)
    result = {"routine": name, "mutates": spec["mutates"], "dry_run": dry_run, "started_at": int(started)}
    if blocked_reason:
        result["duration_s"] = 0.0
        result["status"] = "blocked"
        result["reason"] = blocked_reason
        _record(result)
        _store_result(name, "blocked", blocked_reason, "", dry_run, spec["mutates"])
        return result
    try:
        proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=timeout_s)
        result["duration_s"] = round(time.time() - started, 1)
        result["exit_code"] = proc.returncode
        summary = ""
        if proc.returncode != 0:
            result["status"] = "failed"
            result["reason"] = "claude -p exited non-zero"
            summary = result["reason"]
            content = proc.stdout or ""
        else:
            parsed = parse_routine_result(proc.stdout or "")
            status = parsed.get("status")
            if status:
                result["status"] = status
                summary = parsed.get("summary", "")
                content = (proc.stdout or "")[:parsed["block_start"]].strip()
            else:
                # A clean process exit with no parseable ROUTINE RESULT block is never silently
                # upgraded to COMPLETE (owner requirement §13) — it's a contract violation by the
                # routine's own output, treated as a failure of the run.
                result["status"] = "failed"
                result["reason"] = "missing or malformed ROUTINE RESULT block"
                summary = result["reason"]
                content = proc.stdout or ""
        result["output_chars"] = len(content)
        _store_result(name, result["status"], summary, content, dry_run, spec["mutates"])
    except subprocess.TimeoutExpired:
        result["duration_s"] = round(time.time() - started, 1)
        result["status"] = "failed"
        result["reason"] = f"timed out after {timeout_s}s"
    except FileNotFoundError:
        result["status"] = "failed"
        result["reason"] = "'claude' not on PATH"
    except Exception as e:  # fail-open: a routine crash is recorded, never raised into the scheduler
        result["status"] = "failed"
        result["reason"] = str(e)[:200]
    _record(result)
    return result


def schedule_routine(name: str, freq: str, hour: int = 8, minute: int = 0) -> dict:
    if name not in ROUTINES:
        raise ValueError(f"unknown routine: {name}")
    if not is_macos():
        return {"routine": name, "schedule": freq, "plist": None,
                "note": "launchd is macOS-only: invoke 'groundwork_routines.py run "
                        f"{name}' manually or from cron elsewhere"}
    domain = f"gui/{os.getuid()}"
    _launchctl("bootout", f"{domain}/{_label(name)}")
    p = _plist_path(name)
    if freq == "disabled":
        if p.exists():
            p.unlink()
        return {"routine": name, "schedule": "disabled", "plist": None}
    logs_dir = _config_dir() / "groundwork" / "reports" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        env["CLAUDE_CONFIG_DIR"] = os.environ["CLAUDE_CONFIG_DIR"]
    plist = {"Label": _label(name),
             "ProgramArguments": ["/usr/bin/env", "python3", str(Path(__file__).resolve()), "run", name],
             "StartCalendarInterval": _calendar(freq, hour, minute), "RunAtLoad": False,
             "StandardOutPath": str(logs_dir / f"routine-{name}.log"),
             "StandardErrorPath": str(logs_dir / f"routine-{name}.err"),
             "EnvironmentVariables": env, "ProcessType": "Background"}
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        plistlib.dump(plist, f)
    rc = _launchctl("bootstrap", domain, str(p))
    if rc != 0:
        _launchctl("load", "-w", str(p))
    return {"routine": name, "schedule": freq, "plist": str(p), "hour": hour, "minute": minute}


def _last_runs(limit_per_routine: int = 1) -> dict:
    path = _telemetry_path()
    out = {}
    if not path.exists():
        return out
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[-500:]:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if isinstance(rec, dict) and "routine" in rec:
                out[rec["routine"]] = rec
    except Exception:
        pass
    return out


def check_access(name: str, cfg: dict) -> dict:
    """Best-effort, safe, read-only CONFIGURED/AVAILABLE/CONNECTED checks (owner requirement §8-9)
    — never asserts CONNECTED without actually checking where that's safe to do; when it can't be
    checked safely from here, says so plainly rather than guessing."""
    rc = cfg.get("routines", {}).get(name, {})
    access = rc.get("access", "unconfigured")
    out = {"access": access, "available": None, "connected": None, "detail": ""}
    if access == "unconfigured":
        out["detail"] = "not configured"
        return out
    if access == "gh_cli":
        gh = shutil.which("gh")
        out["available"] = gh is not None
        if not gh:
            out["detail"] = "'gh' not found on PATH"
            return out
        try:
            r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=10)
            out["connected"] = r.returncode == 0
            out["detail"] = "authenticated" if out["connected"] else "not authenticated (run 'gh auth login')"
        except Exception:
            out["detail"] = "'gh auth status' could not be checked"
        return out
    if access in ("jira_mcp", "github_mcp"):
        claude = shutil.which("claude")
        if not claude:
            out["detail"] = "'claude' not found on PATH — cannot check MCP configuration"
            return out
        try:
            r = subprocess.run(["claude", "mcp", "list"], capture_output=True, text=True, timeout=15)
            server = (rc.get("mcp_server") or ("github" if access == "github_mcp" else "")).lower()
            out["available"] = bool(server) and server in (r.stdout or "").lower()
            out["detail"] = ("MCP server configured" if out["available"] else
                              "MCP server not found in 'claude mcp list' — connectivity itself not checked here")
        except Exception:
            out["detail"] = "'claude mcp list' could not be checked"
        return out
    if access == "cli":
        out["detail"] = "generic CLI access — not checked here (no universal command to probe)"
        return out
    if access == "browser":
        out["detail"] = "browser access — not checked here, verified at first live run"
        return out
    return out


def _cmd_run(args) -> int:
    result = run_routine(args.name, dry_run=args.dry_run, repo=args.repo, model=args.model,
                          timeout_s=args.timeout, offline_work=args.offline_work or "")
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") in ("complete", "skipped") else 1


def _cmd_schedule(args) -> int:
    print(json.dumps(schedule_routine(args.name, args.frequency, args.hour, args.minute), indent=2))
    return 0


def _cmd_list(_args) -> int:
    cfg = gcfg.load_config()
    last = _last_runs()
    for name, spec in ROUTINES.items():
        rc = cfg.get("routines", {}).get(name, {})
        enabled = rc.get("enabled", False)
        sched = rc.get("schedule", {})
        sched_txt = f"{sched.get('frequency', spec['default_schedule'])} {sched.get('time', '')}".strip()
        lr = last.get(name)
        lr_txt = f"last run: {lr.get('status')} ({lr.get('started_at')})" if lr else "never run"
        print(f"{name}: enabled={enabled} mutates={spec['mutates']} schedule={sched_txt} — {lr_txt}")
    return 0


def _cmd_latest(args) -> int:
    rec = latest_result(args.name)
    if rec is None:
        print(f"{args.name}: no result recorded yet")
        return 1
    print(f"{args.name} — {rec.get('status', 'unknown').upper()} ({rec.get('summary', '')})")
    print(f"started_at={rec.get('started_at')} dry_run={rec.get('dry_run')} mutates={rec.get('mutates')}")
    print("")
    print(rec.get("content", ""))
    return 0


ROUTINE_LABELS = {"jira_eod": "Jira EOD", "pr_followup": "PR Follow-up", "news": "News",
                  "weekly_status": "Weekly Status", "work_digest": "Work Digest", "doc_drift": "Doc Drift"}
ACCESS_LABELS = {"jira_mcp": "Jira MCP", "gh_cli": "gh CLI", "github_mcp": "GitHub MCP",
                 "cli": "CLI", "browser": "Browser", "unconfigured": "not configured"}


def _doctor_rows(cfg: dict | None = None) -> list:
    """Structured per-routine readiness data — the CONFIGURED/AVAILABLE/CONNECTED/VERIFIED
    distinctions (owner requirement §16), never exposing secrets (there are none in config.json
    to expose). Returns one dict per routine, in ROUTINES order; kept separate from `_cmd_doctor`'s
    own text formatting so tests can assert on structured fields directly, not printed strings."""
    cfg = cfg if cfg is not None else gcfg.load_config()
    last = _last_runs()
    rows = []
    for name, spec in ROUTINES.items():
        rc = cfg.get("routines", {}).get(name, {})
        enabled = rc.get("enabled", False)
        row = {"routine": name, "enabled": enabled, "mutates": spec["mutates"]}
        if not enabled:
            rows.append(row)
            continue
        access_info = check_access(name, cfg) if name in ("jira_eod", "pr_followup") else None
        sched = rc.get("schedule", {})
        row["schedule"] = f"{sched.get('frequency', spec['default_schedule'])} {sched.get('time', '')}".strip()
        if name == "jira_eod":
            row["site"] = rc.get("site", "")
            row["identity"] = rc.get("identity", "")
            row["scope"] = rc.get("scope", {}).get("type", "")
            row["posting"] = rc.get("posting", "dry_run")
        elif name == "pr_followup":
            row["identity"] = rc.get("identity", "")
            row["scope"] = ",".join(rc.get("scope", {}).get("repositories", []))
        elif name == "news":
            row["topics"] = rc.get("topics", [])
        if access_info:
            row["access"] = access_info["access"]
            row["available"] = access_info["available"]
            row["connected"] = access_info["connected"]
            row["access_detail"] = access_info["detail"]
        lr = last.get(name)
        row["last_run"] = lr.get("status") if lr else None
        rows.append(row)
    return rows


def _connectivity_label(row: dict) -> str:
    conn, avail = row.get("connected"), row.get("available")
    if conn is True:
        return "VERIFIED"
    if conn is False:
        return "BLOCKED (" + row.get("access_detail", "not authenticated") + ")"
    if avail is True:
        return "AVAILABLE (connectivity not checked here)"
    if avail is False:
        return "NOT AVAILABLE (" + row.get("access_detail", "") + ")"
    return "RUNTIME VALIDATION REQUIRED (" + row.get("access_detail", "not checked") + ")"


def format_doctor_text(rows: list) -> str:
    """Renders `_doctor_rows()` into the plain, indented text setup.sh's --doctor prints verbatim
    — all formatting lives here, in one testable place, rather than split across a bash re-parse."""
    lines = []
    for row in rows:
        name = row["routine"]
        lines.append(ROUTINE_LABELS.get(name, name))
        if not row.get("enabled"):
            lines.append("  Configuration ........ DISABLED")
            continue
        lines.append("  Configuration ........ PASS")
        if "site" in row:
            lines.append(f"  Jira site ............ {row['site'] or '(not set)'}")
            lines.append(f"  Identity ............. {'configured' if row.get('identity') else 'not configured'}")
        elif "identity" in row:
            lines.append(f"  Identity ............. {row['identity'] or 'not configured'}")
        if "access" in row:
            lines.append(f"  Access ............... {ACCESS_LABELS.get(row['access'], row['access'])}")
            lines.append(f"  Connectivity ......... {_connectivity_label(row)}")
        if "scope" in row:
            lines.append(f"  Scope ................ {row['scope'] or '(not set)'}")
        if "posting" in row:
            lines.append(f"  Posting .............. {row['posting']}")
        if "topics" in row:
            lines.append(f"  Topics ............... {', '.join(row['topics'])}")
        if "schedule" in row:
            lines.append(f"  Schedule ............. {row['schedule']}")
        lr = row.get("last_run")
        lines.append(f"  Last run ............. {lr.upper() if lr else 'never run'}")
    return "\n".join(lines)


def _cmd_doctor(_args) -> int:
    print(format_doctor_text(_doctor_rows()))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="run one routine now")
    p_run.add_argument("name", choices=sorted(ROUTINES))
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--repo", default=".")
    p_run.add_argument("--model", default=os.environ.get("GROUNDWORK_ROUTINES_MODEL", "sonnet"))
    p_run.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    p_run.add_argument("--offline-work", default="")
    p_sched = sub.add_parser("schedule", help="schedule a routine (macOS launchd; elsewhere prints the cron equivalent)")
    p_sched.add_argument("name", choices=sorted(ROUTINES))
    p_sched.add_argument("frequency", choices=["daily", "weekly", "monthly", "disabled"])
    p_sched.add_argument("--hour", type=int, default=8)
    p_sched.add_argument("--minute", type=int, default=0)
    sub.add_parser("list", help="list configured routines and last-run status")
    p_latest = sub.add_parser("latest", help="print the most recent stored result for a routine")
    p_latest.add_argument("name", choices=sorted(ROUTINES))
    sub.add_parser("doctor", help="print one JSON line per routine with readiness detail (for setup.sh --doctor)")
    args = ap.parse_args()
    return {"run": _cmd_run, "schedule": _cmd_schedule, "list": _cmd_list,
            "latest": _cmd_latest, "doctor": _cmd_doctor}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
