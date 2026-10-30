"""`gw doctor`: report-only checks, each problem with the exact command that fixes it (release-gating spec). Later
task groups register more checks with `@check`."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Callable

from . import profile as prof
from .util import PLUGIN_ROOT

CHECKS: list[Callable] = []
SEMVER = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")
TMPDIR_MAX = 60   # phase0-results 1.7: a long TMPDIR stopped the sandbox from starting


def check(fn: Callable) -> Callable:
    CHECKS.append(fn)
    return fn


@check
def plugin_version(ctx: dict) -> list[tuple[str, str]]:
    manifest = json.loads((ctx["root"] / ".claude-plugin" / "plugin.json").read_text())
    v = manifest.get("version", "")
    if not SEMVER.match(v):
        return [(f"plugin version {v!r} is not semver", "set `version` in .claude-plugin/plugin.json, e.g. 3.0.0")]
    return []


@check
def openspec_cli(ctx: dict) -> list[tuple[str, str]]:
    pinned = tomllib.loads((ctx["root"] / "toolchain" / "versions.toml").read_text())["openspec"]
    try:
        r = subprocess.run(["openspec", "--version"], capture_output=True, text=True, timeout=20)
        found = r.stdout.strip().splitlines()[-1] if r.returncode == 0 and r.stdout.strip() else None
    except (OSError, subprocess.SubprocessError):
        found = None
    if found is None:
        return [("OpenSpec CLI not found", f"npm install --prefix ~/.local @fission-ai/openspec@{pinned}")]
    if found != pinned:
        return [(f"OpenSpec CLI is {found}, pinned {pinned}",
                 f"npm install --prefix ~/.local @fission-ai/openspec@{pinned}")]
    return []


@check
def profile_drift(ctx: dict) -> list[tuple[str, str]]:
    out = []
    for name in prof.PROFILES:
        keys = prof.check_drift(name, ctx.get("config_dirs", {}).get(name), ctx["root"])
        for k in keys or []:
            out.append((f"profile {name}: {k} differs from the applied profile", f"gw profile apply {name}"))
    return out


@check
def tmpdir_length(ctx: dict) -> list[tuple[str, str]]:
    t = ctx.get("env", os.environ).get("TMPDIR", "")
    if len(t) > TMPDIR_MAX:
        return [(f"TMPDIR is {len(t)} characters; the Bash sandbox may fail to start",
                 "export TMPDIR=/tmp before starting claude")]
    return []


def run(ctx: dict | None = None, out=sys.stdout) -> int:
    ctx = {"root": PLUGIN_ROOT, **(ctx or {})}
    problems = []
    for fn in CHECKS:
        try:
            problems += fn(ctx)
        except Exception as e:   # a broken check is itself a problem, never a crash
            problems.append((f"check {fn.__name__} failed: {e}", "report this as a Groundwork bug"))
    for msg, fix in problems:
        print(f"PROBLEM  {msg}\n  fix:   {fix}", file=out)
    print(f"{len(problems)} problem(s) found." if problems else "No problems found.", file=out)
    return 1 if problems else 0
