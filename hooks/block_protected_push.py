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
    directory, each `cd`/`pushd` target earlier in the command, `git -C <dir>` and `env -C <dir>`.
    A directory it cannot determine (`cd "$X"`), or one whose branch it cannot read (not created
    yet), denies a push that depends on it;
  - a push the shell or git computes fails closed: an argument with `$`, a substitution, a glob or
    a brace expansion (`origin $B`, `HEAD:$(…)`, `{main,}`), arguments xargs appends, a computed
    `git` or subcommand, and a `-c alias.*` (`$(git branch --show-current)` is read as `HEAD`).
    `$'…'` is decoded as bash 5.2 decodes it, cut at a NUL.

Known limits (deliberate — full shell parsing is out of scope): the protected set is an
exact, case-sensitive match (`main`, `master`, `production`, `prod`, `release`); a push
run by another program (`python -c`, a script file that itself pushes) is not seen, nor a
destination or alias set in a git config file (`.git/config`, `~/.gitconfig`); a computed
git subcommand is denied even when it is not a push (`git $c` in a loop);
quoted text such as `echo "git push origin main"` is correctly NOT treated as a push, but
unquoted text (`echo git push origin main`) and here-document lines that read like a
protected push are denied. Every push still goes through Claude Code's normal Bash
permission model, which is the backstop for anything this parser cannot see.

Fail-open on unreadable hook input — a broken guard must never become a session-wide
bypass of Claude's normal permission prompts. A command it cannot parse is denied only
when it looks like a git push.
"""
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
# characters that make the shell compute a word: an expansion, a substitution, a glob or a brace expansion
COMPUTED_CHARS = "$`{*?["
# `$(git branch --show-current)` and its equivalents name the current branch, exactly like the refspec `HEAD`
CURRENT_BRANCH_RE = re.compile(
    r"\$\(\s*(?P<a>git\s+(?:branch\s+--show-current|rev-parse\s+--abbrev-ref\s+(?:HEAD|@)|symbolic-ref\s+--short\s+HEAD))"
    r"\s*\)|`\s*(?P<b>git\s+(?:branch\s+--show-current|rev-parse\s+--abbrev-ref\s+(?:HEAD|@)|symbolic-ref\s+--short\s+HEAD))\s*`")
# `-c <key>=…` keys that pick a push's repository or destination (others, such as push.autoSetupRemote, do not)
PUSH_CONFIG_RE = re.compile(r"^(?:push\.default|remote\.pushdefault|remote\..+\.(?:push|mirror)"
                            r"|branch\..+\.(?:merge|remote|pushremote)|include\.path|includeif\..+\.path)$")
ANSI_C_SIMPLE = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "n": "\n", "r": "\r", "t": "\t",
                 "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"}
ANSI_C_HEX = {"x": 2, "u": 4, "U": 8}


def _ansi_c(body: str) -> str:
    """The text bash makes of `$'body'` (bash 5.2): its escapes, cut at the first NUL — bash ends the quoted text
    there (`$'ma\\x00junk'in` is `main`; independent review). Python's unicode_escape differs (`\\u6d`, `\\c@`)."""
    out, i, n = [], 0, len(body)
    while i < n:
        c, e = body[i], body[i + 1:i + 2]
        if c != "\\" or not e:
            out.append(c)
            i += 1
        elif e in ANSI_C_SIMPLE:
            out.append(ANSI_C_SIMPLE[e])
            i += 2
        elif e in "01234567":
            m = re.match(r"[0-7]{1,3}", body[i + 1:])
            out.append(chr(int(m.group(0), 8) & 0xFF))
            i += 1 + len(m.group(0))
        elif e in ANSI_C_HEX and (m := re.match(r"[0-9A-Fa-f]{1,%d}" % ANSI_C_HEX[e], body[i + 2:])):
            out.append(chr(min(int(m.group(0), 16), 0x10FFFF)))
            i += 2 + len(m.group(0))
        elif e == "c" and i + 2 < n:
            ch = body[i + 2]
            out.append(chr(0x7F if ch == "?" else ord(ch.upper()) & 0x1F))  # `\c@` is NUL
            i += 3
        else:
            out.append(c)  # an escape bash does not know keeps its backslash (`\N`, `\z`, a bare `\x`)
            i += 1
    return "".join(out).split("\0", 1)[0]


def _strip_comments(cmd: str) -> str:
    """Prepare the text the way bash reads it before shlex sees it:
    - remove `#` comments: only a `#` that starts a word, outside quotes, up to the newline; `a#b`, `$#`, `${x#y}`
      and `\\#` stay literal (shlex's own comment handling ends a word at any `#`);
    - join backslash-newline line continuations, outside single quotes (independent review: `ma\\⏎in` was the
      refspec `\\nmain`, not `main`);
    - decode ANSI-C `$'…'` quoting into an ordinary quoted word, and read `$"…"` as `"…"`;
    - read `$(git branch --show-current)` (and its equivalents) as `HEAD`, the current branch."""
    cmd = CURRENT_BRANCH_RE.sub("HEAD", cmd)
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
            out.append("'" + _ansi_c(cmd[i + 2:j]).replace("'", "'\"'\"'") + "'")
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
    # A command substitution `$(…)` / `…` is its own command, and the command around it goes on after it with the
    # substitution's place kept by its `$` / backtick (independent review: `$(echo git) push origin main`).
    segs, seg, i, outer, tick = [], [], 0, [], None
    while i < len(tokens):
        tok = tokens[i]
        if tok == "(":
            outer.append(seg if seg and seg[-1].endswith("$") else None)
            if seg and outer[-1] is None:
                segs.append(seg)
            seg = []
        elif tok == ")" and outer:
            if seg:
                segs.append(seg)
            seg = outer.pop() or []
        elif tok == "`":
            if seg and tick is not None:
                segs.append(seg)
            seg, tick = ([], seg + ["`"]) if tick is None else (tick, None)
        elif tok in SEPARATORS:
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
    for pending in [seg, tick] + outer:  # an unclosed substitution still shows the command around it
        if pending:
            segs.append(pending)
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
    if base is None or not target or target == "-" or "\0" in target or any(ch in target for ch in "$`*?["):
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


def target_branches(push, dirs, home=None):
    """Every destination branch a `git push` invocation would update (or delete). A destination that depends on the
    current branch is checked in every directory the push may run in; a None directory, or one whose current branch
    cannot be read (it does not exist yet, or git fails on it), is reported as unknown — except the session's own
    directory (`home`) outside any repository, where a push fails anyway (independent review: a path git could not
    open let the push through)."""
    def current():
        found = []
        for d in dirs:
            branch = current_branch(d) if d is not None else None
            found.append(branch or (None if d is not None and d == home else UNKNOWN_DIR))
        return found

    args = push_positionals(push)
    if len(args) < 2:
        return current()  # bare `git push` or `git push <remote>`
    targets = []
    for refspec in args[1:]:
        src, sep, dst = refspec.lstrip("+").partition(":")
        name = dst if sep else src
        if name in ("", "HEAD", "@"):
            targets.extend(current())
            continue
        name = name.replace("refs/heads/", "")
        targets.append(name[len("heads/"):] if name.startswith("heads/") else name)  # git reads `heads/main` as main
    return targets


# GIT_DIR / GIT_WORK_TREE pick another repository; GIT_CONFIG* (files, GIT_CONFIG_COUNT/KEY/VALUE,
# GIT_CONFIG_PARAMETERS) can set push.default or remote.*.push
GIT_ENV_RE = re.compile(r"^(?:GIT_DIR|GIT_WORK_TREE|GIT_CONFIG\w*)=")


def _git_push(seg, k):
    """(push argv, `-C` dirs, unknown, computed) when seg[k] is `git` running `push`, else None.
    - `unknown` names a global option that picks the repository (`--git-dir`, `--work-tree`) or the destination
      (`-c push.default=…`, `-c remote.<name>.push=…`, `--config-env …`) in a way the guard does not follow
      (independent review of the F10 fix); other keys, such as push.autoSetupRemote, change neither.
    - `computed` names a part the shell or git computes, so the guard cannot know what runs: a subcommand or global
      option with `$`, a substitution, a glob or a brace expansion (`git $C origin main`, `git {push,} …`), or a git
      alias defined with `-c alias.<name>=…` that runs a shell command."""
    j, cdirs, unknown, computed, aliases = k + 1, [], None, None, {}
    while j < len(seg) and seg[j].startswith("-"):
        opt = seg[j]
        value = seg[j + 1] if opt in GIT_VALUE_OPTIONS and j + 1 < len(seg) else ""
        if any(ch in opt + value for ch in "$`"):
            computed = computed or f"git option `{opt}`"
        if opt == "-C":
            cdirs.append(value)
        elif opt.startswith("-C"):
            cdirs.append(opt[2:])
        elif opt in ("-c", "--config-env") or opt.startswith("--config-env="):
            item = opt.split("=", 1)[1] if opt.startswith("--config-env=") else value
            key, _, setting = item.partition("=")
            key = key.lower()
            if key.startswith("alias."):
                aliases[key[len("alias."):]] = setting if opt == "-c" else "!"  # --config-env: value in a variable
            elif PUSH_CONFIG_RE.match(key):
                unknown = f"{opt.split('=')[0]} {key}"
        elif opt.split("=")[0] in ("--git-dir", "--work-tree"):
            unknown = opt.split("=")[0]
        j += 2 if opt in GIT_VALUE_OPTIONS else 1
    argv = seg[j:]
    for _ in range(8):  # git expands an alias, also one that names another alias
        if not argv or argv[0].lower() not in aliases:
            break
        setting = aliases.pop(argv[0].lower())
        if setting.startswith("!"):
            return ["push"] + argv[1:], cdirs, unknown, f"git alias `{argv[0]}` (a shell command)"
        try:
            argv = shlex.split(setting) + argv[1:]
        except ValueError:
            return ["push"] + argv[1:], cdirs, unknown, f"git alias `{argv[0]}`"
    if argv and any(ch in argv[0] for ch in COMPUTED_CHARS):
        return argv, cdirs, unknown, f"git subcommand `{argv[0]}`"
    if argv and argv[0] == "push":
        return argv, cdirs, unknown, computed
    return None


def _env_chdirs(seg, k):
    """Directories `env -C DIR` / `env --chdir=DIR` before seg[k] moves the command into."""
    found = []
    for e in range(k):
        if os.path.basename(seg[e]) != "env":
            continue
        x = e + 1
        while x < k:
            t = seg[x]
            if t in ("-C", "--chdir") and x + 1 < k:
                found.append(seg[x + 1])
                x += 1
            elif t.startswith("--chdir="):
                found.append(t.split("=", 1)[1])
            elif t.startswith("-C") and len(t) > 2:
                found.append(t[2:])
            x += 1
    return found


def _computed_reason(what):
    return (f"block_protected_push: this push depends on {what}, which the shell or git computes, so the guard cannot "
            "check which branch it updates. Write the push literally (`git push origin <branch>` or "
            "`git push origin HEAD`) or push yourself.")


def _push_reason(push, dirs, unknown=None, computed=None, home=None):
    refspecs = push_positionals(push)[1:]
    if (any(t in FORCE_FLAGS or t.startswith("--force") or FORCE_CLUSTER_RE.match(t) for t in push[1:])
            or any(r.startswith("+") for r in refspecs)):  # `+refspec` force-updates that branch
        return ("block_protected_push: force-push is not allowed from Claude. Push a normal commit, "
                "or ask the user to force-push themselves.")
    if any(t in ALL_BRANCH_FLAGS for t in push[1:]) or ":" in refspecs:
        return ("block_protected_push: `git push --all/--mirror/--branches` (or the refspec `:`) pushes every "
                "branch, including protected ones, so it is not allowed from Claude. Push one feature branch "
                "explicitly.")
    if computed:
        return _computed_reason(computed)
    expanded = next((t for t in push if any(ch in t for ch in COMPUTED_CHARS)), None)
    if expanded is not None:  # `git push origin $B`, `HEAD:$(…)`, `{main,}`, a glob (independent review)
        return _computed_reason(f"`{expanded}`")
    for target in target_branches(push, dirs, home):
        if target == UNKNOWN_DIR:
            how = (f"sets `{unknown}`" if unknown else
                   "runs where the guard cannot read the current branch (a computed `cd`, or a directory that does "
                   "not exist yet)")
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
            if (_command_position(seg, k) and any(ch in tok for ch in "$`") and not ASSIGNMENT_RE.match(tok)
                    and "push" in seg[k:]):
                # a computed command name running `push`: `$G push origin main`, `$(echo git) push origin main`
                return _computed_reason(f"a computed command (`{tok} … push`)")
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
                    rest = seg[k + 1:]
                    if "push" in rest and any(ch in t for t in rest[:rest.index("push")] for ch in "$`"):
                        # a computed word before `push` can be the whole subcommand position (`git -C $(…)/x push`)
                        return _computed_reason(f"a computed word before `push` (`{' '.join(seg[k:k + 4])} …`)")
                    continue
                push, cdirs, unknown, computed = found
                if any(os.path.basename(t) == "xargs" for t in seg[:k]):
                    computed = computed or "arguments xargs appends"  # `echo main | xargs git push origin`
                split = next((t for t in seg[:k] if any(ch in t for ch in "$`") and not ASSIGNMENT_RE.match(t)), None)
                if split:
                    # an unquoted `$U` before git can split into words that run another push first
                    # (`sudo -u $U git push origin feature/x` with U="root git push origin main")
                    computed = computed or f"`{split}` before git"
                cdirs = _env_chdirs(seg, k) + cdirs
                unknown = unknown or state["git_env"]
                push_dirs = list(dirs)
                for c in cdirs:  # each -C is relative to the previous one, as in git
                    push_dirs = [_resolve_dir(c, d) for d in push_dirs]
                if cdirs:
                    # never weaker than the shell's own directories: `$(git branch --show-current)` runs there
                    push_dirs = push_dirs + list(dirs)
                if unknown:
                    push_dirs = [None]
                reason = _push_reason(push, push_dirs, unknown, computed, cwd)
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
