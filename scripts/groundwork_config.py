#!/usr/bin/env python3
"""Groundwork 2.1 capability configuration — read/write/validate the one small, human-readable,
no-secrets config file setup.sh's optional capability-selection flow writes to.

Format is plain, pretty-printed JSON, not YAML: it matches every other Groundwork config file
(settings.json, report.json) and needs zero new parsing code, for a difference the brief itself
allows ("choose the actual format based on existing Groundwork conventions") — see design.md §G.

Usage:
  groundwork_config.py show [--path FILE]                 print the effective config (defaults + saved)
  groundwork_config.py profiles                            list available profiles and what each recommends
  groundwork_config.py init PROFILE [--path FILE]           write PROFILE's defaults (does not overwrite an existing file)
  groundwork_config.py validate [--path FILE]                exit 0 if the file is valid, else print problems and exit 1

Never stores credentials, tokens, or secrets — only capability names, booleans, and schedule/topic strings.
"""
import argparse
import copy
import json
import os
import sys
from pathlib import Path

# Same CLAUDE_CONFIG_DIR resolution every other Groundwork script uses (groundwork_report.py,
# groundwork_routines.py, the hooks) — without it, a non-default CLAUDE_CONFIG_DIR (set by
# setup.sh's own tests, or by anyone running Groundwork out of a non-~/.claude config dir) would
# silently write/read config.json in the real ~/.claude instead of the target one.
DEFAULT_PATH = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")) / "groundwork" / "config.json"

# One entry per profile: what a fresh selection of that profile pre-fills. The interactive flow
# in setup.sh lets the user change any of it — a profile is a recommendation, never a forced install.
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


def default_config(profile: str = "minimal") -> dict:
    base = copy.deepcopy(PROFILES.get(profile, PROFILES["minimal"]))
    cfg = {
        "profile": profile,
        "cloud": base["cloud"],
        "platform": base["platform"],
        "integrations": base["integrations"],
        "skills": base["skills"],
        "routines": {name: {"enabled": bool(base["routines"].get(name, False))} for name in KNOWN_ROUTINES},
    }
    if cfg["routines"]["news"]["enabled"]:
        cfg["routines"]["news"]["topics"] = list(DEFAULT_NEWS_TOPICS)
    else:
        cfg["routines"]["news"]["topics"] = []
    cfg["routines"]["jira_eod"]["schedule"] = "daily"
    cfg["routines"]["news"]["schedule"] = "daily"
    cfg["routines"]["weekly_status"]["schedule"] = "weekly"
    cfg["routines"]["pr_followup"]["schedule"] = "daily"
    cfg["routines"]["work_digest"]["schedule"] = "daily"
    cfg["routines"]["doc_drift"]["schedule"] = "weekly"
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


def validate_config(cfg: dict) -> list[str]:
    """Returns a list of problems (empty = valid). Unknown capability names are reported, not
    silently dropped — a typo in a hand-edited config should be visible, not swallowed."""
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
        for name in routines:
            if name not in KNOWN_ROUTINES:
                problems.append(f"routines: unknown routine '{name}' (known: {sorted(KNOWN_ROUTINES)})")
    for secret_word in ("token", "password", "secret", "api_key", "apikey", "credential"):
        if secret_word in json.dumps(cfg).lower():
            problems.append(f"config appears to contain a '{secret_word}'-like key — never store credentials here")
    return problems


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
    args = ap.parse_args()
    return {"show": _cmd_show, "profiles": _cmd_profiles, "init": _cmd_init,
            "validate": _cmd_validate}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
