#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash) — deny `git push` to protected branches and force-pushes.

Groundwork extension (not part of ECC). ECC 2.2.1 only *reminds* about pushes in its
`strict` profile; nothing blocks a direct push to main/master or a force-push. This hook
closes that gap with the smallest implementation that survives the bypasses independent
security reviews reproduced against earlier versions:

  - it splits the command on every shell separator bash uses — `;`, `&&`, `||`, `|`, `&`,
    newlines, `(`, `)`, backticks, also when they touch a word (`a;git push`, `true&&git push`)
    — ignoring quoted text, and removes comments only where bash starts one (a `#` at the start
    of a word); redirections and their targets are dropped;
  - it finds a `git … push` anywhere in each command, so leading wrappers (`sudo -u x`,
    `timeout 5`, `nohup`, `{`, `if … then`, env assignments) cannot hide it, and recurses into
    `sh|bash|zsh|dash|ksh -c "<cmd>"` (also clustered flags such as `-lc`, `-ec`) and
    `eval "<cmd>"` strings (depth-limited);
  - for every `git push` it denies force flags (`--force*`, `-f`, and any short-flag cluster
    with an `f`, such as `-uf`), `--all` / `--mirror` / `--branches` (they push every branch,
    so no single safe target exists), and any refspec whose destination is protected —
    checking EVERY refspec, resolving `HEAD` / `@` / a bare push to the current branch,
    `src:dst` to `dst`, `:dst` (remote branch deletion) to `dst`, and stripping `+` and
    `refs/heads/`;
  - the current branch is checked in every directory the push may run in: the session's
    directory, each `cd`/`pushd` target earlier in the command, and `git -C <dir>`. A directory
    it cannot determine (`cd "$X"`) denies a push that depends on it.

Known limits (deliberate — full shell parsing is out of scope): the protected set is an
exact, case-sensitive match (`main`, `master`, `production`, `prod`, `release`); a push
run by another program (`python -c`, a script file that itself pushes) is not seen;
quoted text such as `echo "git push origin main"` is correctly NOT treated as a push, but
unquoted text (`echo git push origin main`) and here-document lines that read like a
protected push are denied. Every push still goes through Claude Code's normal Bash
permission model, which is the backstop for anything this parser cannot see.

Fail-open on unreadable hook input — a broken guard must never become a session-wide
bypass of Claude's normal permission prompts. A command it cannot parse is denied only
when it looks like a git push.
"""
import codecs
import json
import os
import re
import shlex
import subprocess
import sys

PROTECTED = {"main", "master", "production", "prod", "release"}
FORCE_FLAGS = {"--force", "-f", "--force-with-lease", "--force-if-includes"}
FORCE_CLUSTER_RE = re.compile(r"^-[A-Za-z0-9]*f[A-Za-z0-9]*$")  # -f inside a short-flag cluster: -uf, -fu
SHELL_C_RE = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")  # -c inside a short-flag cluster: -lc, -ec, -xc
ALL_BRANCH_FLAGS = {"--all", "--mirror", "--branches"}
# push options that consume the next token when not written as --opt=value
# (`--signed` takes a value only as `--signed=…`, so it never consumes the next word; independent review)
VALUE_FLAGS = {"-o", "--push-option", "--receive-pack", "--exec", "--repo", "--recurse-submodules"}
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
OPERATOR_CHARS = "();<>|&\n`"
OPERATORS = ("&>>", "<<<", "<<-", "&&", "||", ";;", "|&", "&>", ">>", ">&", "<&", ">|", "<>", "<<", ";", "|", "&",
             "(", ")", "<", ">", "\n", "`")
SEPARATORS = {"&&", "||", ";", ";;", "|", "|&", "&", "\n", "(", ")", "`"}
REDIRECT_RE = re.compile(r"^(?:&>>?|>>?|>\||>&|<<<|<<-?|<&|<>|<)$")
COMMENT_AFTER = " \t\n;&|()<>"  # bash blanks are space and tab; a carriage return is part of a word
RESERVED_WORDS = {"!", "{", "}", "if", "then", "elif", "else", "fi", "while", "until", "do", "done", "time"}
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
PUSH_LIKE_RE = re.compile(r"\bgit\b.*\bpush\b", re.S)
UNKNOWN_DIR = "<unknown directory>"
MAX_DEPTH = 3


def _strip_comments(cmd: str) -> str:
    """Prepare the text the way bash reads it before shlex sees it:
    - remove `#` comments: only a `#` that starts a word, outside quotes, up to the newline; `a#b`, `$#`, `${x#y}`
      and `\\#` stay literal (shlex's own comment handling ends a word at any `#`);
    - join backslash-newline line continuations, outside single quotes (independent review: `ma\\⏎in` was the
      refspec `\\nmain`, not `main`);
    - decode ANSI-C `$'…'` quoting into an ordinary quoted word, and read `$"…"` as `"…"`."""
    out, i, n, boundary = [], 0, len(cmd), True
    while i < n:
        c = cmd[i]
        if c == "\\":
            if cmd[i + 1:i + 2] == "\n":
                i += 2  # a line continuation: the word goes on, `boundary` unchanged
                continue
            out.append(cmd[i:i + 2])
            i, boundary = i + 2, False
        elif c == "$" and cmd[i + 1:i + 2] == "'":
            j = i + 2
            while j < n and cmd[j] != "'":
                j += 2 if cmd[j] == "\\" else 1
            try:
                text = codecs.decode(cmd[i + 2:j], "unicode_escape")
            except Exception:
                text = cmd[i + 2:j]
            out.append("'" + text.replace("'", "'\"'\"'") + "'")
            i, boundary = j + 1, False
        elif c == "$" and cmd[i + 1:i + 2] == '"':
            i += 1  # `$"…"` is a locale-translated "…": the same words
        elif c in "'\"":
            j = i + 1
            while j < n and cmd[j] != c:
                j += 2 if c == '"' and cmd[j] == "\\" else 1
            quoted = cmd[i:j + 1]
            out.append(quoted.replace("\\\n", "") if c == '"' else quoted)
            i, boundary = j + 1, False
        elif c == "#" and boundary:
            j = cmd.find("\n", i)
            i = n if j < 0 else j
        else:
            out.append(c)
            i, boundary = i + 1, c in COMMENT_AFTER
    return "".join(out)


def _split_operators(tok: str):
    """shlex returns a run of adjacent operator characters as one token (`;\\n`, `)&&`); split it."""
    if not tok or any(ch not in OPERATOR_CHARS for ch in tok):
        return [tok]
    parts, k = [], 0
    while k < len(tok):
        op = next(o for o in OPERATORS if tok.startswith(o, k))
        parts.append(op)
        k += len(op)
    return parts


def segments(cmd: str):
    """Token lists for each simple command, or None when the command cannot be tokenized (unbalanced quotes)."""
    try:
        lex = shlex.shlex(_strip_comments(cmd), posix=True, punctuation_chars=OPERATOR_CHARS)
        lex.whitespace = " \t\r"
        lex.whitespace_split = True
        lex.commenters = ""
        tokens = [part for tok in lex for part in _split_operators(tok)]
    except ValueError:
        return None
    segs, seg, i = [], [], 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in SEPARATORS:
            if seg:
                segs.append(seg)
            seg = []
        elif REDIRECT_RE.match(tok):
            if i + 1 < len(tokens) and tokens[i + 1] not in SEPARATORS:
                i += 1  # the redirection target or here-document delimiter; `<(` keeps its `(`
        elif tok.isdigit() and i + 1 < len(tokens) and REDIRECT_RE.match(tokens[i + 1]):
            pass  # the "2" in "2>/dev/null"
        else:
            seg.append(tok)
        i += 1
    if seg:
        segs.append(seg)
    return segs


def current_branch(cwd: str):
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return (out.stdout.strip() or None) if out.returncode == 0 else None
    except Exception:
        return None


def _resolve_dir(target: str, base):
    """A literal directory resolved against base; None when base is unknown or the shell would compute the path
    (`$X`, a substitution, a glob, `~user`, `cd -`)."""
    if base is None or not target or target == "-" or any(ch in target for ch in "$`*?["):
        return None
    if target.startswith("~") and target != "~" and not target.startswith("~/"):
        return None
    return os.path.normpath(os.path.join(base, os.path.expanduser(target)))


def _command_position(seg, k) -> bool:
    """True when seg[k] is where bash looks for the command name (after reserved words, assignments, and `builtin` /
    `command`, which run the word after them; independent review: `builtin cd ../repo` was not followed)."""
    return all(t in RESERVED_WORDS or t in ("builtin", "command") or ASSIGNMENT_RE.match(t) for t in seg[:k])


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


def target_branches(push, dirs):
    """Every destination branch a `git push` invocation would update (or delete). A destination that depends on the
    current branch is checked in every directory the push may run in; a None directory is reported as unknown."""
    def current():
        return [current_branch(d) if d is not None else UNKNOWN_DIR for d in dirs]

    args = push_positionals(push)
    if len(args) < 2:
        return current()  # bare `git push` or `git push <remote>`
    targets = []
    for refspec in args[1:]:
        refspec = refspec.lstrip("+")
        src, sep, dst = refspec.partition(":")
        name = dst if sep else src
        if name in ("", "HEAD", "@"):
            targets.extend(current())
            continue
        targets.append(name.replace("refs/heads/", ""))
    return targets


GIT_ENV_RE = re.compile(r"^(?:GIT_DIR|GIT_WORK_TREE)=")


def _git_push(seg, k):
    """(push argv, `-C` dirs, unknown) when seg[k] is `git` running `push`, else None. `unknown` names a global
    option that picks the repository (`--git-dir`, `--work-tree`) or the push destination (`-c push.*`,
    `-c remote.*`) in a way the guard does not follow (independent review of the F10 fix)."""
    j, cdirs, unknown = k + 1, [], None
    while j < len(seg) and seg[j].startswith("-"):
        opt = seg[j]
        if opt == "-C":
            if j + 1 < len(seg):
                cdirs.append(seg[j + 1])
        elif opt.startswith("-C"):
            cdirs.append(opt[2:])
        elif opt == "-c" and j + 1 < len(seg) and seg[j + 1].lower().startswith(("push.", "remote.")):
            unknown = "-c " + seg[j + 1].split("=")[0]
        elif opt.split("=")[0] in ("--git-dir", "--work-tree"):
            unknown = opt.split("=")[0]
        j += 2 if opt in GIT_VALUE_OPTIONS else 1
    if j < len(seg) and seg[j] == "push":
        return seg[j:], cdirs, unknown
    return None


def _push_reason(push, dirs, unknown=None):
    if any(t in FORCE_FLAGS or t.startswith("--force") or FORCE_CLUSTER_RE.match(t) for t in push[1:]):
        return ("block_protected_push: force-push is not allowed from Claude. Push a normal commit, "
                "or ask the user to force-push themselves.")
    if any(t in ALL_BRANCH_FLAGS for t in push[1:]):
        return ("block_protected_push: `git push --all/--mirror/--branches` pushes every branch, including "
                "protected ones, so it is not allowed from Claude. Push one feature branch explicitly.")
    for target in target_branches(push, dirs):
        if target == UNKNOWN_DIR:
            how = f"sets `{unknown}`" if unknown else "runs in a directory the guard cannot determine"
            return (f"block_protected_push: this push {how}, so the guard cannot check which branch it updates. "
                    "Name the branch explicitly (`git push origin <branch>`) or push yourself.")
        if target in PROTECTED:
            return (f"block_protected_push: direct push to protected branch '{target}' is not allowed "
                    "(branch → PR → merge). Push a feature branch and open a PR instead.")
    return None


def inspect_command(cmd: str, cwd: str, depth: int = 0, state=None):
    """Return a denial reason for the first violating `git push`, else None. `state` is shared with nested
    `eval` / `sh -c` commands so a `cd` or a GIT_DIR assignment in them counts for later pushes: dirs are the
    directories the command may be running in (the session's, plus every `cd` target seen so far)."""
    if depth > MAX_DEPTH:
        return ("block_protected_push: too many nested shells to check this git push; run it yourself."
                if PUSH_LIKE_RE.search(cmd) else None)
    segs = segments(cmd)
    if segs is None:
        return ("block_protected_push: this command could not be parsed (unbalanced quotes) and looks like a git "
                "push; run the push yourself or simplify the command." if PUSH_LIKE_RE.search(cmd) else None)
    if state is None:
        state = {"dirs": [cwd], "git_env": None}
    dirs = state["dirs"]
    for seg in segs:
        for k, tok in enumerate(seg):
            name = os.path.basename(tok)
            if GIT_ENV_RE.match(tok):
                state["git_env"] = tok.split("=")[0]  # GIT_DIR=… / export GIT_WORK_TREE=… picks another repository
            elif name in ("cd", "pushd") and _command_position(seg, k):
                args = [a for a in seg[k + 1:] if not a.startswith("-") or a == "-"]
                dirs.append(os.path.expanduser("~") if not args else _resolve_dir(args[0], dirs[-1]))
            elif name in SHELLS:
                # Recurse into nested shells so `bash -c "…"` and `bash -lc "…"` are seen.
                for j in range(k + 1, len(seg) - 1):
                    if SHELL_C_RE.match(seg[j]):
                        reason = inspect_command(seg[j + 1], cwd, depth + 1, state)
                        if reason:
                            return reason
                        break
            elif name == "eval":
                reason = inspect_command(" ".join(seg[k + 1:]), cwd, depth + 1, state)
                if reason:
                    return reason
            elif name == "git":
                found = _git_push(seg, k)
                if not found:
                    continue
                push, cdirs, unknown = found
                unknown = unknown or state["git_env"]
                push_dirs = list(dirs)
                for c in cdirs:  # each -C is relative to the previous one, as in git
                    push_dirs = [_resolve_dir(c, d) for d in push_dirs]
                if cdirs:
                    push_dirs = push_dirs + [cwd]  # never weaker than checking the session's directory
                if unknown:
                    push_dirs = [None]
                reason = _push_reason(push, push_dirs, unknown)
                if reason:
                    return reason
    return None


def deny(reason: str):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))
    sys.exit(0)


def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError("hook input must be a JSON object")
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
