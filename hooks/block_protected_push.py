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
    `git` or subcommand, any computed word before `push`, and a `-c alias.*` that runs a shell
    (`$(git branch --show-current)` is read as the current branch). `$'…'` is decoded as bash 5.2
    decodes it, cut at a NUL;
  - substitutions inside double quotes, `${…}` and unquoted here-documents are checked; a here-document
    body is otherwise data, unless it feeds a shell (`bash <<EOF`);
  - a branch switch earlier in the command (`git switch main`, `git checkout -`, `git branch -m`,
    `git init`) makes a later bare or `HEAD` push unknown; after `git checkout -b <name>` it is <name>.

Known limits (deliberate — full shell parsing is out of scope): the protected set is an
exact, case-sensitive match (`main`, `master`, `production`, `prod`, `release`); a push
run by another program (`python -c`, a script file that itself pushes) or fed to a shell on
stdin (`echo … | bash`) is not seen, nor a destination or alias set in a git config file
(`.git/config`, `~/.gitconfig`), nor a push whose run order differs from its text order
(a function or trap defined before a `cd`); a computed git subcommand is denied even when it
is not a push (`git $c` in a loop), and so is a computed word before the word `push`
(`echo $(date) push`). Quoted text such as `echo "git push origin main"` is correctly NOT
treated as a push, but unquoted text (`echo git push origin main`) is denied. Because a
program can push without any of this text, the guard stops mistakes rather than a determined
adversary: branch protection on the server is the control for that. Every push still goes
through Claude Code's normal Bash permission model, which is the backstop for anything this
parser cannot see.

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
# `$(git branch --show-current)` and its equivalents name the current branch. They are replaced by CURRENT, which
# is resolved like `HEAD` when it is a whole destination (`origin "$(…)"`, `HEAD:refs/heads/$(…)`) and is computed
# anywhere else (`main$(…)`; independent review).
CURRENT = "__groundwork_current_branch__"
CURRENT_BRANCH_RE = re.compile(
    r"\$\(\s*(?P<a>git\s+(?:branch\s+--show-current|rev-parse\s+--abbrev-ref\s+(?:HEAD|@)|symbolic-ref\s+--short\s+HEAD))"
    r"\s*\)|`\s*(?P<b>git\s+(?:branch\s+--show-current|rev-parse\s+--abbrev-ref\s+(?:HEAD|@)|symbolic-ref\s+--short\s+HEAD))\s*`")
# `-c <key>=…` keys that pick a push's repository or destination (others, such as push.autoSetupRemote, do not)
PUSH_CONFIG_RE = re.compile(r"^(?:push\.default|remote\.pushdefault|remote\..+\.(?:push|mirror)"
                            r"|branch\..+\.(?:merge|remote|pushremote)|include\.path|includeif\..+\.path)$")
# GIT_DIR / GIT_WORK_TREE pick another repository; GIT_CONFIG* (files, GIT_CONFIG_COUNT/KEY/VALUE,
# GIT_CONFIG_PARAMETERS) can set push.default or remote.*.push
GIT_ENV_RE = re.compile(r"^(?:GIT_DIR|GIT_WORK_TREE|GIT_CONFIG\w*)=")
# `git checkout -b NAME` / `git switch -c NAME` make NAME the current branch
CREATE_FLAGS = {"checkout": ("-b", "-B", "--orphan"), "switch": ("-c", "-C", "--create", "--force-create", "--orphan")}
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
            if ch == "?":
                out.append("\x7f")
            else:  # `\c@` is NUL; bash takes a non-ASCII character's first byte (independent review: `\cß` crashed)
                code = ord(ch.upper()) if ch.isascii() else ch.encode("utf-8", "surrogatepass")[0]
                out.append(chr(code & 0x1F))
            i += 3
        else:
            out.append(c)  # an escape bash does not know keeps its backslash (`\N`, `\z`, a bare `\x`)
            i += 1
    return "".join(out).split("\0", 1)[0]


def _heredoc_delimiter(cmd: str, j: int):
    """(delimiter, index after it, quoted) for the word after `<<` / `<<-` at j, or None when it is not one
    (it must start with a letter, `_`, a quote or a backslash; `1<<2` is a shift). Same rules as the task gate."""
    n = len(cmd)
    while j < n and cmd[j] in " \t":
        j += 1
    if j >= n or not (cmd[j].isalpha() or cmd[j] in "_'\"\\"):
        return None
    word, quoted = [], False
    while j < n and cmd[j] not in " \t\r" and cmd[j] not in OPERATOR_CHARS:
        if cmd[j] in "'\"":
            k = cmd.find(cmd[j], j + 1)
            if k < 0:
                return None
            word.append(cmd[j + 1:k])
            j, quoted = k + 1, True
        elif cmd[j] == "\\":
            word.append(cmd[j + 1:j + 2])
            j, quoted = j + 2, True
        else:
            word.append(cmd[j])
            j += 1
    return ("".join(word), j, quoted) if word else None


def _scan_braced(cmd: str, j: int):
    """Index just past the `}` closing a `${` whose body starts at j (quotes honoured), or None when unclosed."""
    n, depth = len(cmd), 1
    while j < n and depth:
        ch = cmd[j]
        if ch == "\\":
            j += 2
            continue
        if ch in "'\"":
            k = j + 1
            while k < n and cmd[k] != ch:
                k += 2 if ch == '"' and cmd[k] == "\\" else 1
            if k >= n:
                return None
            j = k + 1
            continue
        depth += {"{": 1, "}": -1}.get(ch, 0)
        j += 1
    return j if depth == 0 else None


def _scan_arithmetic(cmd: str, j: int):
    """Index just past the `))` closing an arithmetic `((` whose body starts at j, or None when the parentheses do
    not close as `))` (then they are nested subshells, `((cd a); ls)`)."""
    n, depth, first_close = len(cmd), 2, None
    while j < n and depth:
        if cmd[j] == "(":
            depth += 1
        elif cmd[j] == ")":
            depth -= 1
            if depth == 1 and first_close is None:
                first_close = j
        j += 1
    return j if depth == 0 and first_close == j - 2 else None


def _matching_paren(text: str, j: int):
    """Index of the `)` closing a group whose body starts at j, honouring quotes, escapes and here-document bodies
    inside it (`"$(cat <<'EOF' … don't … EOF)"`, the usual commit-message form), or None when unclosed."""
    n, depth, pending = len(text), 1, []
    while j < n:
        ch = text[j]
        if ch == "\\":
            j += 2
        elif ch in "'\"":
            k = j + 1
            while k < n and text[k] != ch:
                k += 2 if ch == '"' and text[k] == "\\" else 1
            if k >= n:
                return None
            j = k + 1
        elif text.startswith("<<", j) and not text.startswith("<<<", j):
            strip = text.startswith("<<-", j)
            found = _heredoc_delimiter(text, j + (3 if strip else 2))
            if found:
                pending.append((found[0], strip))
                j = found[1]
            else:
                j += 2
        elif ch == "\n" and pending:
            j += 1
            for delim, strip in pending:  # skip each body up to its terminator line
                while True:
                    if j >= n:
                        return None
                    k = text.find("\n", j)
                    k = n if k < 0 else k
                    line = text[j:k]
                    j = min(k + 1, n)
                    if (line.lstrip("\t") if strip else line) == delim:
                        break
            pending = []
        else:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return j
            j += 1
    return None


def _substitutions_in(text: str, subs: list, single_quotes: bool) -> bool:
    """Add the body of every `$(…)` and backtick in text to subs (bash runs them); False when one is unclosed.
    `single_quotes`: whether `'…'` quotes here (not inside double quotes or a here-document)."""
    k, n = 0, len(text)
    while k < n:
        ch = text[k]
        if ch == "\\":
            k += 2
        elif ch == "'" and single_quotes:
            e = text.find("'", k + 1)
            if e < 0:
                return False
            k = e + 1
        elif text.startswith("$(", k):
            e = _matching_paren(text, k + 2)
            if e is None:
                return False
            subs.append(text[k + 2:e])
            k = e + 1
        elif ch == "`":
            e = k + 1
            while e < n and text[e] != "`":
                e += 2 if text[e] == "\\" else 1
            if e >= n:
                return False
            subs.append(text[k + 1:e])
            k = e + 1
        else:
            k += 1
    return True


def _prepare(cmd: str):
    """Prepare the text the way bash reads it before shlex sees it. Returns (text, substitutions) — the bodies of
    the `$(…)` / backticks shlex would keep inside one word, which bash runs — or None when the command cannot be
    read (an unclosed quote, substitution or `${`).
    - remove `#` comments: only a `#` that starts a word, outside quotes, up to the newline; `a#b`, `$#`, `${x#y}`
      and `\\#` stay literal (shlex's own comment handling ends a word at any `#`);
    - join backslash-newline line continuations, outside single quotes (independent review: `ma\\⏎in` was the
      refspec `\\nmain`, not `main`);
    - decode ANSI-C `$'…'` quoting into an ordinary quoted word, and read `$"…"` as `"…"`;
    - read `$(git branch --show-current)` (and its equivalents) as CURRENT;
    - keep `${…}`, `$((…))` and `((…))` whole, so a `<<` in them is not a here-document;
    - a here-document body is data for its command and is dropped, except that a body fed to a shell
      (`bash <<EOF`) is returned as commands, and the substitutions in a body whose delimiter is unquoted are
      returned (independent review: a body with an apostrophe made an ordinary push unparseable);
    - the substitutions inside double quotes and `${…}` are returned (independent review:
      `out="$(git push origin main 2>&1)"` was not seen)."""
    cmd = CURRENT_BRANCH_RE.sub(CURRENT, cmd)
    out, subs, heredocs = [], [], []
    i, n, boundary, line_start = 0, len(cmd), True, 0
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
            if j >= n:
                return None
            out.append("'" + _ansi_c(cmd[i + 2:j]).replace("'", "'\"'\"'") + "'")
            i, boundary = j + 1, False
        elif c == "$" and cmd[i + 1:i + 2] == '"':
            i += 1  # `$"…"` is a locale-translated "…": the same words
        elif c == "$" and cmd[i + 1:i + 2] == "{":
            j = _scan_braced(cmd, i + 2)
            if j is None or not _substitutions_in(cmd[i + 2:j - 1], subs, True):
                return None
            out.append(cmd[i:j])
            i, boundary = j, False
        elif (c == "$" and cmd.startswith("$((", i) and _scan_arithmetic(cmd, i + 3)) or \
                (c == "(" and boundary and cmd.startswith("((", i) and _scan_arithmetic(cmd, i + 2)):
            start = i + (3 if c == "$" else 2)
            j = _scan_arithmetic(cmd, start)
            if not _substitutions_in(cmd[start:j - 2], subs, True):
                return None
            out.append(cmd[i:j])  # arithmetic: `<<` is a shift, not a here-document
            i, boundary = j, False
        elif c == '"':
            j = i + 1
            while j < n and cmd[j] != '"':
                if cmd[j] == "\\":
                    j += 2
                elif cmd.startswith("$(", j) and not cmd.startswith("$((", j):  # "$(echo ")")" stays one word
                    k = _matching_paren(cmd, j + 2)
                    if k is None:
                        return None
                    j = k + 1
                elif cmd[j] == "`":
                    k = j + 1
                    while k < n and cmd[k] != "`":
                        k += 2 if cmd[k] == "\\" else 1
                    j = k + 1
                else:
                    j += 1
            if j >= n:
                return None
            body = cmd[i + 1:j].replace("\\\n", "")
            if not _substitutions_in(body, subs, False):
                return None
            # a body with a substitution becomes one literal word (its `$` keeps it computed); its commands are checked
            # from subs, and quotes inside it cannot end the word early for shlex
            out.append("'" + body.replace("'", "'\"'\"'") + "'" if "$(" in body or "`" in body else '"' + body + '"')
            i, boundary = j + 1, False
        elif c == "'":
            j = cmd.find("'", i + 1)
            if j < 0:
                return None
            out.append(cmd[i:j + 1])
            i, boundary = j + 1, False
        elif c == "#" and boundary:
            j = cmd.find("\n", i)
            i = n if j < 0 else j
        elif cmd.startswith("<<<", i):
            out.append("<<<")  # a here-string, not a here-document
            i, boundary = i + 3, True
        elif cmd.startswith("<<", i):
            strip = cmd.startswith("<<-", i)
            found = _heredoc_delimiter(cmd, i + (3 if strip else 2))
            if found:
                heredocs.append((found[0], strip, found[2]))
                out.append(cmd[i:found[1]])
                i, boundary = found[1], False
            else:
                out.append(cmd[i:i + 2])
                i, boundary = i + 2, True
        elif c == "\n":
            out.append(c)
            i, boundary = i + 1, True
            if heredocs:
                line = "".join(out[line_start:])
                feeds_shell = any(os.path.basename(w) in SHELLS or w in ("source", ".")
                                  for w in re.findall(r"[^\s;&|()<>]+", line))
                for delim, strip, quoted in heredocs:  # the bodies start after this newline, one after another
                    lines = []
                    while i < n:
                        k = cmd.find("\n", i)
                        k = n if k < 0 else k
                        text = cmd[i:k]
                        i = min(k + 1, n)
                        if (text.lstrip("\t") if strip else text) == delim:
                            break
                        lines.append(text)  # without its terminator, bash reads the body to the end
                    body = "\n".join(lines)
                    if feeds_shell:
                        subs.append(body)
                    elif not quoted and not _substitutions_in(body, subs, False):
                        return None
                heredocs = []
            line_start = len(out)
        else:
            out.append(c)
            i, boundary = i + 1, c in COMMENT_AFTER
    return "".join(out), subs


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
    """(token lists for each simple command, substitution bodies to check), or None when the command cannot be
    tokenized (unbalanced quotes)."""
    prepared = _prepare(cmd)
    if prepared is None:
        return None
    text, subs = prepared
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=OPERATOR_CHARS)
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
    return segs, subs


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
    """True when seg[k] is where bash looks for the command name: after reserved words, assignments, and `builtin` /
    `command` (also `command -p`, `builtin --`), which run the word after them (independent review)."""
    for x, t in enumerate(seg[:k]):
        if t in RESERVED_WORDS or t in ("builtin", "command") or ASSIGNMENT_RE.match(t):
            continue
        if t in ("-p", "--") and x > 0 and seg[x - 1] in ("builtin", "command", "-p", "--"):
            continue
        return False
    return True


def _shell_command(args):
    """The command string of `sh ARGS` when it has `-c` (also `-lc`, `-c -x CMD`, `-o pipefail -c CMD`, `-c -- CMD`:
    -c makes the first operand the command string), else None. Same rules as the task gate."""
    i, has_c = 0, False
    while i < len(args):
        a = args[i]
        if a in ("--", "-"):
            i += 1
            break
        if a.startswith("--"):
            i += 2 if a in ("--rcfile", "--init-file") else 1
            continue
        if re.match(r"^[-+][a-zA-Z]+$", a):
            has_c = has_c or (a[0] == "-" and "c" in a)
            i += 1 + sum(ch in "oO" for ch in a[1:])  # each o/O takes the next argument as its option name
            continue
        break
    return args[i] if has_c and i < len(args) else None


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


def _branch_name(name: str) -> str:
    name = name.replace("refs/heads/", "")
    return name[len("heads/"):] if name.startswith("heads/") else name  # git reads `heads/main` as main


def target_branches(push, dirs, home=None, created=None, single=False):
    """Every destination branch a `git push` invocation would update (or delete). A destination that depends on the
    current branch is checked in every directory the push may run in; a None directory, or one whose current branch
    cannot be read (it does not exist yet, or git fails on it), is reported as unknown — except the session's own
    directory (`home`) outside any repository, where a push fails anyway (independent review: a path git could not
    open let the push through). `created`: a branch `git checkout -b` made current earlier in the command; it
    replaces the session directory's branch when the command never left that directory (`single`)."""
    def current():
        if created and single and None not in dirs:
            return [created]
        found = []
        for d in dirs:
            branch = current_branch(d) if d is not None else None
            found.append(branch or (None if d is not None and d == home else UNKNOWN_DIR))
        return found + ([created] if created else [])

    args = push_positionals(push)
    if len(args) < 2:
        return current()  # bare `git push` or `git push <remote>`
    targets = []
    for refspec in args[1:]:
        src, sep, dst = refspec.lstrip("+").partition(":")
        name = _branch_name(dst if sep else src)
        if name in ("", "HEAD", "@", CURRENT):
            targets.extend(current())
            continue
        targets.append(name)
    return targets


def _git_invocation(seg, k):
    """(argv from the subcommand on, `-C` dirs, unknown, computed) for the `git` at seg[k], or None when no
    subcommand follows. `-c alias.<name>=…` is expanded as git expands it, except an alias that shadows `push`, which
    git ignores (independent review).
    - `unknown` says how a global option picks the repository (`--git-dir`, `--work-tree`) or the destination
      (`-c push.default=…`, `-c remote.<name>.push=…`, `--config-env …`) in a way the guard does not follow;
      other keys, such as push.autoSetupRemote, change neither.
    - `computed` names a part the shell or git computes, so the guard cannot know what runs: a global option with
      `$` or a substitution, or a git alias that runs a shell command."""
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
                unknown = f"sets `{opt.split('=')[0]} {key}`"
        elif opt.split("=")[0] in ("--git-dir", "--work-tree"):
            unknown = f"sets `{opt.split('=')[0]}`"
        j += 2 if opt in GIT_VALUE_OPTIONS else 1
    argv = seg[j:]
    for _ in range(8):  # git expands an alias, also one that names another alias
        if not argv or argv[0] == "push" or argv[0].lower() not in aliases:
            break
        setting = aliases.pop(argv[0].lower())
        if setting.startswith("!"):
            return ["push"] + argv[1:], cdirs, unknown, f"git alias `{argv[0]}` (a shell command)"
        try:
            argv = shlex.split(setting) + argv[1:]
        except ValueError:
            return ["push"] + argv[1:], cdirs, unknown, f"git alias `{argv[0]}`"
    return (argv, cdirs, unknown, computed) if argv else None


def _branch_change(argv):
    """("created", NAME) when `git checkout -b NAME` / `git switch -c NAME` makes NAME the current branch;
    ("moved", what) when the command may switch to another branch (`git switch main`, `git checkout -`,
    `git branch -m`, `git init`, `git clone`, `git symbolic-ref HEAD …`, `git rebase <base> <branch>`,
    `git stash branch`), so a later `git push` / `git push origin HEAD` cannot be resolved from the repository as it
    is now (independent review: `git switch main && git merge … && git push origin HEAD`); else None."""
    sub, args = argv[0], argv[1:]
    positional = [a for a in args if not a.startswith("-")]
    moved = ("moved", f"git {sub}")
    if sub in CREATE_FLAGS:
        flags = CREATE_FLAGS[sub]
        letters = "".join(f[1] for f in flags if len(f) == 2)
        for x, a in enumerate(args):
            name = None
            if a in flags or (a.startswith("--") and a.split("=", 1)[0] in flags):
                name = a.split("=", 1)[1] if "=" in a else (args[x + 1] if x + 1 < len(args) else "")
            elif re.match(r"^-[A-Za-z]+", a) and not a.startswith("--") and any(ch in letters for ch in a[1:]):
                at = next(p for p, ch in enumerate(a[1:], 1) if ch in letters)  # -qb NAME, -bNAME
                name = a[at + 1:] or (args[x + 1] if x + 1 < len(args) else "")
            if name is not None:
                return ("created", name) if name and not any(ch in name for ch in COMPUTED_CHARS) else moved
        if "--" in args:
            return None  # `git checkout -- file` / `git checkout main -- file` restore files
        return moved if positional or "-" in args else None
    if sub == "branch" and any(a in ("-m", "-M", "--move") or re.match(r"^-[A-Za-z]*[mM]$", a) for a in args):
        return moved
    if sub in ("init", "clone") or (sub in ("symbolic-ref", "rebase") and len(positional) >= 2) or \
            (sub == "stash" and positional[:1] == ["branch"]):
        return moved
    return None


def _wrapper_chdirs(seg, k):
    """Directories `env -C DIR` / `env --chdir=DIR` (also clustered, `-iC DIR`) or `sudo -D DIR` before seg[k] move
    the command into."""
    found = []
    for e in range(k):
        prog = os.path.basename(seg[e])
        if prog not in ("env", "sudo"):
            continue
        letter, takes_value = ("C", "uS") if prog == "env" else ("D", "ugpCrtUTh")
        x = e + 1
        while x < k and seg[x].startswith("-") and seg[x] != "--":
            t = seg[x]
            if t == "--chdir" and x + 1 < k:
                found.append(seg[x + 1])
                x += 1
            elif t.startswith("--chdir="):
                found.append(t.split("=", 1)[1])
            elif not t.startswith("--"):
                for p, ch in enumerate(t[1:], 1):
                    if ch == letter:
                        if t[p + 1:]:
                            found.append(t[p + 1:])
                        elif x + 1 < k:
                            found.append(seg[x + 1])
                            x += 1
                        break
                    if ch in takes_value:
                        x += 0 if t[p + 1:] else 1  # the value is the rest of the cluster or the next word
                        break
            x += 1
    return found


def _computed_reason(what):
    return (f"block_protected_push: this push depends on {what}, which the shell or git computes, so the guard cannot "
            "check which branch it updates. Write the push literally (`git push origin <branch>` or "
            "`git push origin HEAD`) or push yourself.")


def _computed_word(push):
    """The first push word the shell computes (`$B`, `$(…)`, a glob or a brace expansion), or a destination that
    has `$(git branch --show-current)` inside a longer name; None when there is none. A value of `-o` and the like
    is checked for expansions only: a push option such as `x [WIP]` is text."""
    value_next = False
    for t in push:
        is_value = value_next or t.startswith(("--push-option=", "--receive-pack=", "--exec=", "--repo=")) or \
            (t.startswith("-o") and len(t) > 2)
        value_next = t in VALUE_FLAGS
        if any(ch in t for ch in ("$`{" if is_value else COMPUTED_CHARS)):
            return t
        if CURRENT in t and any(CURRENT in p and _branch_name(p) != CURRENT for p in t.lstrip("+").split(":")):
            return t.replace(CURRENT, "$(git branch --show-current)")
    return None


def _push_reason(push, dirs, unknown=None, computed=None, home=None, created=None, single=False):
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
    expanded = _computed_word(push)
    if expanded is not None:  # `git push origin $B`, `HEAD:$(…)`, `{main,}`, a glob (independent review)
        return _computed_reason(f"`{expanded}`")
    for target in target_branches(push, dirs, home, created, single):
        if target == UNKNOWN_DIR:
            how = unknown or ("runs where the guard cannot read the current branch (a computed `cd`, or a directory "
                              "that does not exist yet)")
            return (f"block_protected_push: this push {how}, so the guard cannot check which branch it updates. "
                    "Name the branch explicitly (`git push origin <branch>`) or push yourself.")
        if target in PROTECTED:
            return (f"block_protected_push: direct push to protected branch '{target}' is not allowed "
                    "(branch → PR → merge). Push a feature branch and open a PR instead.")
    return None


def inspect_command(cmd: str, cwd: str, depth: int = 0, state=None):
    """Return a denial reason for the first violating `git push`, else None. `state` is shared with nested
    `eval` / `sh -c` commands and substitutions, so a `cd`, a GIT_DIR assignment or a branch switch in them counts
    for later pushes: dirs are the directories the command may be running in (the session's, plus every `cd`
    target seen so far); head is a branch change seen so far (see _branch_change)."""
    if depth > MAX_DEPTH:
        return ("block_protected_push: too many nested shells to check this git push; run it yourself."
                if PUSH_LIKE_RE.search(cmd) else None)
    parsed = segments(cmd)
    if parsed is None:
        return ("block_protected_push: this command could not be parsed (unbalanced quotes) and looks like a git "
                "push; run the push yourself or simplify the command." if PUSH_LIKE_RE.search(cmd) else None)
    segs, subs = parsed
    if state is None:
        state = {"dirs": [cwd], "git_env": None, "head": None}
    dirs = state["dirs"]
    for seg in segs:
        if "push" in seg:
            before = seg[:seg.index("push")]
            word = next((t for t in before if any(ch in t for ch in "$`") and not ASSIGNMENT_RE.match(t)), None)
            if word is not None:
                # a word the shell computes before `push` can be the command itself, or split into words that run
                # another push first: `$G push`, `timeout 5 $(echo git) push`, `sudo -u $U git push`, `git -C $D push`
                return _computed_reason(f"`{word}` before `push`")
        for k, tok in enumerate(seg):
            name = os.path.basename(tok)
            if GIT_ENV_RE.match(tok):
                key, value = tok.split("=", 1)
                state["git_env"] = f"sets `{key}`"  # GIT_DIR=… / export GIT_WORK_TREE=… picks another repository
                if key.startswith("GIT_CONFIG") and re.search(r"push|!|[$`]", value):
                    return _computed_reason(f"`{key}` (git configuration set through the environment)")
            elif name in ("cd", "pushd") and _command_position(seg, k):
                args = [a for a in seg[k + 1:] if not a.startswith("-") or a == "-"]
                dirs.append(os.path.expanduser("~") if not args else _resolve_dir(args[0], dirs[-1]))
            elif name in SHELLS:
                script = _shell_command(seg[k + 1:])  # `bash -c "…"`, `bash -lc "…"`, `sh -c -- "…"`
                if script is not None:
                    reason = inspect_command(script, cwd, depth + 1, state)
                    if reason:
                        return reason
            elif name == "eval":
                reason = inspect_command(" ".join(seg[k + 1:]), cwd, depth + 1, state)
                if reason:
                    return reason
            elif name == "gh" and seg[k + 1:k + 3] in (["pr", "checkout"], ["repo", "clone"]):
                state["head"] = ("moved", "gh " + " ".join(seg[k + 1:k + 3]))
            elif name == "git":
                found = _git_invocation(seg, k)
                if not found:
                    continue
                argv, cdirs, unknown, computed = found
                if any(ch in argv[0] for ch in COMPUTED_CHARS):  # `git $C origin main`, `git {push,} origin main`
                    return _computed_reason(f"git subcommand `{argv[0]}`")
                cdirs = _wrapper_chdirs(seg, k) + cdirs
                unknown = unknown or state["git_env"]
                if argv[0] != "push":
                    change = _branch_change(argv)
                    if change and change[0] == "created" and (cdirs or unknown or dirs != [cwd]):
                        change = ("moved", f"git {argv[0]}")  # made in a directory other than the session's
                    if change:
                        state["head"] = change
                    continue
                if any(os.path.basename(t) == "xargs" for t in seg[:k]):
                    computed = computed or "arguments xargs appends"  # `echo main | xargs git push origin`
                head = state["head"]
                if head and head[0] == "moved":
                    unknown = unknown or f"follows `{head[1]}` in the same command"
                push_dirs = list(dirs)
                for c in cdirs:  # each -C is relative to the previous one, as in git
                    push_dirs = [_resolve_dir(c, d) for d in push_dirs]
                if cdirs:
                    # never weaker than the shell's own directories: `$(git branch --show-current)` runs there
                    push_dirs = push_dirs + list(dirs)
                if unknown:
                    push_dirs = [None]
                created = head[1] if head and head[0] == "created" else None
                reason = _push_reason(argv, push_dirs, unknown, computed, cwd, created,
                                      single=not cdirs and dirs == [cwd])
                if reason:
                    return reason
    for body in subs:  # after the commands around them, so a branch switch in a substitution counts conservatively
        reason = inspect_command(body, cwd, depth + 1, state)
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
        # a fault in the guard must not let a push through (independent review: an exception allowed one)
        reason = ("block_protected_push: the guard could not check this command and it mentions push; run the push "
                  "yourself or simplify the command." if re.search(r"\bpush\b", cmd) else None)
    if reason:
        deny(reason)
    sys.exit(0)


if __name__ == "__main__":
    main()
