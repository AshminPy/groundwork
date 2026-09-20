#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash) — deny `git push` to protected branches and force-pushes.

Groundwork extension (not part of ECC). ECC 2.2.1 only *reminds* about pushes in its
`strict` profile; nothing blocks a direct push to main/master or a force-push. This hook
closes that gap with the smallest implementation that survives the bypasses an
independent security review reproduced against the 1.0.0 version:

  - it splits the command on shell separators (ignoring quoted strings), strips env
    assignments / sudo / command / env / nice wrappers, and recurses into
    `sh|bash|zsh|dash|ksh -c "<cmd>"` and `eval "<cmd>"` strings (depth-limited);
  - for every `git push` it finds it denies force flags, `--all` / `--mirror` /
    `--branches` (they push every branch, so no single safe target exists), and any
    refspec whose destination is protected — checking EVERY refspec, resolving `HEAD`
    / `@` / a bare push to the current branch, `src:dst` to `dst`, `:dst` (remote
    branch deletion) to `dst`, and stripping `+` and `refs/heads/`.

Known limits (deliberate — full shell parsing is out of scope): the protected set is an
exact, case-sensitive match (`main`, `master`, `production`, `prod`, `release`);
wrappers other than the shells above and `eval` (e.g. `xargs`, `python -c`, a script
file that itself pushes) are not parsed; quoted text such as `echo "git push origin
main"` is correctly NOT treated as a push. Every push still goes through Claude Code's
normal Bash permission model, which is the backstop for anything this parser cannot see.

Fail-open on any parse error — a broken guard must never become a session-wide bypass of
Claude's normal permission prompts.
"""
import json
import os
import re
import shlex
import subprocess
import sys

PROTECTED = {"main", "master", "production", "prod", "release"}
FORCE_FLAGS = {"--force", "-f", "--force-with-lease", "--force-if-includes"}
ALL_BRANCH_FLAGS = {"--all", "--mirror", "--branches"}
# push options that consume the next token when not written as --opt=value
VALUE_FLAGS = {"-o", "--push-option", "--receive-pack", "--exec", "--repo", "--recurse-submodules", "--signed"}
SEPARATORS = {"&&", "||", ";", "|", "&"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
WRAPPERS = {"sudo", "command", "env", "nice", "time"}
MAX_DEPTH = 3


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
    """Drop leading env assignments / sudo / command wrappers before the real command."""
    i = 0
    while i < len(seg) and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", seg[i]) or seg[i] in WRAPPERS):
        i += 1
    return seg[i:]


def current_branch(cwd: str):
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return (out.stdout.strip() or None) if out.returncode == 0 else None
    except Exception:
        return None


def push_positionals(push):
    """Positional args of `git push [opts] [remote] [refspec...]`, skipping option values."""
    args = []
    skip = False
    for tok in push[1:]:
        if skip:
            skip = False
            continue
        if tok.startswith("-"):
            if tok in VALUE_FLAGS:
                skip = True
            continue
        args.append(tok)
    return args


def target_branches(push, cwd):
    """Every destination branch a `git push` invocation would update (or delete)."""
    args = push_positionals(push)
    if len(args) < 2:
        return [current_branch(cwd)]  # bare `git push` or `git push <remote>`
    targets = []
    for refspec in args[1:]:
        refspec = refspec.lstrip("+")
        src, sep, dst = refspec.partition(":")
        name = dst if sep else src
        if name in ("", "HEAD", "@"):
            name = current_branch(cwd)
        if name:
            name = name.replace("refs/heads/", "")
        targets.append(name)
    return targets


def inspect_command(cmd: str, cwd: str, depth: int = 0):
    """Return a denial reason for the first violating `git push`, else None."""
    if depth > MAX_DEPTH:
        return None
    for seg in segments(cmd):
        seg = strip_wrappers(seg)
        if not seg:
            continue
        head = os.path.basename(seg[0])
        # Recurse into nested shells and eval so `bash -c "git push origin main"` is seen.
        if head in SHELLS and "-c" in seg:
            idx = seg.index("-c")
            if idx + 1 < len(seg):
                reason = inspect_command(seg[idx + 1], cwd, depth + 1)
                if reason:
                    return reason
            continue
        if head == "eval":
            reason = inspect_command(" ".join(seg[1:]), cwd, depth + 1)
            if reason:
                return reason
            continue
        if head != "git" or len(seg) < 2:
            continue
        j = 1  # skip global git options such as `-C <dir>` / `-c k=v`
        while j < len(seg) and seg[j].startswith("-"):
            j += 2 if seg[j] in ("-C", "-c") else 1
        if j >= len(seg) or seg[j] != "push":
            continue
        push = seg[j:]  # ["push", ...]
        if any(t in FORCE_FLAGS or t.startswith("--force") for t in push[1:]):
            return ("block_protected_push: force-push is not allowed from Claude. Push a normal commit, "
                    "or ask the user to force-push themselves.")
        if any(t in ALL_BRANCH_FLAGS for t in push[1:]):
            return ("block_protected_push: `git push --all/--mirror/--branches` pushes every branch, including "
                    "protected ones, so it is not allowed from Claude. Push one feature branch explicitly.")
        for target in target_branches(push, cwd):
            if target in PROTECTED:
                return (f"block_protected_push: direct push to protected branch '{target}' is not allowed "
                        "(branch → PR → merge). Push a feature branch and open a PR instead.")
    return None


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
    try:
        reason = inspect_command(cmd, cwd)
    except Exception:
        reason = None
    if reason:
        deny(reason)
    sys.exit(0)


if __name__ == "__main__":
    main()
