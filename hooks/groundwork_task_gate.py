#!/usr/bin/env python3
"""Groundwork task hook — native OpenSpec stays the workflow; this adds tracking, evidence and authorization
(openspec/changes/add-task-lifecycle-gate/).

  UserPromptSubmit     automatic, lightweight task intake (groundwork_tasks.intake): engineering prompts are
                       recorded; MATERIAL work gets its OpenSpec change and plain guidance; known keys get status
  PreToolUse           sensitive actions — cloud, cluster, production or data changes, deletes outside the working
                       tree, discarding Git history or work, credential access, elevated privileges, Groundwork's own
                       hooks and settings, commands that cannot be checked — return Claude Code's native "ask", so
                       the user authorizes them in the normal permission prompt. Everything else is untouched.
  PostToolUse          evidence for open tasks: declared verification commands, review results, sensitive
  PostToolUseFailure   operations, and completion when the change is archived natively

No approval codes, no scope gate: plans and implementation can be revised at any time. Fail-open: an unreadable
input or a missing module never blocks work; an internal error while checking a command asks the user.
Kill switch: GROUNDWORK_TASK_GATE=off in settings.json env.

Not a sandbox (docs/TASK-LIFECYCLE.md): programs such as Python are not inspected; shell commands and scripts run
directly are.
"""
import json
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import groundwork_tasks as gt
except Exception:  # partial install: fail open
    sys.exit(0)
try:
    from require_material_review import is_review_call, parse_review_result  # reused, not copied
except Exception:
    def is_review_call(name, tool_input):
        target = " ".join(str((tool_input or {}).get(f, "") or "") for f in ("subagent_type", "name"))
        return name in ("Agent", "Task") and re.search(r"(?<![a-zA-Z])review", target, re.I) is not None

    def parse_review_result(text):
        return {}

FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "NotebookRead", "Grep"}
COMMAND_TOOLS = {"Bash", "Monitor"}

# ---------------------------------------------------------------------------------------------- shell parsing

SEPARATORS = {";", "&&", "||", "|", "&", "|&", "\n", "(", ")", ";;"}
REDIRECT_RE = re.compile(r"^(?:&>>?|>>?|>\||>&|<<<|<<-?|<&|<>|<)$")
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
DEV_SINKS = {"/dev/null", "/dev/stdout", "/dev/stderr"}

ALWAYS_RO = {"ls", "cat", "head", "tail", "wc", "grep", "egrep", "fgrep", "rg", "stat", "file", "pwd", "echo",
             "printf", "which", "type", "tree", "du", "df", "date", "uname", "whoami", "id", "hostname", "basename",
             "dirname", "realpath", "readlink", "sort", "uniq", "cut", "tr", "diff", "cmp", "md5sum", "sha1sum",
             "sha256sum", "shasum", "jq", "test", "[", "true", "false", "printenv", "column", "nl", "ps", "uptime",
             "nproc", "free", "cd", "comm", "fold", "fmt", "rev", "seq"}
GCLOUD_WRITE = {"create", "delete", "update", "patch", "set", "deploy", "start", "stop", "reset", "resize", "ssh",
                "scp", "import", "export", "move", "apply", "enable", "disable", "attach-disk", "detach-disk",
                "rollback", "undelete", "suspend", "resume", "replace", "submit", "run", "execute", "cancel",
                "set-iam-policy", "add-iam-policy-binding", "remove-iam-policy-binding", "print-access-token",
                "activate-service-account", "login", "revoke"}
KUBECTL_WRITE = {"apply", "create", "delete", "replace", "patch", "scale", "rollout", "drain", "cordon", "uncordon",
                 "edit", "set", "label", "annotate", "taint", "expose", "run", "exec", "cp", "autoscale",
                 "attach", "port-forward", "debug"}
# Prefixes that run the command after them; unwrapped before the sensitivity check (found by independent review:
# `sudo gcloud … delete`, `watch kubectl delete …`, `setsid terraform destroy` were not classified as sensitive).
RUN_WRAPPERS = {"sudo": {"-u", "-g", "-C", "-h", "-p", "-U", "-r", "-t", "-D", "-T", "-R", "--user", "--group",
                         "--close-from", "--host", "--prompt", "--other-user", "--role", "--type", "--chdir", "--chroot",
                         "--command-timeout"},
                "doas": {"-u", "-C"},
                "watch": {"-n", "--interval"}, "setsid": set(),
                "ionice": {"-c", "-n", "-p", "-P", "-u", "--class", "--classdata", "--pid", "--pgid", "--uid"},
                "chrt": set(), "taskset": set(), "unbuffer": set()}
RUN_WRAPPER_POSITIONALS = {"chrt": 1, "taskset": 1}  # chrt PRIORITY cmd …, taskset MASK cmd …
MAX_DEPTH = 6  # nested shells, scripts, substitutions and here-documents checked before failing closed
DB_CLIENTS = {"psql", "mysql", "sqlplus", "mongosh", "mongo", "redis-cli", "cqlsh", "sqlcmd", "sqlite3"}


# Shell operators, longest first. shlex returns a run of adjacent operator characters as one token ("&&\n", ";\n",
# ")&&"), so runs are split into these (found by independent review: the line after `&&⏎` joined the previous command).
OPERATORS = ("&>>", "<<<", "<<-", "&&", "||", ";;", "|&", "&>", ">>", ">&", "<&", ">|", "<>", "<<", ";", "|", "&",
             "(", ")", "<", ">", "\n")
OPERATOR_CHARS = "();<>|&\n"
COMMENT_AFTER = " \t\r\n;&|()<>"  # a `#` that starts a word (at the start or after one of these) begins a comment
# Quoted or escaped operator characters (and blanks inside ${…}) are literal text. They are encoded as private-use
# characters before lexing and decoded in the argv, so `grep '||'`, `cut -d '|'` and `find … \;` keep them as
# arguments and `rm '&&' -rf dir` is not split into `rm` and `-rf dir` (found by independent review).
_ENCODED = {c: chr(0xE000 + k) for k, c in enumerate(OPERATOR_CHARS + " \t")}
_DECODE = str.maketrans({v: k for k, v in _ENCODED.items()})
HEREDOC_MARK = "\ue0ff"  # prefixes a here-document delimiter so split_segments can tie each body to its command


def _encode(text: str) -> str:
    return "".join(_ENCODED.get(ch, ch) for ch in text)


def _heredoc_delimiter(cmd: str, j: int):
    """(delimiter, index after it, quoted) for the word after `<<`/`<<-` at j, or None when it is not a here-document
    delimiter this parser accepts (it must start with a letter, `_`, a quote or a backslash; `1<<2` is arithmetic)."""
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


def _scan_braced(cmd: str, j: int) -> int | None:
    """Index just past the `}` closing a `${` whose body starts at j; quotes and escapes inside are honoured
    (found by independent review: `${x:-'{'}` must not swallow later commands). None when unclosed."""
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


def _scan_arithmetic(cmd: str, j: int) -> int | None:
    """Index just past the `))` closing an arithmetic `((` whose body starts at j, or None when the parentheses do
    not close as `))` (then it is nested subshells, `((cd a); ls)`, and is parsed as such)."""
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


def _matching_paren(text: str, j: int) -> int | None:
    """Index of the `)` closing a group whose body starts at j, honouring quotes, escapes and here-document bodies
    inside it (found by independent review: `"$(cat <<'EOF' … don't … EOF)"`, the usual commit-message form, must
    not read the apostrophe as a quote)."""
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
                    line = text[j:k].rstrip("\r")
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


def _expansions(text: str, subs: list[str]) -> bool:
    """Record the `$(…)` and backtick bodies in text where quotes are literal (double-quoted text, an unquoted
    here-document body, `${…}`, `$((…))`). False when one is not closed."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
        elif text.startswith("$((", i):
            i += 3  # arithmetic: keep scanning inside it for a nested $(…)
        elif text.startswith("$(", i):
            j = _matching_paren(text, i + 2)
            if j is None:
                return False
            subs.append(text[i + 2:j])
            i = j + 1
        elif c == "`":
            j = i + 1
            while j < n and text[j] != "`":
                j += 2 if text[j] == "\\" else 1
            if j >= n:
                return False
            subs.append(text[i + 1:j])
            i = j + 1
        else:
            i += 1
    return True


def _scan_test(cmd: str, j: int) -> int | None:
    """Index just past the `]]` closing a `[[` test whose body starts at j (quotes and escapes honoured), or None."""
    n = len(cmd)
    while j < n:
        ch = cmd[j]
        if ch == "\\":
            j += 2
        elif ch in "'\"":
            k = j + 1
            while k < n and cmd[k] != ch:
                k += 2 if ch == '"' and cmd[k] == "\\" else 1
            if k >= n:
                return None
            j = k + 1
        elif cmd.startswith("]]", j) and cmd[j - 1] in " \t" and (j + 2 == n or cmd[j + 2] in " \t\r\n;&|)"):
            return j + 2
        else:
            j += 1
    return None


def _prepare_command(cmd: str) -> tuple[str, list[str], list[str]] | None:
    """Quote-aware pass before shlex, matching bash where it matters to the gate. Returns (text, here-doc bodies,
    command-substitution bodies); the substitutions are what bash would run (see substitutions()).
    - quoted or escaped operator characters are literal (encoded, see _ENCODED); `\⏎` is a line continuation;
    - a `#` that starts a word begins a comment, removed up to (not including) the newline; elsewhere (`a#b`,
      `a\ #b`, `${x#y}`, `$#`) it is literal;
    - `${…}`, `$((…))` and `((…))` are one word each; `<<<` is a here-string;
    - here-document bodies are taken out of the text (they are data for the command, returned separately so the
      caller can still check them; found by independent review).
    None when the command cannot be checked: an unbalanced quote or `${`, a here-document without its terminator,
    `$'…'` / `$"…"` quoting (shlex does not decode it), or a private-use character used by the encoding."""
    if any(ch in _DECODE for ch in map(ord, cmd)) or HEREDOC_MARK in cmd:
        return None
    out, i, n, boundary, heredocs, bodies, subs = [], 0, len(cmd), True, [], [], []
    while i < n:
        c = cmd[i]
        if c == "\\":
            nxt = cmd[i + 1:i + 2]
            if nxt == "\n":
                i += 2  # continuation: the word goes on, `boundary` unchanged
                continue
            out.append(_ENCODED[nxt] if nxt and nxt in OPERATOR_CHARS else cmd[i:i + 2])
            i, boundary = i + 2, False
        elif c == "#" and boundary:
            j = cmd.find("\n", i)
            i = n if j < 0 else j
        elif c == "$" and cmd[i + 1:i + 2] in ("'", '"'):
            return None
        elif c == "$" and cmd[i + 1:i + 2] == "{":
            j = _scan_braced(cmd, i + 2)
            if j is None:
                return None
            if not _expansions(cmd[i + 2:j], subs):
                return None
            out.append("${" + _encode(cmd[i + 2:j]))
            i, boundary = j, False
        elif (c == "$" and cmd.startswith("$((", i) and _scan_arithmetic(cmd, i + 3)) or \
                (c == "(" and boundary and cmd.startswith("((", i) and _scan_arithmetic(cmd, i + 2)):
            j = _scan_arithmetic(cmd, i + (3 if c == "$" else 2))
            if not _expansions(cmd[i:j], subs):
                return None
            out.append(_encode(cmd[i:j]))  # arithmetic: `<<` is a shift, not a here-document
            i, boundary = j, False
        elif c == "[" and boundary and cmd.startswith("[[", i) and cmd[i + 2:i + 3] in (" ", "\t") and \
                _scan_test(cmd, i + 3):
            j = _scan_test(cmd, i + 3)  # `[[ a && b ]]` is one test, not two commands (found by independent review)
            if not _expansions(cmd[i:j], subs):
                return None
            out.append(_encode(cmd[i:j]))
            i, boundary = j, False
        elif c == "$" and cmd[i + 1:i + 2] == "(":
            j = _matching_paren(cmd, i + 2)
            if j is None:
                return None
            subs.append(cmd[i + 2:j])  # also parsed in place below, as before
            out.append(c)
            i, boundary = i + 1, False
        elif c == "`":
            j = i + 1
            while j < n and cmd[j] != "`":
                j += 2 if cmd[j] == "\\" else 1
            if j >= n:
                return None
            subs.append(cmd[i + 1:j])
            out.append(_encode(cmd[i:j + 1]))
            i, boundary = j + 1, False
        elif c in "<>" and cmd[i + 1:i + 2] == "(":
            j = _matching_paren(cmd, i + 2)
            if j is None:
                return None
            subs.append(cmd[i + 2:j])  # process substitution: its commands are checked as a substitution, and
            out.append("/dev/fd/63")    # the word is a pipe path, so `bash <(curl …)` reads unseen input
            i, boundary = j + 1, False
        elif c in "'\"":
            j = i + 1
            while j < n and cmd[j] != c:
                if c == "'":
                    j += 1
                elif cmd[j] == "\\":
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
            body = cmd[i + 1:j]
            if c == '"':
                body = body.replace("\\\n", "")
                if not _expansions(body, subs):
                    return None
            out.append(c + _encode(body) + c)
            i, boundary = j + 1, False
        elif cmd.startswith("<<<", i):
            out.append("<<<")  # a here-string, not a here-document (found by independent review)
            i, boundary = i + 3, True
        elif cmd.startswith("<<", i):
            strip = cmd.startswith("<<-", i)
            j = i + (3 if strip else 2)
            found = _heredoc_delimiter(cmd, j)
            if found:
                heredocs.append((found[0], strip, found[2]))
                out.append("<< " + HEREDOC_MARK + _encode(found[0]) + " ")  # body taken out below; `-` no longer matters
                i, boundary = found[1], False
            else:
                out.append(cmd[i:j])
                i, boundary = j, True
        elif c == "\n":
            out.append(c)
            i, boundary = i + 1, True
            for delim, strip, quoted in heredocs:  # the bodies start after this newline, one after another
                lines = []
                while True:
                    if i >= n:
                        return None
                    j = cmd.find("\n", i)
                    j = n if j < 0 else j
                    line = cmd[i:j].rstrip("\r")
                    i = min(j + 1, n)
                    if (line.lstrip("\t") if strip else line) == delim:
                        break
                    lines.append(line)
                bodies.append("\n".join(lines))
                if not quoted and not _expansions(bodies[-1], subs):  # unquoted delimiter: the body is expanded
                    return None
            heredocs = []
        else:
            out.append(c)
            i, boundary = i + 1, c in COMMENT_AFTER
    if heredocs:
        return None
    return "".join(out), bodies, subs


def _split_operators(tok: str) -> list[str]:
    if not tok or any(ch not in OPERATOR_CHARS for ch in tok):
        return [tok]
    parts, k = [], 0
    while k < len(tok):
        op = next(o for o in OPERATORS if tok.startswith(o, k))
        parts.append(op)
        k += len(op)
    return parts


def split_segments(cmd: str):
    """[{argv, writes, prev, next}] for each simple command, or None when the command cannot be parsed.
    `writes`: an output redirection to a real file (also with no command, `> f`). prev/next: the operator
    before/after the segment; a newline after an operator (`a ||⏎b`) does not replace it."""
    prepared = _prepare_command(cmd)
    if prepared is None:
        return None
    try:
        lex = shlex.shlex(prepared[0], posix=True, punctuation_chars=OPERATOR_CHARS)
        lex.whitespace = " \t\r"
        lex.whitespace_split = True
        lex.commenters = ""  # comments were removed by _prepare_command; shlex's own would swallow the newline
        tokens = [part for tok in lex for part in _split_operators(tok)]
    except ValueError:
        return None
    segments, cur, writes, targets, docs, prev, n_docs = [], [], False, [], [], None, 0
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in SEPARATORS:
            if cur or writes or docs:
                segments.append({"argv": cur, "writes": writes, "targets": targets, "heredocs": docs, "prev": prev,
                                 "next": tok})
                prev = tok
            elif tok != "\n" or prev is None:
                prev = tok
            cur, writes, targets, docs = [], False, [], []
        elif REDIRECT_RE.match(tok):
            target = (tokens[i + 1] if i + 1 < len(tokens) else "").translate(_DECODE)
            if tok == "<<" and target.startswith(HEREDOC_MARK):
                docs.append(n_docs)  # index into _prepare_command's bodies
                n_docs += 1
            if (tok.startswith((">", "&>")) or tok == "<>") and not (tok == ">&" and target.isdigit()) \
                    and target not in DEV_SINKS:
                writes = True
                targets.append(target)
            i += 1  # skip the redirection target / heredoc delimiter
        elif tok.isdigit() and i + 1 < len(tokens) and REDIRECT_RE.match(tokens[i + 1]):
            pass  # the "2" in "2>&1"
        else:
            cur.append(tok.translate(_DECODE))
        i += 1
    if cur or writes or docs:
        segments.append({"argv": cur, "writes": writes, "targets": targets, "heredocs": docs, "prev": prev,
                         "next": None})
    return segments


def substitutions(cmd: str) -> list[str] | None:
    """The command text of every `$(…)`, backtick and `<(…)` / `>(…)` that bash would run for cmd: unquoted, in
    double quotes, in `${…}`, in `$((…))`, or in a here-document whose delimiter is unquoted; not in single quotes
    or a quoted-delimiter here-document, where they are text (found by independent review). None when cmd cannot
    be parsed."""
    prepared = _prepare_command(cmd)
    return prepared[2] if prepared else None


def heredoc_bodies(cmd: str) -> list[str]:
    prepared = _prepare_command(cmd)
    return prepared[1] if prepared else []


# Words that open or continue a compound command; the command after them is what runs (found by independent
# review: `if …; then terraform destroy; fi`, `do kubectl delete …`, `{ terraform apply; }`, `! terraform apply`).
RESERVED_WORDS = {"!", "{", "}", "if", "then", "elif", "else", "fi", "while", "until", "do", "done", "esac", "coproc"}


def strip_wrappers(argv: list[str]):
    """Drop env assignments and harmless wrappers. Returns (argv, had_assignments)."""
    i, assigns = 0, False
    while i < len(argv):
        t = argv[i]
        name = os.path.basename(t)
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            assigns, i = True, i + 1
        elif t in RESERVED_WORDS:
            i += 1
        elif t == "function":
            i += 2  # function NAME { … }: the body follows
        elif name in ("command", "builtin", "nohup", "time", "exec"):
            i += 1
            while i < len(argv) and argv[i].startswith("-") and name != "nohup":
                i += 1
        elif name == "env":
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 2 if argv[i] in ("-u", "--unset", "-C", "--chdir") else 1
        elif name == "nice":
            i += 1
            if i < len(argv) and argv[i] == "-n":
                i += 2
            elif i < len(argv) and argv[i].startswith("-"):
                i += 1
        elif name == "timeout":
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 2 if argv[i] in ("-s", "--signal", "-k", "--kill-after") else 1
            i += 1  # the duration
        elif name == "stdbuf":
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 1
        else:
            break
    return argv[i:], assigns


def _words(args):
    return [a for a in args if not a.startswith("-")]


def _xargs_command(args: list[str]) -> list[str]:
    """The command xargs runs: after its options, skipping the values of -I, -n, -P, … (found by independent review:
    `xargs -n 1 kubectl delete pod` was read as the command `1`)."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-I", "-n", "-P", "-L", "-d", "-E", "-s", "-a", "--max-args", "--max-procs",
                              "--max-chars", "--delimiter", "--arg-file") else 1
    return args[i:]


def unwrap_run(argv: list[str]) -> list[str]:
    """strip_wrappers() plus the prefixes in RUN_WRAPPERS (sudo, watch, setsid, …), repeatedly."""
    argv, _ = strip_wrappers(argv)
    while argv and os.path.basename(argv[0]) in RUN_WRAPPERS:
        name = os.path.basename(argv[0])
        value_flags = RUN_WRAPPERS[name]
        i = 1
        while i < len(argv) and argv[i].startswith("-"):
            flag = argv[i]
            i += 1
            if flag == "--":
                break
            if flag.startswith("--"):
                i += 1 if flag in value_flags else 0
                continue
            # a short cluster, left to right: the first value letter takes the rest of the cluster (-uroot) or, when
            # it is last, the next argument (-dn 5); found by independent review (-uroot hid `terraform apply`)
            for pos, letter in enumerate(flag[1:], 1):
                if f"-{letter}" in value_flags:
                    i += 1 if pos == len(flag) - 1 else 0
                    break
        i += RUN_WRAPPER_POSITIONALS.get(name, 0)
        argv, _ = strip_wrappers(argv[i:])
    return argv


def _shell_invocation(args: list[str]) -> tuple[str, str | None]:
    """How `sh ARGS` gets its commands: ("c", CMD) for -c (also -lc, -ec, `-o pipefail -c`, `-c -o pipefail CMD`);
    ("stdin", None) for -s or no operand; ("script", PATH) for a script file."""
    i, has_c, has_s = 0, False, False
    while i < len(args):
        a = args[i]
        if a in ("--", "-"):
            i += 1
            break
        if a.startswith("--"):
            i += 2 if a in ("--rcfile", "--init-file") else 1
            continue
        if re.match(r"^[-+][a-zA-Z]+$", a):
            # each o/O in a cluster takes the next argument as its option name: -euo pipefail, -oc pipefail,
            # -c -o pipefail (found by independent review); -c makes the first operand the command string
            if a[0] == "-":
                has_c, has_s = has_c or "c" in a, has_s or "s" in a
            i += 1 + sum(ch in "oO" for ch in a[1:])
            continue
        break
    if has_c:
        return "c", args[i] if i < len(args) else ""
    if has_s or i >= len(args) or _is_stdin_path(args[i]):
        return "stdin", None  # -s: commands come from stdin, operands are positional parameters (independent review)
    return "script", args[i]


def _is_stdin_path(path: str) -> bool:
    return path in ("/dev/stdin", "/proc/self/fd/0", "-") or path.startswith("/dev/fd/")


def _shell_command_arg(args: list[str]):
    """The command string of `sh -c CMD`; "" when the shell reads its commands from stdin; None for a script file."""
    kind, value = _shell_invocation(args)
    return value if kind == "c" else "" if kind == "stdin" else None


ELEVATORS = {"sudo", "doas", "su", "pkexec"}


def segment_sensitive(argv: list[str], cwd: str, depth: int = 0, base: str | None = None) -> str | None:
    """A label when the command needs the user's authorization: it changes cloud, cluster, production or data
    systems, deletes outside the working tree, discards Git history or work, handles credentials, runs with elevated
    privileges, or runs commands Groundwork cannot see; else None."""
    unwrapped = unwrap_run(argv)
    for w in argv[:len(argv) - len(unwrapped) + 1] if argv else []:  # the wrapper chain and the command itself
        if os.path.basename(w) in ELEVATORS:
            return f"a command run with elevated privileges ({os.path.basename(w)})"
    argv = unwrapped
    if not argv:
        return None
    name, args = os.path.basename(argv[0]), argv[1:]
    words = _words(args)
    found = _credential_access(name, words, args)
    if found:
        return found
    if "`" in argv[0]:
        return "a command whose name comes from a command substitution (it cannot be checked)"
    if name == "eval":
        if any("$" in a or "`" in a for a in args):
            return "eval of a variable or command output (it cannot be checked)"
        return command_sensitive(" ".join(args), cwd, depth + 1, base) if depth < MAX_DEPTH else "a deeply nested eval"
    if name == "trap" and args and not args[0].startswith("-") and depth < MAX_DEPTH:
        return command_sensitive(args[0], cwd, depth + 1, base)
    if name in SHELLS:
        kind, value = _shell_invocation(args)
        if kind == "stdin" or (kind == "c" and value == ""):
            return "commands piped into a shell (they cannot be checked)"
        if kind == "c" and value.lstrip().startswith(("$(", "`")):
            return "a shell running downloaded or computed commands (they cannot be checked)"
        if kind == "c":
            return command_sensitive(value, cwd, depth + 1, base) if depth < MAX_DEPTH else "a deeply nested shell"
        return _script_sensitive(value, cwd, depth)
    if name in ("source", ".") and words:
        if _is_stdin_path(words[0]):
            return "commands piped into a shell (they cannot be checked)"
        return _script_sensitive(words[0], cwd, depth, sourced=True)
    if name == "claude":
        return "a nested Claude Code session"
    if name == "find" and depth < MAX_DEPTH:
        for k, flag in enumerate(args):  # every -exec clause, not only the first (found by independent review)
            if flag in ("-exec", "-execdir", "-ok", "-okdir"):
                rest = args[k + 1:]
                end = next((j for j, a in enumerate(rest) if a in (";", "+")), len(rest))
                found = segment_sensitive(rest[:end], cwd, depth + 1, base)
                if not found and "{}" in rest[:end]:  # `{}` is whatever find finds under its start points
                    roots = [a for a in args[:next((j for j, a in enumerate(args) if a.startswith(("-", "(", "!"))),
                                                  len(args))]] or ["."]
                    found = segment_sensitive([w for w in rest[:end] if w != "{}"] + [os.path.join(r, "{}") for r in roots],
                                              cwd, depth + 1, base)
                if found:
                    return f"{found} (run by find {flag})"
    if "/" in argv[0] or argv[0].endswith(".sh"):
        found = _script_sensitive(argv[0], cwd, depth)
        if found:
            return found
    if name == "xargs":
        raw = _xargs_command(args)
        rest = unwrap_run(raw)
        if rest and os.path.basename(rest[0]) in SHELLS | {"eval"}:
            return "commands built by xargs for a shell (they cannot be checked)"
        return segment_sensitive(raw, cwd, depth + 1, base) if rest and depth < MAX_DEPTH else None
    if name == "gcloud" and any(w in GCLOUD_WRITE or w.startswith(("add-", "remove-", "set-")) for w in words):
        return "a gcloud mutation"
    if name == "kubectl" and any(w in KUBECTL_WRITE for w in words):
        return "a kubectl mutation"
    if name == "terraform":
        sub = words[0] if words else ""
        if sub in ("apply", "destroy", "import", "taint", "untaint", "force-unlock") or \
                (sub == "state" and words[1:2] and words[1] in ("rm", "mv", "push", "replace-provider")) or \
                (sub == "workspace" and words[1:2] and words[1] in ("delete", "new")):
            return f"terraform {sub}"
    if name == "helm" and words and words[0] in ("install", "upgrade", "uninstall", "delete", "rollback"):
        return f"helm {words[0]}"
    if name == "aws" and len(words) >= 2:
        if words[0] == "s3":
            if words[1] in ("cp", "mv", "rm", "sync", "mb", "rb"):
                return f"aws s3 {words[1]}"
        elif not words[1].startswith(("describe", "list", "get", "wait", "help")):
            return f"an aws {words[0]} {words[1]} call"
    if name == "az" and any(w in ("create", "delete", "update", "set", "start", "stop", "restart", "deploy", "purge",
                                  "assign", "remove", "add") for w in words):
        return "an az mutation"
    if name == "gsutil" and words and words[0] in ("rm", "rb", "mb", "cp", "mv", "rsync", "setmeta", "acl", "iam",
                                                   "defacl", "lifecycle"):
        return f"gsutil {words[0]}"
    if name == "bq" and words and words[0] in ("rm", "mk", "load", "insert", "update", "cp", "query"):
        return f"bq {words[0]}"
    if name == "docker" and words and (words[0] in ("push", "rm", "rmi", "prune", "kill", "stop") or
                                       (words[0] == "system" and "prune" in words)):
        return f"docker {words[0]}"
    if name in ("ansible", "ansible-playbook"):
        return name
    if name in DB_CLIENTS:
        return f"a database client ({name})"
    if name == "rm" and any(a in ("-r", "-R", "--recursive") or re.match(r"^-[a-zA-Z]*[rR]", a) for a in args) and \
            any(_risky_delete_target(w, cwd, base) for w in words):
        return "a recursive delete of, or outside, the working directory"
    if name == "ssh":
        return "remote execution (ssh)"
    if name in ("scp", "rsync") and any(":" in w and not w.startswith(("/", "./")) for w in words):
        return f"a remote copy ({name})"
    if name == "curl":
        for i, a in enumerate(args):
            if a in ("-X", "--request") and i + 1 < len(args) and args[i + 1].upper() != "GET":
                return f"an HTTP {args[i + 1].upper()} request"
            if re.match(r"^-X(?!GET)[A-Z]+$", a) or a.startswith(("-d", "--data", "-F", "--form", "-T", "--upload-file", "--json")):
                return "an HTTP request that sends data"
    if name == "wget" and any(a.startswith(("--post-data", "--post-file", "--method", "--body-data")) for a in args):
        return "an HTTP request that sends data"
    if name == "git":
        sub_args = _git_subcommand_args(args)
        return _git_destructive(_words(sub_args), sub_args)
    return None


CREDENTIAL_PATH_RE = re.compile(
    r"(?:^|/)(?:\.ssh/|\.aws/(?:credentials|config)|\.config/gcloud/|\.kube/config|\.netrc|\.docker/config\.json|"
    r"\.npmrc|\.pypirc|\.git-credentials|\.gnupg/|\.vault-token)|(?:^|/)\.env(?:\.(?!example|sample|template)[\w.-]+)?$|"
    r"(?:^|/)id_(?:rsa|ed25519|ecdsa|dsa)(?:\.pub)?$")
# Key and certificate files by extension: only for a path-like word (no spaces; a `.key` file needs a directory), so
# `grep -rn "event.key"` or a commit message mentioning `item.key` is not credential access (found by review).
CREDENTIAL_EXT_RE = re.compile(r"^[^\s]*\.(?:pem|p12|pfx)$|^[^\s]*/[^/\s]+\.key$")


def credential_path(word: str) -> bool:
    return bool(CREDENTIAL_PATH_RE.search(word) or CREDENTIAL_EXT_RE.search(word))


CREDENTIAL_COMMANDS = {  # name -> subcommand word sequences that read, print, store or change credentials
    "gh": (("auth",),), "aws": (("configure",), ("sts", "get-session-token"), ("secretsmanager", "get-secret-value"),
                                ("ssm", "get-parameter"), ("iam", "create-access-key")),
    "gcloud": (("auth",), ("secrets", "versions", "access"), ("iam", "service-accounts", "keys")),
    "az": (("account", "get-access-token"), ("keyvault", "secret")), "vault": ((),), "op": ((),),
    "kubectl": (("get", "secret"), ("get", "secrets"), ("create", "secret"), ("config", "view")),
    "docker": (("login",),), "npm": (("login",), ("token",)), "security": (("find-generic-password",),
                                                                      ("find-internet-password",)),
    "ssh-add": ((),), "ssh-keygen": ((),),
}


def _credential_access(name: str, words: list[str], args: list[str]) -> str | None:
    """Reading, printing, storing or changing credentials (found as a requirement: credential-related actions need
    explicit authorization)."""
    for seq in CREDENTIAL_COMMANDS.get(name, ()):
        n = len(seq)
        # A one-word sequence is the subcommand; a longer one may follow global options' values
        # (`kubectl -n ns get secret`, `aws --profile p secretsmanager ...`; found by review).
        hit = words[:n] == list(seq) if n <= 1 else any(words[i:i + n] == list(seq) for i in range(len(words)))
        if hit and (name != "aws" or seq != ("ssm", "get-parameter") or "--with-decryption" in args):
            return f"credential access ({' '.join([name, *seq])})"
    if any(credential_path(a) for a in args if not a.startswith("-")):
        return f"credential access (a credential file, via {name})"
    return None


TEMP_DIRS = ("/tmp/", "/private/tmp/", "/var/tmp/", "/var/folders/")


def _risky_delete_target(word: str, cwd: str, base: str | None = None) -> bool:
    """A recursive delete target outside the session's working directory `base` (or that directory itself, or
    everything in it): unknown ($VAR, ~), absolute, or up the tree. `cwd` is where the command runs (after a `cd`);
    the boundary stays `base` (found by independent review: `cd /other && <delete> data`). base "" means a `cd`
    Groundwork could not follow, so every target is unknown. Temporary directories are ordinary scratch space."""
    base = cwd if base is None else base
    if not base or "$" in word or "`" in word or word.startswith("~"):
        return True
    if word in ("*", ".*", "./*", ".", "./", "/", "..") or word.rstrip("/") in ("", ".", ".."):
        return True
    path = os.path.normpath(word if os.path.isabs(word) else os.path.join(cwd, word))
    if path.startswith(TEMP_DIRS) or (os.environ.get("TMPDIR") and path.startswith(os.environ["TMPDIR"].rstrip("/") + "/")):
        return False
    return not path.startswith(os.path.normpath(base).rstrip("/") + "/")


GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env",
                     "--super-prefix", "--list-cmds", "--attr-source"}


def _git_subcommand_args(args: list[str]) -> list[str]:
    """git's arguments from the subcommand on: global options (`-C dir`, `-c k=v`, `--git-dir=...`, `--no-pager`)
    are skipped, so they cannot hide the subcommand (found by independent review)."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in GIT_VALUE_OPTIONS else 1
    return args[i:]


def _git_destructive(words: list[str], args: list[str]) -> str | None:
    """Git commands that discard history or uncommitted work; `git push` to a protected branch is the separate
    block_protected_push hook. `args` start at the subcommand."""
    sub = words[0] if words else ""
    if sub == "push" and any(a in ("-f", "--force", "--force-with-lease", "--mirror", "--delete", "-d")
                             or a.startswith(("--force", "+")) for a in args[1:]):
        return "a forced or deleting git push"
    if sub == "reset" and "--hard" in args:
        return "git reset --hard (discards uncommitted work)"
    if sub == "clean" and any(re.match(r"^-[a-zA-Z]*f", a) or a == "--force" for a in args):
        return "git clean (deletes untracked files)"
    if sub == "branch" and (any(re.match(r"^-[a-zA-Z]*D", a) for a in args) or (
            any(a == "--delete" or re.match(r"^-[a-zA-Z]*d", a) for a in args)
            and any(a == "--force" or re.match(r"^-[a-zA-Z]*f", a) for a in args))):
        return "git branch force-delete (discards unmerged commits)"
    if sub == "stash" and words[1:2] in (["drop"], ["clear"]):
        return f"git stash {words[1]} (discards stashed work)"
    if sub in ("checkout", "restore") and ("." in words[1:] or "--" in args and words[-1:] == ["."]) and not (
            sub == "restore" and any(a in ("--staged", "-S") for a in args) and
            not any(a in ("--worktree", "-W") for a in args)):  # `restore --staged .` only unstages
        return f"git {sub} . (discards uncommitted changes)"
    if sub in ("checkout", "switch") and any(a in ("-f", "--force", "--discard-changes") for a in args):
        return f"git {sub} --force (discards uncommitted changes)"
    if sub == "filter-branch" or (sub == "update-ref" and "-d" in args) or words[:2] == ["reflog", "expire"]:
        return f"git {' '.join(words[:2]) if sub == 'reflog' else sub} (rewrites or drops history)"
    return None


def _script_sensitive(script: str, cwd: str, depth: int, sourced: bool = False) -> str | None:
    path = script if os.path.isabs(script) else os.path.join(cwd, script)
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > 200_000:
            return None
        text = Path(path).read_text(errors="replace")
    except OSError:
        return None
    if not (sourced or path.endswith(".sh") or re.match(r"#!\S*\b(?:ba|z|k|da)?sh\b|#!\S*env\s+(?:ba|z|k|da)?sh\b", text)):
        return None
    if depth >= MAX_DEPTH:
        return f"a deeply nested script ({script})"
    found = command_sensitive(text, cwd, depth + 1)
    return f"{found} inside {script}" if found else None


VAR_REF_RE = re.compile(r"^\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?$")


def _literal_assignments(segs: list[dict]) -> dict[str, str | None]:
    """NAME -> value for assignments made in this command (`T=terraform`, `export T=…`, `local T=…`); the value is
    None when it is computed (contains `$` or a backtick)."""
    found = {}
    for s in segs:
        argv = s["argv"]
        if argv and argv[0] in ("export", "local", "declare", "typeset", "readonly"):
            argv = argv[1:]
        for tok in argv:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", tok, re.DOTALL)
            if not m:
                break
            value = m.group(2)
            default = re.match(r"^\$\{[A-Za-z_][A-Za-z0-9_]*:?-([^$`{}]*)\}$", value)  # ${TF:-terraform}
            found[m.group(1)] = default.group(1) if default else (None if ("$" in value or "`" in value) else value)
    return found


def _resolve_head(argv: list[str], assigns: dict) -> list[str] | str:
    """A command whose name is `$T` / `${T}`: when T is assigned a literal value (or `${T:-literal}`) in the same
    command, that value stands in for the name (`T=terraform; $T apply` is `terraform apply`). A computed value or
    a variable from outside the command (`"$@"`, `"$PY"`) is left as is: the gate cannot know it (found by
    independent review: stricter rules denied many ordinary scripts)."""
    lead = len(argv) - len(unwrap_run(argv))
    head = argv[lead] if lead < len(argv) else ""
    m = VAR_REF_RE.match(head)
    if not m or m.group(1) not in assigns:
        return argv
    value = assigns[m.group(1)]
    if value is None:
        return argv  # computed: like a variable from outside the command (found by independent review)
    return argv[:lead] + (value.split() or [""]) + argv[lead + 1:]


def _cd_target(argv: list[str]) -> str | None:
    """The literal directory of `cd DIR` / `pushd DIR`; "" for a target Groundwork cannot follow; None otherwise."""
    u = unwrap_run(argv)
    if not u or os.path.basename(u[0]) not in ("cd", "pushd"):
        return None
    words = [a for a in u[1:] if a not in ("-P", "-L", "-e", "-@", "--")]
    target = words[0] if words else "~"
    return "" if ("$" in target or "`" in target or target == "-") else os.path.expanduser(target)


def checked_segments(segs: list[dict], cwd: str, depth: int = 0, base: str | None = None):
    """(segment, argv as checked, label or None) for each segment: a variable command name resolved from a literal
    assignment in the same command, and scripts read in every directory a literal `cd` / `pushd` may have moved to
    (`cd scripts && ./tfa.sh`; found by independent review). Used for the typed command and for nested commands."""
    assigns = _literal_assignments(segs)
    dirs = [cwd]
    base = cwd if base is None else base  # the delete boundary stays the starting directory
    for s in segs:
        argv = _resolve_head(s["argv"], assigns)
        label = None
        for d in dirs:
            label = segment_sensitive(argv, d, depth, base)
            if label:
                break
        yield s, argv, label
        target = _cd_target(argv)
        if target == "":
            base = ""  # a cd Groundwork cannot follow: where a later delete lands is unknown
        if target:
            dirs = list(dict.fromkeys(dirs + [os.path.normpath(os.path.join(d, target)) for d in dirs]))
            if len(dirs) > 32:
                dirs = [cwd] + dirs[-31:]  # keep the start and the newest directories


def command_sensitive(cmd: str, cwd: str, depth: int = 0, base: str | None = None) -> str | None:
    segs = split_segments(cmd)
    if segs is None:
        return "a command Groundwork could not parse"
    for _s, _argv, label in checked_segments(segs, cwd, depth, base):
        if label:
            return label
    return embedded_sensitive(cmd, segs, cwd, depth)


# Programs that can create or replace a file other than through a shell redirect.
FILE_WRITERS = {"wget", "tar", "unzip", "patch", "rsync", "scp"}


GIT_TREE_WRITERS = {"checkout", "restore", "reset", "apply", "am", "pull", "merge", "stash", "switch", "clone",
                    "cherry-pick", "revert", "rebase", "mv", "worktree", "submodule"}
IN_PLACE_RE = re.compile(r"^-[A-Za-z0-9]*i|^--in-place")  # sed -i/-ri/-Ei/--in-place, perl -i/-pi/-0pi


def _written_and_run(segs: list[dict]) -> bool:
    """One command writes a file and later runs a script of that name (`cat > d.sh <<EOF … EOF; bash d.sh`,
    `curl -o d.sh URL && bash d.sh`, `sed -ri … d.sh; bash d.sh`). The gate reads a script when it runs, so one
    created or changed earlier in the same command cannot be checked first (found by independent review). Names
    are compared by basename. A writer whose targets are unknown (wget, tar, curl -O, git checkout …) counts as
    writing every relative path."""
    written, everything = set(), False
    for s in segs:
        argv = unwrap_run(s["argv"])
        name, args = (os.path.basename(argv[0]), argv[1:]) if argv else ("", [])
        words = _words(args)
        runs = None
        if name in SHELLS:
            kind, value = _shell_invocation(args)
            runs = value if kind == "script" and value else None
        elif name in ("source", ".") and words:
            runs = words[0]
        elif argv and "/" in argv[0]:
            runs = argv[0]
        if runs and (os.path.basename(runs) in written or (everything and not os.path.isabs(runs))):
            return True
        written.update(os.path.basename(t) for t in s.get("targets", []))
        if name in ("tee", "cp", "mv", "install", "ln"):
            written.update(os.path.basename(w.rstrip("/")) for w in words)
        elif name == "dd":
            written.update(os.path.basename(a[3:]) for a in args if a.startswith("of="))
        elif name in ("sed", "perl") and any(IN_PLACE_RE.match(a) for a in args):
            written.update(os.path.basename(w) for w in words)
        elif name == "curl":
            everything |= any(re.match(r"^-[a-zA-Z]*[oO]", a) or a.startswith(("--output", "--remote-name"))
                              for a in args)
        elif name in FILE_WRITERS or (name == "git" and words[:1] and words[0] in GIT_TREE_WRITERS
                                      and words[1:2] not in (["list"], ["show"])):
            everything = True
    return False


# Programs that only read a here-document as data. Any other receiver (a shell, `sudo -s`, `su`, `docker exec … sh`,
# a `while read; do eval` loop, an interpreter) may run it as commands, so its body is checked.
HEREDOC_DATA_READERS = ALWAYS_RO | {"git", "gh", "openspec", "tee", "base64", "xxd", "od", "less", "more", ":", "read",
                                    "mapfile", "readarray", "python", "python3", "node", "ruby", "perl", "php"}
CONTAINER_RUNNERS = {"docker", "podman", "kubectl", "oc", "nerdctl"}  # read stdin as data unless they exec/run


def embedded_sensitive(cmd: str, segs: list[dict], cwd: str, depth: int = 0) -> str | None:
    """Sensitive work that is not a command word of `cmd` itself: a script written and run in the same command, or
    a sensitive command in a here-document fed to something that may run it (`bash /dev/stdin <<EOF`,
    `sudo -s <<EOF`, `while read c; do eval "$c"; done <<EOF`; found by independent review). A body that does not
    parse as commands is treated as text."""
    if _written_and_run(segs):
        return "a script written and run in the same command (it cannot be checked before it runs; write it first, " \
               "then run it in a separate command)"
    subs = substitutions(cmd)
    if subs is None:
        return "an unclosed command substitution"
    if depth >= MAX_DEPTH and (subs or any(s.get("heredocs") for s in segs)):
        return "deeply nested commands"  # only when something nested is left unchecked (found by independent review)
    for body in subs:
        found = command_sensitive(body, cwd, depth + 1)
        if found:
            return f"{found} (in a command substitution)"
    bodies = heredoc_bodies(cmd)
    for s in segs:
        receiver = unwrap_run(s["argv"])
        rname = os.path.basename(receiver[0]) if receiver else ""
        if not s.get("heredocs") or rname in HEREDOC_DATA_READERS or (
                rname in CONTAINER_RUNNERS and not set(_words(receiver[1:])) & {"exec", "run", "attach", "debug"}):
            continue
        for k in s["heredocs"]:
            body = bodies[k] if k < len(bodies) else ""
            # a body that is not shell as a whole (an apostrophe in prose) is still checked line by line
            for part in ([body] if split_segments(body) is not None else body.splitlines()):
                if split_segments(part) is not None:
                    found = command_sensitive(part, cwd, depth + 1)
                    if found:
                        return f"{found} (in a here-document)"
    return None


def _norm_tokens(cmd: str) -> list[str] | None:
    try:
        return shlex.split(cmd)
    except ValueError:
        return None


def verification_status(segs, verify_cmd: str) -> str | None:
    return verification_match(segs, verify_cmd)[0]


def verification_match(segs, verify_cmd: str) -> tuple[str | None, int | None]:
    """'counted' when the declared verification command ran exactly as declared (same words; output redirection
    allowed) and its exit status is the tool's exit status: started at the beginning, after ; or && (not after ||)
    and followed only by && (found by independent review: `cmd && echo PASS || echo FAIL` exits 0 when cmd fails,
    and `cmd -k x` / `--collect-only` are not the declared run). 'masked' when it ran but its status was not
    observable or it ran with extra arguments; else None."""
    toks = _norm_tokens(verify_cmd)
    if not toks:
        return None, None
    found = None
    for k, s in enumerate(segs):
        argv = s["argv"]
        if argv[: len(toks)] != toks:
            continue
        if argv != toks:
            found = "masked"
            continue
        later_ok = all(t["prev"] == "&&" for t in segs[k + 1:])
        if s["prev"] in (None, ";", "&&", "\n") and later_ok and s["next"] in (None, "&&", "\n"):
            return "counted", k
        found = "masked"
    return found, None


def _response_text(resp) -> str:
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        content = resp.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
        return str(resp.get("result") or resp.get("text") or "")
    if isinstance(resp, list):
        return "\n".join(b.get("text", "") for b in resp if isinstance(b, dict))
    return ""


# ---------------------------------------------------------------------------------------------- output


def emit(obj) -> None:
    print(json.dumps(obj))
    sys.exit(0)


def ask(reason: str) -> None:
    """Claude Code's own permission prompt: the user authorizes or declines (in a -p run with no one to answer, the
    call is denied and Claude reads the reason)."""
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                 "permissionDecisionReason": "Groundwork: " + reason}})


def deny(reason: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": reason}})


def add_context(event: str, text: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


def under(path: str, base: Path) -> bool:
    real, b = os.path.realpath(path), os.path.realpath(str(base))
    return real == b or real.startswith(b + os.sep)


# ---------------------------------------------------------------------------------------------- events


def on_prompt(data: dict) -> None:
    prompt = str(data.get("prompt") or "")
    res = gt.intake(data.get("cwd") or os.getcwd(), prompt, str(data.get("session_id") or ""))
    if not res:
        return
    root = res["root"]
    if res["action"] == "created":
        t = res["tasks"][0]
        if t.get("tier") == gt.MATERIAL:
            risk = t.get("risk") or {}
            status = res.get("openspec") or "exists"
            create = "" if status in ("created", "exists") else (
                f" The change was not created ({status}); create it: openspec new change {t['change']}.")
            checklist = "\n".join(f"  - {c}" for c in t.get("checklist", []))
            how = "now tracks" if res.get("escalated") else "recorded"
            add_context("UserPromptSubmit", (
                f"[Groundwork] {how} {t['key']} as a MATERIAL task (risk {risk.get('level')}: "
                f"{', '.join(risk.get('categories', []))}). Its OpenSpec change is openspec/changes/{t['change']}/ "
                f"({status}).{create}\n"
                "Work the native OpenSpec way: plan the change (proposal, design, specs, tasks — /opsx:propose or the "
                "openspec-propose skill), then implement it (/opsx:apply), revising the plan whenever the work needs "
                "it. In design.md, settle the checklist below and add a ## Verification section listing the exact "
                "commands (one per line, in backticks) that prove the change works. Ask the owner only about real open "
                "decisions; otherwise proceed. Sensitive actions (cloud, cluster or production changes, deletes "
                "outside the repository, credential access) ask the owner through Claude Code's permission prompt.\n"
                f"To finish: run each verification command on its own, get an independent review (a foreground "
                f"review subagent ending with a REVIEW RESULT block), then run: {gt.task_cli()} complete {t['key']}. "
                "Archive the change natively when it is done (/opsx:archive or openspec archive).\n"
                f"Intake checklist:\n{checklist}\n"
                f"Mission, in the owner's words: {gt.clip(t.get('mission'), 400)}"))
        add_context("UserPromptSubmit", (
            f"[Groundwork] recorded {t['key']} (STANDARD): plan inline, implement and test. When done: "
            f"{gt.task_cli()} complete {t['key']}."))
    tasks = [t for t in res["tasks"] if t]
    if tasks:
        lead = ("[Groundwork] this continues the open task(s) below; no new task was recorded."
                if res.get("suppressed") else "[Groundwork task ledger]")
        add_context("UserPromptSubmit", lead + "\n" + "\n".join(gt.render(root, t) for t in tasks))


def config_paths() -> set[str]:
    cdir = gt.claude_dir()
    return {os.path.realpath(str(cdir / n)) for n in ("settings.json", "settings.local.json")}


def check_file(tool: str, path: str, cwd: str) -> None:
    """File tools: the ledger is written only by Groundwork; Groundwork's hooks and settings, project settings and
    credential files need the user's authorization."""
    if not path:
        return
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    if tool in FILE_TOOLS and under(path, gt.tasks_root()):
        deny("Groundwork: the task ledger is written only by Groundwork (it holds the evidence for each task).")
    if tool in FILE_TOOLS and (under(path, gt.claude_dir() / "hooks") or os.path.realpath(path) in config_paths()
                               or re.search(r"(^|/)\.claude/settings(\.local)?\.json$", path)):
        ask("this edits Claude Code settings or Groundwork's hooks (it can change what is checked).")
    if credential_path(path):
        ask(f"this {'reads' if tool in READ_TOOLS else 'changes'} a credential file ({os.path.basename(path)}).")


PROTECTED_TEXT = ("disableAllHooks", "GROUNDWORK_TASK_GATE", "groundwork/tasks")


def check_command(cmd: str, cwd: str) -> None:
    segs = split_segments(cmd)
    if segs is None:
        ask("this command could not be parsed, so Groundwork cannot tell what it does.")
    for _s, _argv, label in checked_segments(segs, cwd):
        if label:
            ask(f"{label}.")
    label = embedded_sensitive(cmd, segs, cwd)
    if label:
        ask(f"{label}.")
    if _touches_protected(segs, cmd):
        ask("this command touches Claude Code settings, Groundwork's hooks or the task ledger.")


PROTECTED_READERS = {"cat", "ls", "grep", "rg", "head", "tail", "jq", "less", "wc", "diff", "stat", "file", "echo",
                     "printf", "test", "[", "realpath", "readlink", "dirname", "basename"}


def _task_cli(argv: list[str]) -> bool:
    """Groundwork's own task CLI (`groundwork task …`, or python3 running the installed groundwork_tasks.py): it
    writes the ledger only through its own checks, so running it never asks (found in the live run)."""
    if argv[:2] == ["groundwork", "task"]:
        return True
    if len(argv) >= 2 and os.path.basename(argv[0]).startswith("python"):
        script = os.path.realpath(os.path.expanduser(os.path.expandvars(argv[1])))
        return script in {os.path.realpath(str(gt.claude_dir() / "hooks" / "groundwork_tasks.py")),
                          os.path.realpath(gt.__file__)}
    return False


def _touches_protected(segs: list[dict], cmd: str) -> bool:
    """A command that may change Claude Code settings, Groundwork's hooks or the task ledger: a segment that names
    one of them (in its words, redirect targets or here-document) and is not a plain reader or the task CLI. After
    `cd` into one of them, every later segment counts as naming it."""
    cdir = str(gt.claude_dir())
    markers = PROTECTED_TEXT + (cdir + "/settings", cdir + "/hooks", cdir + "/groundwork", "~/.claude/settings",
                                "~/.claude/hooks", ".claude/settings")
    bodies = heredoc_bodies(cmd)
    inside = False
    for s in segs:
        argv = unwrap_run(s["argv"]) or s["argv"]
        text = os.path.expandvars(" ".join(s["argv"] + s["targets"] + [bodies[i] for i in s["heredocs"] if i < len(bodies)]))
        named = inside or any(m in text for m in markers)
        if argv[:1] in (["cd"], ["pushd"]):
            target = os.path.expanduser(os.path.expandvars(_words(argv[1:])[0])) if _words(argv[1:]) else ""
            inside = inside or named or (bool(target) and under(target, Path(cdir)))
            continue
        if named and (s["writes"] or ((os.path.basename(argv[0]) if argv else "") not in PROTECTED_READERS
                                      and not _task_cli(argv))):
            return True
    return False


def on_pre(data: dict) -> None:
    tool = str(data.get("tool_name") or "")
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    cwd = data.get("cwd") or os.getcwd()
    try:
        if tool in FILE_TOOLS or tool in READ_TOOLS:
            check_file(tool, str(ti.get("file_path") or ti.get("notebook_path") or ti.get("path") or ""), cwd)
        elif tool in COMMAND_TOOLS and isinstance(ti.get("command"), str):
            check_command(ti["command"], cwd)
        elif tool == "PowerShell" and isinstance(ti.get("command"), str):
            ask("PowerShell commands are not parsed, so Groundwork cannot tell what this one does.")
    except SystemExit:
        raise
    except Exception as exc:
        ask(f"an internal error stopped the check of this call ({type(exc).__name__}); confirm it yourself.")


def on_post(data: dict) -> None:
    tool = str(data.get("tool_name") or "")
    event = str(data.get("hook_event_name") or "PostToolUse")
    if tool not in COMMAND_TOOLS and tool not in ("Agent", "Task"):
        return
    cwd = data.get("cwd") or os.getcwd()
    root = gt.repo_root(cwd)
    if not root:
        return
    tasks = gt.open_tasks(root)
    if not tasks:
        return
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    notes = []
    if isinstance(ti.get("command"), str):
        segs = split_segments(ti["command"]) or []
        resp = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
        ok = event == "PostToolUse" and not resp.get("interrupted")
        detail = str(data.get("error") or "").splitlines()[0] if not ok and data.get("error") else ""
        # A background command has only started when this fires: never evidence of a verification result.
        evidence = tool == "Bash" and not ti.get("run_in_background")
        # Evidence is recorded in the order the command ran it, so a verification counts only when it ran after the
        # last sensitive operation; a sensitive command that is itself a declared verification (`psql …`, `ssh …`)
        # is not an operation, and reading credentials changes nothing (found by independent review).
        plans = {t["key"]: (gt.read_plan(root, t)["verify"] if evidence and t.get("change") else []) for t in tasks}
        declared = [toks for v in {v for vs in plans.values() for v in vs} if (toks := _norm_tokens(v))]
        events = []
        for t in tasks:
            for v in plans[t["key"]]:
                status, k = verification_match(segs, v)
                if status == "counted":
                    events.append((k, 1, t, v))
                elif status == "masked":
                    notes.append(f"{t['key']}: `{v}` ran with extra arguments, piped or chained, so it does not count "
                                 "as the declared verification. Run it exactly as declared, on its own.")
        for k, (seg, argv, label) in enumerate(checked_segments(segs, cwd)):
            if label and not label.startswith("credential access") and seg["argv"] not in declared:
                events.append((k, 0, None, " ".join(argv)))
        ops = 0
        for _k, _order, t, what in sorted(events, key=lambda e: (e[0], e[1])):
            if t is not None:
                gt.record_verification(root, t["key"], what, ok, detail)
                notes.append(f"{t['key']}: verification `{what}` recorded as {'PASSED' if ok else 'FAILED'}.")
            elif ops < 3:
                ops += 1
                for task in tasks:
                    if task.get("tier") == gt.MATERIAL:
                        gt.record_operation(root, task["key"], what)
                notes.append(f"sensitive operation recorded (`{gt.clip(what, 80)}`); verification counts only after it.")
        if ok and "archive" in ti["command"]:
            # Native archive (openspec archive, or the /opsx:archive move into openspec/changes/archive/) completes
            # the task when its evidence is in place.
            for t in tasks:
                if t.get("change") and gt.is_archived(root, t):
                    done, msg = gt.complete(root, t["key"])
                    notes.append(f"{t['key']}: change archived; " + (msg.splitlines()[0] if done else
                                 "not complete yet — " + "; ".join(m.strip(" -") for m in msg.splitlines()[1:3])))
    if tool in ("Agent", "Task") and is_review_call(tool, ti):
        resp = data.get("tool_response")
        if isinstance(resp, dict) and resp.get("status") not in (None, "completed"):
            notes.append(f"A review that has not finished ({resp.get('status')}) is not captured as evidence; run the "
                         "review in the foreground so its result is returned.")
        else:
            result = parse_review_result(_response_text(resp))
            reviewer = str(ti.get("subagent_type") or ti.get("name") or "reviewer")
            for t in tasks:
                gt.record_review(root, t["key"], reviewer, result)
            mf = result.get("must_fix", 0 if result.get("verdict") == "approve" else None)
            notes.append(f"Review by {reviewer} recorded: " + ("no REVIEW RESULT block found, so it cannot count "
                         "toward completion." if mf is None else f"{mf} MUST FIX finding(s)."))
    if notes:
        add_context(event, "[Groundwork] " + " ".join(notes))


def main() -> None:
    if os.environ.get("GROUNDWORK_TASK_GATE", "").lower() == "off":
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError
    except Exception:
        sys.exit(0)
    event = data.get("hook_event_name")
    try:
        if event == "UserPromptSubmit":
            on_prompt(data)
        elif event == "PreToolUse":
            on_pre(data)  # asks the user itself on an internal error
        elif event in ("PostToolUse", "PostToolUseFailure"):
            on_post(data)
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    sys.exit(0)


if __name__ == "__main__":
    main()
