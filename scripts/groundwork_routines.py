#!/usr/bin/env python3
"""Groundwork 2.1 Routines — recurring/scheduled automation, distinct from a Playbook (task-routing.md §4).

Each routine is a name + a prompt template + a mutates flag + a default schedule: one generic
framework, not six bespoke scripts. A scheduled run invokes a real, separate, non-interactive
`claude -p` session per routine (never the interactive session's own context — routines are
isolated by construction, docs/CONTEXT-ENGINEERING.md).

Safe unattended invocation (confirmed live against code.claude.com, 2026-09-28 — see design.md §C):
NEVER --dangerously-skip-permissions (restricted to containers/VMs, refused under root/sudo).
NEVER --bare (would skip Groundwork's own hooks/skills/MCP config that routines should inherit).
Uses --permission-mode dontAsk + --permission-prompts none + an explicit --allowedTools allowlist:
anything not pre-configured is safely denied, not guessed at — an under-configured environment
fails closed (BLOCKED/PARTIAL), never fabricates success.

Scheduling extends the exact pattern already proven for the health dashboard
(groundwork_report.py's launchd-on-macOS/cron-elsewhere scheduler) — no new scheduler.

Disable a specific routine with GROUNDWORK_ROUTINES_<NAME>=off. Disable the whole subsystem with
GROUNDWORK_ROUTINES=off. Path override: GROUNDWORK_ROUTINES_TELEMETRY_PATH.
"""
import argparse
import json
import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import groundwork_config as gcfg  # noqa: E402

LABEL_PREFIX = "com.groundwork.routine"
DEFAULT_TIMEOUT_S = 600
READ_ONLY_TOOLS = "Bash(git *) Read Grep Glob WebSearch WebFetch"
JIRA_LIVE_TOOLS = READ_ONLY_TOOLS  # Jira write access, if configured, is whatever MCP/CLI the user
# already set up and already allowed in their own settings — Routines never widen it; an
# unconfigured Jira write path is denied by --permission-mode dontAsk, not worked around here.


def _telemetry_path() -> Path:
    override = os.environ.get("GROUNDWORK_ROUTINES_TELEMETRY_PATH")
    if override:
        return Path(override)
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    return base / "groundwork" / "telemetry" / "routines.jsonl"


def _record(event: dict) -> None:
    """Append one JSON line, owner-only, fail-open — mirrors hooks/groundwork_telemetry.py's own
    pattern exactly (same directory, same 0600 permissions, same append-only discipline; a
    sibling file because a routine run is not a Claude Code hook Stop event, so it has no
    transcript to parse the same way — see design.md §D)."""
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


def _jira_eod_prompt(topics: list, dry_run: bool, offline_work: str) -> str:
    dry_run_line = (
        "This is a DRY RUN: draft the exact Jira comment(s) you would post, and print each one "
        "clearly labeled with its ticket key, but do NOT call any tool that would actually write "
        "to Jira. End with 'DRY RUN — nothing was posted.'"
        if dry_run else
        "This is a LIVE run: after drafting each comment, post it via whatever Jira write "
        "mechanism (MCP or CLI) is already configured and already permitted — if none is "
        "available or permitted, say so plainly and report that ticket BLOCKED rather than "
        "inventing a post. After posting, read the ticket/comment back to confirm it actually "
        "landed before reporting it VERIFIED — a successful tool call is not evidence of a "
        "successful mutation."
    )
    offline_block = (
        f"\n\nThe user separately reported this work, which may not be visible in git/PR/OpenSpec "
        f"evidence — fold it into the relevant ticket's update, rewritten concisely and "
        f"professionally, only if it's genuinely relevant:\n{offline_work}\n"
        if offline_work else ""
    )
    return f"""You are running Groundwork's Jira end-of-day routine, a scheduled Routine (not an interactive session) — see rules/task-routing.md's Playbook/Routine distinction and engineering-workflow.md's evidence and completion rules, which still apply.

Goal: review today's engineering work in the current repository and prepare a factual, concise Jira ticket update for each ticket that had real, evidenced work today.

Evidence sources, in order: git log/diff for commits made today, open/updated PRs, OpenSpec task-checkbox changes, the investigation-continuity file for this repo if one exists, test results, review outcomes, deployment/runtime validation actually observed today. Never invent work: if evidence suggests work happened but you cannot determine which ticket it belongs to, say so explicitly as a blocker rather than guessing a ticket key.

For each ticket with real evidenced work, draft a comment covering only what's relevant and actually true: work completed, evidence/validation (command + result, not just "tests pass"), blockers, remaining work, next action. Never claim deployment or live/runtime validation without direct evidence you observed yourself today. Keep it concise and professional — this is read by humans, not a raw evidence dump.
{offline_block}
{dry_run_line}

If no ticket had meaningful evidenced work today, say so plainly and do not post or draft anything — avoid comments when nothing meaningful changed."""


def _news_prompt(topics: list) -> str:
    topic_list = ", ".join(topics) if topics else "AI, Claude, agentic AI, cybersecurity, SRE"
    return f"""You are running Groundwork's daily technical-news routine, a scheduled Routine (not an interactive session).

Topics: {topic_list}.

Research current news for these topics using authoritative, reputable sources only (official vendor blogs/docs, established technical press — not random forum posts). Deduplicate across sources. Filter for genuine materiality — skip routine/minor updates. For each item worth including: a concise summary, the source link, and why it matters when that's not obvious.

If nothing material happened across these topics since the last run, say so plainly in one line — do not manufacture filler content to make the digest look substantial. Do not store or reproduce full article bodies, only your own summary plus the source link."""


def _weekly_status_prompt(_topics: list) -> str:
    return """You are running Groundwork's weekly status routine, a scheduled Routine (not an interactive session).

Using engineering-workflow.md §3's own completion-facts model (code written, tests run, independent review, merged, deployed, live validated — plus completed/in-progress/blocked), summarize this repository's status over the past week from real evidence: git history, PR state, OpenSpec task progress, test results, review outcomes, deployment/runtime validation actually observed.

Cover: completed, in progress, blocked, decisions made, next actions. Do not invent status for anything you lack evidence for — state it as unknown rather than guessing. Merged is not deployed; deployed is not runtime-validated; keep those distinctions exact."""


def _pr_followup_prompt(_topics: list) -> str:
    return """You are running Groundwork's PR/review follow-up routine, a scheduled Routine (not an interactive session).

Using `gh pr list`/`gh pr view`/`gh pr checks` (or the repository's own equivalent), identify: PRs awaiting review, PRs with requested changes, PRs with failing CI, stale branches, PRs with merge conflicts, and work that is complete but not yet merged. Report each with the evidence (exact command + result), not a guess.

MERGED IS NOT DEPLOYED — only report something as deployed if you have direct evidence of a deployment, never inferred from a merge alone. If nothing needs attention, say so plainly."""


def _work_digest_prompt(_topics: list) -> str:
    return """You are running Groundwork's daily work/TODO digest routine, a scheduled Routine (not an interactive session).

From real evidence only — git branches and dirty work, open PRs, OpenSpec task state, the investigation-continuity file if one exists, failed validation, pending review, blocked deployments — produce three short sections: TODAY (concrete next actions with real evidence behind them), BLOCKED (what's blocking, and on what), FOLLOW-UP (loose ends worth revisiting).

Do not create a task from a weak or ambiguous signal — a real task needs real evidence, not a guess dressed up as one."""


def _doc_drift_prompt(_topics: list) -> str:
    return """You are running Groundwork's documentation-drift routine, a scheduled Routine (not an interactive session).

Compare the actual current implementation (code, configuration, tests, CI) against README.md, architecture docs, runbooks, and OpenSpec artifacts in this repository. Report only meaningful drift — a documented claim that no longer matches what the code does, a missing capability that's documented as shipped, or vice versa.

Do NOT rewrite documentation yourself in this routine — report the drift found, with the exact file/line and the exact mismatch, for a human or a follow-up session to fix. A routine that silently rewrites documentation on a schedule is exactly the kind of unreviewed automation Groundwork's evidence discipline exists to prevent."""


ROUTINES = {
    "jira_eod": {"mutates": True, "default_schedule": "daily", "prompt": _jira_eod_prompt, "needs_offline_work": True},
    "news": {"mutates": False, "default_schedule": "daily", "prompt": _news_prompt, "needs_offline_work": False},
    "weekly_status": {"mutates": False, "default_schedule": "weekly", "prompt": _weekly_status_prompt, "needs_offline_work": False},
    "pr_followup": {"mutates": False, "default_schedule": "daily", "prompt": _pr_followup_prompt, "needs_offline_work": False},
    "work_digest": {"mutates": False, "default_schedule": "daily", "prompt": _work_digest_prompt, "needs_offline_work": False},
    "doc_drift": {"mutates": False, "default_schedule": "weekly", "prompt": _doc_drift_prompt, "needs_offline_work": False},
}


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


def _calendar(freq: str, hour: int) -> dict:
    return {"daily": {"Hour": hour, "Minute": 0}, "weekly": {"Weekday": 1, "Hour": hour, "Minute": 0},
            "monthly": {"Day": 1, "Hour": hour, "Minute": 0}}[freq]


def _launchctl(*argv) -> int:
    if os.environ.get("GROUNDWORK_NO_LAUNCHCTL"):
        return 0
    try:
        return subprocess.run(["launchctl", *argv], capture_output=True, text=True, timeout=30).returncode
    except Exception:
        return 1


def build_command(name: str, dry_run: bool, repo: str, model: str, offline_work: str) -> list:
    if name not in ROUTINES:
        raise ValueError(f"unknown routine: {name}")
    spec = ROUTINES[name]
    cfg = gcfg.load_config()
    routine_cfg = cfg.get("routines", {}).get(name, {})
    topics = routine_cfg.get("topics", []) if name == "news" else []
    if spec.get("needs_offline_work"):
        prompt = spec["prompt"](topics, dry_run, offline_work)
    else:
        prompt = spec["prompt"](topics)
    allowed = JIRA_LIVE_TOOLS if (name == "jira_eod" and not dry_run) else READ_ONLY_TOOLS
    cmd = ["claude", "-p", prompt, "--permission-mode", "dontAsk", "--permission-prompts", "none",
           "--allowedTools", allowed, "--model", model]
    return cmd


def run_routine(name: str, dry_run: bool = False, repo: str = ".", model: str = "sonnet",
                 timeout_s: int = DEFAULT_TIMEOUT_S, offline_work: str = "") -> dict:
    if os.environ.get("GROUNDWORK_ROUTINES", "").strip().lower() == "off":
        return {"routine": name, "status": "skipped", "reason": "GROUNDWORK_ROUTINES=off"}
    if os.environ.get(f"GROUNDWORK_ROUTINES_{name.upper()}", "").strip().lower() == "off":
        return {"routine": name, "status": "skipped", "reason": f"GROUNDWORK_ROUTINES_{name.upper()}=off"}
    spec = ROUTINES.get(name)
    if spec is None:
        return {"routine": name, "status": "failed", "reason": f"unknown routine: {name}"}
    started = time.time()
    cmd = build_command(name, dry_run, repo, model, offline_work)
    result = {"routine": name, "mutates": spec["mutates"], "dry_run": dry_run, "started_at": int(started)}
    try:
        proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=timeout_s)
        result["duration_s"] = round(time.time() - started, 1)
        result["exit_code"] = proc.returncode
        result["status"] = "complete" if proc.returncode == 0 else "failed"
        result["output_chars"] = len(proc.stdout or "")
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


def schedule_routine(name: str, freq: str, hour: int = 8) -> dict:
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
    logs_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")) / "groundwork" / "reports" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        env["CLAUDE_CONFIG_DIR"] = os.environ["CLAUDE_CONFIG_DIR"]
    plist = {"Label": _label(name),
             "ProgramArguments": ["/usr/bin/env", "python3", str(Path(__file__).resolve()), "run", name],
             "StartCalendarInterval": _calendar(freq, hour), "RunAtLoad": False,
             "StandardOutPath": str(logs_dir / f"routine-{name}.log"),
             "StandardErrorPath": str(logs_dir / f"routine-{name}.err"),
             "EnvironmentVariables": env, "ProcessType": "Background"}
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        plistlib.dump(plist, f)
    rc = _launchctl("bootstrap", domain, str(p))
    if rc != 0:
        _launchctl("load", "-w", str(p))
    return {"routine": name, "schedule": freq, "plist": str(p), "hour": hour}


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


def _cmd_run(args) -> int:
    result = run_routine(args.name, dry_run=args.dry_run, repo=args.repo, model=args.model,
                          timeout_s=args.timeout, offline_work=args.offline_work or "")
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") in ("complete", "skipped") else 1


def _cmd_schedule(args) -> int:
    print(json.dumps(schedule_routine(args.name, args.frequency, args.hour), indent=2))
    return 0


def _cmd_list(_args) -> int:
    cfg = gcfg.load_config()
    last = _last_runs()
    for name, spec in ROUTINES.items():
        rc = cfg.get("routines", {}).get(name, {})
        enabled = rc.get("enabled", False)
        lr = last.get(name)
        lr_txt = f"last run: {lr.get('status')} ({lr.get('started_at')})" if lr else "never run"
        print(f"{name}: enabled={enabled} mutates={spec['mutates']} schedule={rc.get('schedule', spec['default_schedule'])} — {lr_txt}")
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
    sub.add_parser("list", help="list configured routines and last-run status")
    args = ap.parse_args()
    return {"run": _cmd_run, "schedule": _cmd_schedule, "list": _cmd_list}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
