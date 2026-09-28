#!/usr/bin/env python3
"""Groundwork 2.1 capability configuration — read/write/validate the one small, human-readable,
no-secrets config file setup.sh's optional capability-selection flow writes to.

Format is plain, pretty-printed JSON, not YAML: it matches every other Groundwork config file
(settings.json, report.json) and needs zero new parsing code, for a difference the brief itself
allows ("choose the actual format based on existing Groundwork conventions") — see design.md §G.

Routine configuration contract (owner requirement, added after the first RC): a routine is
configured ONCE — identity, scope, access mechanism, mutation permission, schedule — during
setup/configure, then runs automatically inside that saved scope. The user is never asked again
at runtime which Jira site, which GitHub user, which repositories, or which topics. See
docs/ROUTINES.md and design.md §D.2 for the full schema rationale.

Usage:
  groundwork_config.py show [--path FILE]                    print the effective config (defaults + saved)
  groundwork_config.py profiles                               list available profiles and what each recommends
  groundwork_config.py init PROFILE [--path FILE]              write PROFILE's defaults (does not overwrite an existing file)
  groundwork_config.py validate [--path FILE]                   exit 0 if the file is valid, else print problems and exit 1
  groundwork_config.py get ROUTINE KEY [--path FILE]             print one field (dotted path, e.g. scope.type); empty if unset
  groundwork_config.py set ROUTINE KEY=VALUE [KEY=VALUE ...]      merge one or more fields into a routine's config (dotted
                       [--path FILE]                              paths; JSON-parsed values, e.g. enabled=true, topics=["AI"])

Never stores credentials, tokens, or secrets — only capability names, booleans, identities
(usernames/emails, not passwords), scope descriptors, and schedule/topic strings.
"""
import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path

# Same CLAUDE_CONFIG_DIR resolution every other Groundwork script uses (groundwork_report.py,
# groundwork_routines.py, the hooks) — without it, a non-default CLAUDE_CONFIG_DIR (set by
# setup.sh's own tests, or by anyone running Groundwork out of a non-~/.claude config dir) would
# silently write/read config.json in the real ~/.claude instead of the target one.
DEFAULT_PATH = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")) / "groundwork" / "config.json"

# One entry per profile: which routines a fresh selection of that profile recommends *offering*
# during the wizard (§14 of the brief — only ask about a routine the profile or the user actually
# wants). Enabling a routine here does not by itself configure identity/scope/access; those are
# collected by the wizard right after, or the routine stays enabled-but-unconfigured (access:
# "unconfigured") until `--configure` revisits it — see BLOCKED in groundwork_routines.py.
PROFILES = {
    "sre-cloudops": {
        "cloud": ["gcp", "aws"],
        "platform": ["kubernetes", "terraform", "spacelift"],
        "integrations": ["github", "jira"],
        "skills": {"teaching": False, "task_observer": False, "security_review": True},
        "routines": {"jira_eod": True, "news": True, "weekly_status": True, "pr_followup": True,
                     "work_digest": True, "doc_drift": False},
    },
    "platform-engineering": {
        "cloud": ["gcp", "aws"],
        "platform": ["kubernetes", "terraform"],
        "integrations": ["github"],
        "skills": {"teaching": False, "task_observer": False, "security_review": True},
        "routines": {"jira_eod": False, "news": True, "weekly_status": True, "pr_followup": True,
                     "work_digest": True, "doc_drift": True},
    },
    "devops": {
        "cloud": [],
        "platform": ["kubernetes", "terraform"],
        "integrations": ["github"],
        "skills": {"teaching": False, "task_observer": False, "security_review": True},
        "routines": {"jira_eod": False, "news": True, "weekly_status": False, "pr_followup": True,
                     "work_digest": True, "doc_drift": False},
    },
    "software-engineering": {
        "cloud": [],
        "platform": [],
        "integrations": ["github"],
        "skills": {"teaching": True, "task_observer": False, "security_review": True},
        "routines": {"jira_eod": False, "news": True, "weekly_status": False, "pr_followup": True,
                     "work_digest": True, "doc_drift": False},
    },
    "cloud-architecture": {
        "cloud": ["gcp", "aws"],
        "platform": ["terraform"],
        "integrations": ["github", "jira", "confluence"],
        "skills": {"teaching": False, "task_observer": False, "security_review": True},
        "routines": {"jira_eod": True, "news": True, "weekly_status": True, "pr_followup": False,
                     "work_digest": False, "doc_drift": True},
    },
    "security-engineering": {
        "cloud": ["gcp", "aws"],
        "platform": ["kubernetes"],
        "integrations": ["github"],
        "skills": {"teaching": False, "task_observer": False, "security_review": True},
        "routines": {"jira_eod": False, "news": True, "weekly_status": False, "pr_followup": True,
                     "work_digest": False, "doc_drift": False},
    },
    "minimal": {
        "cloud": [], "platform": [], "integrations": [],
        "skills": {"teaching": False, "task_observer": False, "security_review": False},
        "routines": {"jira_eod": False, "news": False, "weekly_status": False, "pr_followup": False,
                     "work_digest": False, "doc_drift": False},
    },
    "custom": {
        "cloud": [], "platform": [], "integrations": [],
        "skills": {"teaching": False, "task_observer": False, "security_review": False},
        "routines": {"jira_eod": False, "news": False, "weekly_status": False, "pr_followup": False,
                     "work_digest": False, "doc_drift": False},
    },
}

KNOWN_CLOUD = {"gcp", "aws", "azure"}
KNOWN_PLATFORM = {"kubernetes", "terraform", "ansible", "spacelift"}
KNOWN_INTEGRATIONS = {"github", "jira", "confluence"}
KNOWN_ROUTINES = {"jira_eod", "news", "weekly_status", "pr_followup", "work_digest", "doc_drift"}
DEFAULT_NEWS_TOPICS = ["AI", "Claude", "Kubernetes", "AWS", "GCP"]

# Routine configuration contract (owner requirement): the closed sets every per-routine field is
# validated against. "unconfigured" is always a legitimate, explicit value for an access
# mechanism — it means "enabled, but the user chose 'configure later'" (see docs/ROUTINES.md);
# groundwork_routines.py treats it as BLOCKED, never as license to guess or fall back wider.
KNOWN_JIRA_ACCESS = {"jira_mcp", "cli", "browser", "unconfigured"}
KNOWN_JIRA_SCOPE_TYPES = {"assigned_to_me", "created_by_me", "projects", "custom_jql"}
KNOWN_JIRA_POSTING = {"dry_run", "automatic"}
KNOWN_GITHUB_ACCESS = {"gh_cli", "github_mcp", "unconfigured"}
KNOWN_SCHEDULE_FREQ = {"daily", "weekly", "monthly", "disabled"}
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _default_schedule(freq: str, time_: str = "08:00") -> dict:
    return {"frequency": freq, "time": time_}


def _default_jira_eod(enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "site": "",
        "identity": "",
        "access": "unconfigured",
        "scope": {"type": "assigned_to_me"},
        "posting": "dry_run",
        "schedule": _default_schedule("daily", "17:00"),
    }


def _default_pr_followup(enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "identity": "",
        "access": "unconfigured",
        "scope": {
            "repositories": ["current"],
            "authored_by_me": True,
            "requested_changes": True,
            "failing_ci": True,
            "merge_conflicts": True,
            "requires_action": True,
        },
        "schedule": _default_schedule("daily", "08:00"),
    }


def _default_news(enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "topics": list(DEFAULT_NEWS_TOPICS) if enabled else [],
        "schedule": _default_schedule("daily", "08:00"),
    }


def _default_weekly_status(enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "repository_scope": ["current"],
        "jira_projects": [],
        "github_scope": ["current"],
        "include_openspec": True,
        "period_days": 7,
        "schedule": _default_schedule("weekly", "08:00"),
    }


def _default_work_digest(enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "repository_scope": ["current"],
        "use_github": True,
        "use_jira": False,
        "include_openspec": True,
        "schedule": _default_schedule("daily", "08:00"),
    }


def _default_doc_drift(enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "repository": "current",
        "doc_paths": ["README.md", "docs/"],
        "impl_paths": [],
        "schedule": _default_schedule("weekly", "08:00"),
    }


_ROUTINE_DEFAULTS = {
    "jira_eod": _default_jira_eod,
    "pr_followup": _default_pr_followup,
    "news": _default_news,
    "weekly_status": _default_weekly_status,
    "work_digest": _default_work_digest,
    "doc_drift": _default_doc_drift,
}


def default_config(profile: str = "minimal") -> dict:
    base = copy.deepcopy(PROFILES.get(profile, PROFILES["minimal"]))
    cfg = {
        "profile": profile,
        "cloud": base["cloud"],
        "platform": base["platform"],
        "integrations": base["integrations"],
        "skills": base["skills"],
        "routines": {name: _ROUTINE_DEFAULTS[name](bool(base["routines"].get(name, False)))
                     for name in KNOWN_ROUTINES},
    }
    return cfg


def load_config(path: Path = DEFAULT_PATH) -> dict:
    """Returns the saved config, or a minimal-profile default if none exists yet. Never raises —
    an unreadable/corrupt file degrades to defaults (fail-open, matching every Groundwork hook)."""
    if not path.exists():
        return default_config("minimal")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default_config("minimal")
        return data
    except Exception:
        return default_config("minimal")


def save_config(cfg: dict, path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)
        f.write("\n")


def _validate_schedule(sched, where: str, problems: list) -> None:
    if not isinstance(sched, dict):
        problems.append(f"{where}.schedule must be an object with frequency/time")
        return
    freq = sched.get("frequency")
    if freq not in KNOWN_SCHEDULE_FREQ:
        problems.append(f"{where}.schedule.frequency: unknown value '{freq}' (known: {sorted(KNOWN_SCHEDULE_FREQ)})")
    time_ = sched.get("time")
    if freq != "disabled" and time_ is not None and not _TIME_RE.match(str(time_)):
        problems.append(f"{where}.schedule.time: '{time_}' is not HH:MM (24-hour)")


def _validate_routine(name: str, rc, problems: list) -> None:
    if not isinstance(rc, dict):
        problems.append(f"routines.{name} must be an object")
        return
    if "enabled" in rc and not isinstance(rc["enabled"], bool):
        problems.append(f"routines.{name}.enabled must be a boolean")
    if "schedule" in rc:
        _validate_schedule(rc["schedule"], f"routines.{name}", problems)
    if name == "jira_eod":
        access = rc.get("access")
        if access is not None and access not in KNOWN_JIRA_ACCESS:
            problems.append(f"routines.jira_eod.access: unknown value '{access}' (known: {sorted(KNOWN_JIRA_ACCESS)})")
        posting = rc.get("posting")
        if posting is not None and posting not in KNOWN_JIRA_POSTING:
            problems.append(f"routines.jira_eod.posting: unknown value '{posting}' (known: {sorted(KNOWN_JIRA_POSTING)})")
        scope = rc.get("scope")
        if scope is not None:
            if not isinstance(scope, dict):
                problems.append("routines.jira_eod.scope must be an object")
            elif scope.get("type") is not None and scope.get("type") not in KNOWN_JIRA_SCOPE_TYPES:
                problems.append(f"routines.jira_eod.scope.type: unknown value '{scope.get('type')}' (known: {sorted(KNOWN_JIRA_SCOPE_TYPES)})")
    elif name == "pr_followup":
        access = rc.get("access")
        if access is not None and access not in KNOWN_GITHUB_ACCESS:
            problems.append(f"routines.pr_followup.access: unknown value '{access}' (known: {sorted(KNOWN_GITHUB_ACCESS)})")
        scope = rc.get("scope")
        if scope is not None and not isinstance(scope, dict):
            problems.append("routines.pr_followup.scope must be an object")
    elif name == "news":
        topics = rc.get("topics")
        if topics is not None and (not isinstance(topics, list) or not all(isinstance(t, str) for t in topics)):
            problems.append("routines.news.topics must be a list of strings")


def validate_config(cfg: dict) -> list[str]:
    """Returns a list of problems (empty = valid). Unknown capability names/values are reported,
    not silently dropped — a typo in a hand-edited config should be visible, not swallowed."""
    problems = []
    if not isinstance(cfg, dict):
        return ["config is not a JSON object"]
    for key, known in (("cloud", KNOWN_CLOUD), ("platform", KNOWN_PLATFORM), ("integrations", KNOWN_INTEGRATIONS)):
        vals = cfg.get(key, [])
        if not isinstance(vals, list):
            problems.append(f"{key} must be a list")
            continue
        for v in vals:
            if v not in known:
                problems.append(f"{key}: unknown value '{v}' (known: {sorted(known)})")
    routines = cfg.get("routines", {})
    if not isinstance(routines, dict):
        problems.append("routines must be an object")
    else:
        for name, rc in routines.items():
            if name not in KNOWN_ROUTINES:
                problems.append(f"routines: unknown routine '{name}' (known: {sorted(KNOWN_ROUTINES)})")
                continue
            _validate_routine(name, rc, problems)
    for secret_word in ("token", "password", "secret", "api_key", "apikey", "credential", "cookie"):
        if secret_word in json.dumps(cfg).lower():
            problems.append(f"config appears to contain a '{secret_word}'-like key — never store credentials here")
    return problems


def _parse_value(raw: str):
    """KEY=VALUE values are JSON when they parse as JSON (true/false/123/["a","b"]/{"x":1}),
    else treated as a plain string — so `enabled=true` and `identity=jane@company.com` both
    do the intuitive thing without the caller needing to know JSON quoting rules for strings."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


def _set_dotted(d: dict, dotted_key: str, value) -> None:
    parts = dotted_key.split(".")
    cur = d
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _get_dotted(d: dict, dotted_key: str):
    cur = d
    for p in dotted_key.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def _cmd_show(args) -> int:
    print(json.dumps(load_config(Path(args.path)), indent=2, sort_keys=True))
    return 0


def _cmd_profiles(_args) -> int:
    for name, p in PROFILES.items():
        print(f"{name}: cloud={p['cloud']} platform={p['platform']} integrations={p['integrations']}")
    return 0


def _cmd_init(args) -> int:
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"{path} already exists — not overwriting (pass --force to replace)", file=sys.stderr)
        return 1
    if args.profile not in PROFILES:
        print(f"unknown profile '{args.profile}' — choices: {sorted(PROFILES)}", file=sys.stderr)
        return 1
    save_config(default_config(args.profile), path)
    print(f"wrote {path} (profile: {args.profile})")
    return 0


def _cmd_validate(args) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"{path} does not exist (this is fine — Groundwork falls back to the minimal profile)")
        return 0
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"invalid JSON: {e}", file=sys.stderr)
        return 1
    problems = validate_config(cfg)
    if problems:
        for p in problems:
            print(f"- {p}", file=sys.stderr)
        return 1
    print("valid")
    return 0


def _cmd_get(args) -> int:
    cfg = load_config(Path(args.path))
    rc = cfg.get("routines", {}).get(args.routine, {})
    val = _get_dotted(rc, args.key)
    if val is None:
        print("")
        return 0
    print(val if isinstance(val, str) else json.dumps(val))
    return 0


def _cmd_set(args) -> int:
    if args.routine not in KNOWN_ROUTINES:
        print(f"unknown routine '{args.routine}' (known: {sorted(KNOWN_ROUTINES)})", file=sys.stderr)
        return 1
    path = Path(args.path)
    cfg = load_config(path)
    cfg.setdefault("routines", {})
    if args.routine not in cfg["routines"] or not isinstance(cfg["routines"][args.routine], dict):
        cfg["routines"][args.routine] = _ROUTINE_DEFAULTS[args.routine](False)
    rc = cfg["routines"][args.routine]
    for kv in args.assignments:
        if "=" not in kv:
            print(f"expected KEY=VALUE, got '{kv}'", file=sys.stderr)
            return 1
        key, raw = kv.split("=", 1)
        _set_dotted(rc, key, _parse_value(raw))
    problems = validate_config(cfg)
    if problems:
        for p in problems:
            print(f"- {p}", file=sys.stderr)
        return 1
    save_config(cfg, path)
    print(f"updated routines.{args.routine} in {path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_show = sub.add_parser("show", help="print the effective config")
    p_show.add_argument("--path", default=str(DEFAULT_PATH))
    sub.add_parser("profiles", help="list available profiles")
    p_init = sub.add_parser("init", help="write a profile's defaults")
    p_init.add_argument("profile")
    p_init.add_argument("--path", default=str(DEFAULT_PATH))
    p_init.add_argument("--force", action="store_true")
    p_val = sub.add_parser("validate", help="validate the config file")
    p_val.add_argument("--path", default=str(DEFAULT_PATH))
    p_get = sub.add_parser("get", help="print one routine field (dotted path)")
    p_get.add_argument("routine")
    p_get.add_argument("key")
    p_get.add_argument("--path", default=str(DEFAULT_PATH))
    p_set = sub.add_parser("set", help="merge one or more KEY=VALUE fields into a routine's config")
    p_set.add_argument("routine")
    p_set.add_argument("assignments", nargs="+", metavar="KEY=VALUE")
    p_set.add_argument("--path", default=str(DEFAULT_PATH))
    args = ap.parse_args()
    return {"show": _cmd_show, "profiles": _cmd_profiles, "init": _cmd_init,
            "validate": _cmd_validate, "get": _cmd_get, "set": _cmd_set}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
