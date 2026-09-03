#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash) — deny `git push` to protected branches and force-pushes.

Custom harness extension (not part of ECC). ECC 2.2.1 only *reminds* about pushes in its
`strict` profile; nothing blocks a direct push to main/master or a force-push. This hook
closes that gap with the smallest possible implementation: it only looks at real `git push`
invocations (split on shell separators, ignoring quoted strings), resolves the target branch
(explicit refspec, else the current branch), and denies protected targets and force flags.

Fail-open on any parse error — a broken guard must never become a session-wide bypass of
Claude's normal permission prompts, and every push still goes through the normal permission
model anyway.
"""
import json
import os
import re
import shlex
import subprocess
import sys

PROTECTED = {"main", "master", "production", "prod", "release"}
FORCE_FLAGS = {"--force", "-f", "--force-with-lease", "--force-if-includes"}
SEPARATORS = {"&&", "||", ";", "|", "&"}


def segments(cmd: str):
    """Yield token lists for each simple command in a shell chain."""
    try:
        tokens = shlex.split(cmd, posix=True)
    except ValueError:
        return
    seg = []
    for tok in tokens:
        if tok in SEPARATORS:
            if seg:
                yield seg
            seg = []
        else:
            seg.append(tok)
    if seg:
        yield seg


def strip_wrappers(seg):
    """Drop leading env assignments / sudo / command wrappers before `git`."""
    i = 0
    while i < len(seg) and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", seg[i]) or seg[i] in ("sudo", "command", "env", "nice")):
        i += 1
    return seg[i:]


def current_branch(cwd: str):
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return (out.stdout.strip() or None) if out.returncode == 0 else None
    except Exception:
        return None


def target_branch(seg, cwd):
    """`git push [opts] [remote] [refspec]` → destination branch name or None."""
    args = [t for t in seg[1:] if not t.startswith("-")]
    if len(args) >= 2:
        refspec = args[1]
        if ":" in refspec:
            refspec = refspec.split(":", 1)[1]
        refspec = refspec.lstrip("+")
        return refspec.replace("refs/heads/", "") or None
    return current_branch(cwd)


def deny(reason: str):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))
    sys.exit(0)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    cwd = data.get("cwd") or os.getcwd()
    for seg in segments(cmd):
        seg = strip_wrappers(seg)
        if len(seg) < 2 or seg[0] != "git":
            continue
        j = 1  # skip global git options such as `-C <dir>` / `-c k=v`
        while j < len(seg) and seg[j].startswith("-"):
            j += 2 if seg[j] in ("-C", "-c") else 1
        if j >= len(seg) or seg[j] != "push":
            continue
        push = seg[j:]  # ["push", ...]
        if any(t in FORCE_FLAGS or t.startswith("--force") for t in push[1:]):
            deny("block_protected_push: force-push is not allowed from Claude. Push a normal commit, "
                 "or ask the user to force-push themselves.")
        target = target_branch(push, cwd)
        if target in PROTECTED:
            deny(f"block_protected_push: direct push to protected branch '{target}' is not allowed "
                 "(branch → PR → merge). Push a feature branch and open a PR instead.")
    sys.exit(0)


if __name__ == "__main__":
    main()
