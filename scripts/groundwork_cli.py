#!/usr/bin/env python3
"""The `groundwork` command — a single, discoverable entry point that dispatches to Groundwork's
existing, already-tested functionality. It does not reimplement any logic: `doctor` shells out to
the installed copy of setup.sh's own `--doctor` mode so output is identical by construction, and
`version` reads the same `$CLAUDE_CONFIG_DIR/groundwork/VERSION` file `setup.sh --verify` reads.

Phase 1 of the Groundwork CLI (openspec/changes/groundwork-cli-foundation/): --help, version,
doctor only. Later phases add integrations/routines/update/rollback subtrees — this file's
dispatch table is where those get added, not a restructure.

Installed as `$CLAUDE_CONFIG_DIR/groundwork/bin/groundwork` (no .py extension, executable bit
set) by install.sh, and made reachable via PATH by the env-script mechanism install.sh also sets
up (see merge_settings.py-style additive/idempotent pattern — scripts/groundwork_cli.py itself
never touches PATH or shell rc files; that is install.sh's job).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
VERSION_PATH = CLAUDE_DIR / "groundwork" / "VERSION"
# The installed copy of setup.sh exists solely so `doctor` can invoke its --doctor mode with an
# identical, already-tested code path (DECISION 1: dispatch, never reimplement). Its --doctor/
# --verify modes are fully self-contained against $CLAUDE_DIR (confirmed by reading setup.sh
# directly: verify_install()/verify_capabilities() and everything they call resolve only
# $CLAUDE_DIR-relative paths, never $HERE-relative ones). Its --setup/--configure/--rollback/
# --uninstall modes DO depend on $HERE-relative files (install.sh, scripts/merge_settings.py)
# that are not copied alongside it, and are never invoked from this installed location — only
# --doctor is ever passed to it from here.
INSTALLED_SETUP_SH = CLAUDE_DIR / "groundwork" / "bin" / "setup.sh"


def _read_version() -> str | None:
    try:
        text = VERSION_PATH.read_text().strip()
        return text or None
    except OSError:
        return None


def cmd_version(_args) -> int:
    version = _read_version()
    if version is None:
        print(f"Groundwork version not found at {VERSION_PATH} — is Groundwork installed?", file=sys.stderr)
        return 1
    print(f"Groundwork {version}")
    return 0


def cmd_doctor(_args) -> int:
    if not INSTALLED_SETUP_SH.exists():
        print(f"doctor: {INSTALLED_SETUP_SH} not found — is Groundwork installed? "
              "(re-run install.sh, or run ./setup.sh --doctor directly from a repo clone)", file=sys.stderr)
        return 1
    result = subprocess.run(["bash", str(INSTALLED_SETUP_SH), "--doctor"])
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="groundwork",
        description="Groundwork — evidence-first governance layer for Claude Code. "
                     "This CLI dispatches to Groundwork's existing, already-tested functionality; "
                     "it does not reimplement it.",
    )
    sub = parser.add_subparsers(dest="command")
    p_version = sub.add_parser("version", help="print the installed Groundwork version")
    p_version.set_defaults(func=cmd_version)
    p_doctor = sub.add_parser("doctor", help="read-only health check (identical to ./setup.sh --doctor)")
    p_doctor.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
