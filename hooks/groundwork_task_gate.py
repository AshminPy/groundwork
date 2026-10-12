#!/usr/bin/env python3
"""Groundwork task gate — one hook script, five Claude Code events (openspec/changes/add-task-lifecycle-gate/).

  UserPromptSubmit     deterministic task intake (groundwork_tasks.intake); a prompt naming a known task key gets
                       that task's state; plain-text "approve …" is answered with "not an approval"
  UserPromptExpansion  the ONLY place an approval or cancellation is recorded: the owner typed /gw-approve or
                       /gw-cancel (this event fires for typed commands, never for Claude's Skill tool calls)
  PreToolUse           the execution gate for every MATERIAL task in planning / awaiting-approval / approved
  PostToolUse          evidence (approved verification commands, review results, sensitive operations) and the
  PostToolUseFailure   git scope audit after every Bash / Agent / MCP call

Fail-open when no gated task exists or the input is unreadable (a broken guard must not take over sessions that
have nothing to gate); fail-CLOSED (deny) on an internal error while a gated task is active. Owner kill switch:
GROUNDWORK_TASK_GATE=off in settings.json env (Claude cannot change a hook's environment, and settings edits are
denied while a task is gated).

Known limits (docs/TASK-LIFECYCLE.md): this is not a sandbox against a deliberately adversarial same-user process —
code run with the user's permissions can write the ledger. Sensitive operations inside programs (python, node, …)
are not inspected; shell scripts run directly are scanned line by line. Side effects outside the repository are
covered only by the sensitive-command list.
"""
import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import groundwork_tasks as gt
except Exception:  # partial install: nothing can be known about tasks -> fail open
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
READ_TOOLS = {"Read", "Grep", "Glob", "LS", "NotebookRead", "WebFetch", "WebSearch", "ToolSearch", "TaskList",
              "TaskGet", "TaskOutput"}
OWNER_CMD_RE = re.compile(r"gw-(?:approve|cancel)", re.IGNORECASE)
TASK_SUBS = {"list", "status", "show", "intake", "request-approval", "complete", "block", "-h", "--help"}

# ---------------------------------------------------------------------------------------------- shell parsing

SEPARATORS = {";", "&&", "||", "|", "&", "|&", "\n", "(", ")", ";;"}
REDIRECT_RE = re.compile(r"^(?:&>>?|>>?|>\||>&|<<<|<<-?|<&|<>|<)$")
UNSAFE_SUBSTRINGS = ("$(", "`", "<(", ">(")
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
DEV_SINKS = {"/dev/null", "/dev/stdout", "/dev/stderr"}
PROTECTED_MARKERS = (".claude/settings", ".claude/hooks", "groundwork/tasks", "disableAllHooks", "groundwork_task_gate",
                     "groundwork_tasks.py", "commands/gw-", "GROUNDWORK_TASK_GATE")

ALWAYS_RO = {"ls", "cat", "head", "tail", "wc", "grep", "egrep", "fgrep", "rg", "stat", "file", "pwd", "echo",
             "printf", "which", "type", "tree", "du", "df", "date", "uname", "whoami", "id", "hostname", "basename",
             "dirname", "realpath", "readlink", "sort", "uniq", "cut", "tr", "diff", "cmp", "md5sum", "sha1sum",
             "sha256sum", "shasum", "jq", "test", "[", "true", "false", "printenv", "column", "nl", "ps", "uptime",
             "nproc", "free", "cd", "comm", "fold", "fmt", "rev", "seq"}
GIT_RO = {"status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree", "blame", "grep", "describe",
          "shortlog", "cat-file", "merge-base", "name-rev", "for-each-ref", "rev-list", "show-ref", "help",
          "version", "whatchanged", "annotate", "count-objects", "check-ignore", "var", "show-branch"}
OPENSPEC_RO = {"list", "show", "status", "validate", "instructions", "view", "templates", "schemas", "new",
               "--version", "-V", "--help", "-h", "help"}
GCLOUD_READ = {"list", "describe", "get-iam-policy", "get-value", "info", "version", "help", "get"}
GCLOUD_WRITE = {"create", "delete", "update", "patch", "set", "deploy", "start", "stop", "reset", "resize", "ssh",
                "scp", "import", "export", "move", "apply", "enable", "disable", "attach-disk", "detach-disk",
                "rollback", "undelete", "suspend", "resume", "replace", "submit", "run", "execute", "cancel",
                "set-iam-policy", "add-iam-policy-binding", "remove-iam-policy-binding", "print-access-token",
                "activate-service-account", "login", "revoke"}
KUBECTL_READ = {"get", "describe", "logs", "top", "explain", "version", "api-resources", "api-versions",
                "cluster-info", "diff"}
KUBECTL_WRITE = {"apply", "create", "delete", "replace", "patch", "scale", "rollout", "drain", "cordon", "uncordon",
                 "edit", "set", "label", "annotate", "taint", "expose", "run", "exec", "cp", "autoscale",
                 "attach", "port-forward", "debug"}
TERRAFORM_READ = {"plan", "validate", "show", "output", "version", "providers", "graph"}
HELM_READ = {"list", "ls", "status", "get", "show", "template", "lint", "version", "history", "search", "env"}
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


def git_read_only(args: list[str]) -> bool:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i].startswith(("-c", "--exec-path", "--config-env")):
            return False  # -c core.pager=… / core.fsmonitor=… can execute commands
        i += 2 if args[i] in ("-C", "--git-dir", "--work-tree", "--namespace") else 1
    if i >= len(args):
        return True
    sub, rest = args[i], args[i + 1:]
    if any(a.startswith(("--output", "--ext-diff", "--textconv", "--upload-pack", "--exec")) for a in rest):
        return False
    if sub in GIT_RO:
        return True
    positional = _words(rest)
    if sub == "branch":
        return not positional or "--list" in rest or "-l" in rest or (
            any(a in ("--contains", "--merged", "--no-merged", "--points-at") for a in rest) and len(positional) <= 1)
    if sub == "tag":
        return not positional or "-l" in rest or "--list" in rest
    if sub == "remote":
        return not positional or positional[0] in ("show", "get-url")
    if sub == "config":
        return any(a in ("--get", "--get-all", "--list", "-l", "--get-regexp") for a in rest)
    if sub == "stash":
        return bool(positional) and positional[0] in ("list", "show")
    if sub == "worktree":
        return bool(positional) and positional[0] == "list"
    if sub == "reflog":
        return not positional or positional[0] == "show"
    return False


def installed_task_cli() -> str:
    return os.path.realpath(gt.__file__)


def _xargs_command(args: list[str]) -> list[str]:
    """The command xargs runs: after its options, skipping the values of -I, -n, -P, … (found by independent review:
    `xargs -n 1 kubectl delete pod` was read as the command `1`)."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-I", "-n", "-P", "-L", "-d", "-E", "-s", "-a", "--max-args", "--max-procs",
                              "--max-chars", "--delimiter", "--arg-file") else 1
    return args[i:]


def segment_read_only(argv: list[str], depth: int = 0) -> bool:
    argv, assigns = strip_wrappers(argv)
    if assigns:
        return False  # PATH=…, GIT_*=…, LD_*=… can change what a "read-only" command executes
    if not argv:
        return True
    head, args = argv[0], argv[1:]
    name = os.path.basename(head)
    if name in ("python3", "python") and len(args) >= 2 and \
            os.path.realpath(os.path.expanduser(args[0])) == installed_task_cli():
        return args[1] in TASK_SUBS
    if "/" in head:
        return False  # a path-qualified program may be anything (e.g. a script written into the plan directory)
    if name in SHELLS:
        if "-c" in args and args.index("-c") + 1 < len(args) and depth < 3:
            return command_read_only(args[args.index("-c") + 1], depth + 1)
        return False
    if name == "xargs":
        rest = _xargs_command(args)
        return bool(rest) and depth < 3 and segment_read_only(rest, depth + 1)
    if name in ALWAYS_RO:
        if name == "sort" and any(a.startswith(("-o", "--output")) for a in args):
            return False
        if name == "uniq" and len(_words(args)) >= 2:
            return False
        if name == "tree" and "-o" in args:
            return False
        return True
    if name == "find":
        return not any(a in ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf",
                             "-fls") for a in args)
    if name == "git":
        return git_read_only(args)
    if name == "openspec":
        return not args or args[0] in OPENSPEC_RO
    if name == "groundwork":
        return bool(args) and (args[0] in ("version", "--help", "-h") or
                               (args[0] == "task" and (len(args) == 1 or args[1] in TASK_SUBS)))
    words = _words(args)
    if name == "gcloud":
        return any(w in GCLOUD_READ for w in words) and not any(
            w in GCLOUD_WRITE or w.startswith(("add-", "remove-", "set-")) for w in words)
    if name == "kubectl":
        if words[:2] == ["auth", "can-i"] or (words[:1] == ["config"] and words[1:2] and
                                              words[1] in ("view", "get-contexts", "current-context")):
            return True
        return any(w in KUBECTL_READ for w in words) and not any(w in KUBECTL_WRITE for w in words)
    if name == "terraform":
        sub = words[0] if words else ""
        if sub == "state":
            return words[1:2] in (["list"], ["show"])
        if sub == "fmt":
            return "-check" in args
        return sub in TERRAFORM_READ
    if name == "helm":
        return bool(words) and words[0] in HELM_READ
    return False


def command_read_only(cmd: str, depth: int = 0) -> bool:
    if any(s in cmd for s in UNSAFE_SUBSTRINGS):
        return False
    segs = split_segments(cmd)
    if segs is None:
        return False
    return all(segment_read_only(s["argv"], depth) and not s["writes"] for s in segs)


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


def segment_sensitive(argv: list[str], cwd: str, depth: int = 0) -> str | None:
    """A label when the command changes systems outside the working tree (cloud, cluster, data, remote hosts),
    deletes recursively, starts a nested Claude Code session, or escapes the scope audit; else None."""
    argv = unwrap_run(argv)
    if not argv:
        return None
    name, args = os.path.basename(argv[0]), argv[1:]
    words = _words(args)
    if "`" in argv[0]:
        return "a command whose name comes from a command substitution (it cannot be checked)"
    if name == "eval":
        if any("$" in a or "`" in a for a in args):
            return "eval of a variable or command output (it cannot be checked)"
        return command_sensitive(" ".join(args), cwd, depth + 1) if depth < MAX_DEPTH else "a deeply nested eval"
    if name == "trap" and args and not args[0].startswith("-") and depth < MAX_DEPTH:
        return command_sensitive(args[0], cwd, depth + 1)
    if name in SHELLS:
        kind, value = _shell_invocation(args)
        if kind == "stdin" or (kind == "c" and value == ""):
            return "commands piped into a shell (they cannot be checked)"
        if kind == "c":
            return command_sensitive(value, cwd, depth + 1) if depth < MAX_DEPTH else "a deeply nested shell"
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
                found = segment_sensitive(rest[:end], cwd, depth + 1)
                if found:
                    return f"{found} (run by find {flag})"
    if "/" in argv[0] or argv[0].endswith(".sh"):
        found = _script_sensitive(argv[0], cwd, depth)
        if found:
            return found
    if name == "xargs":
        rest = unwrap_run(_xargs_command(args))
        if rest and os.path.basename(rest[0]) in SHELLS | {"eval"}:
            return "commands built by xargs for a shell (they cannot be checked)"
        return segment_sensitive(rest, cwd, depth + 1) if rest and depth < MAX_DEPTH else None
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
    if name == "rm" and any(a in ("-r", "-R", "--recursive") or re.match(r"^-[a-zA-Z]*[rR]", a) for a in args):
        return "a recursive delete"
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
    if name == "git" and words[:2] == ["worktree", "add"]:
        return "git worktree add (work in another checkout escapes the scope audit)"
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
            found[m.group(1)] = None if ("$" in m.group(2) or "`" in m.group(2)) else m.group(2)
    return found


def _resolve_head(argv: list[str], assigns: dict) -> list[str] | str:
    """A command whose name is `$T` / `${T}`: when T is assigned a literal value in the same command, its value
    stands in for the name (`T=terraform; $T apply` is `terraform apply`). When T is assigned a computed value the
    command cannot be checked (a label is returned). A variable from outside the command (`"$@"`, `"$PY"`) is left
    as is: the gate cannot know it (found by independent review: a blanket rule denied many ordinary scripts)."""
    lead = len(argv) - len(unwrap_run(argv))
    head = argv[lead] if lead < len(argv) else ""
    m = VAR_REF_RE.match(head)
    if not m or m.group(1) not in assigns:
        return argv
    value = assigns[m.group(1)]
    if value is None:
        return "a command whose name comes from a computed variable (it cannot be checked)"
    return argv[:lead] + (value.split() or [""]) + argv[lead + 1:]


def _cd_target(argv: list[str]) -> str | None:
    """The literal directory of `cd DIR` / `pushd DIR`; "" for a target Groundwork cannot follow; None otherwise."""
    u = unwrap_run(argv)
    if not u or os.path.basename(u[0]) not in ("cd", "pushd"):
        return None
    words = _words(u[1:])
    target = words[0] if words else "~"
    return "" if ("$" in target or "`" in target or target == "-") else os.path.expanduser(target)


def command_sensitive(cmd: str, cwd: str, depth: int = 0) -> str | None:
    segs = split_segments(cmd)
    if segs is None:
        return "a command Groundwork could not parse"
    assigns = _literal_assignments(segs)
    dirs, lost = [cwd], False  # `cd scripts && ./tfa.sh` runs scripts/tfa.sh (found by independent review)
    for s in segs:
        argv = _resolve_head(s["argv"], assigns)
        if isinstance(argv, str):
            return argv
        for d in dirs:
            found = segment_sensitive(argv, d, depth)
            if found:
                return found
        script = _script_operand(argv)
        if lost and script and not os.path.isabs(script) and \
                not any(os.path.isfile(os.path.join(d, script)) for d in dirs):
            return f"a script ({script}) run after a directory change Groundwork cannot follow"
        target = _cd_target(argv)
        if target == "":
            lost = True
        elif target is not None:
            dirs = list(dict.fromkeys(dirs + [os.path.normpath(os.path.join(d, target)) for d in dirs]))[:8]
    return embedded_sensitive(cmd, segs, cwd, depth)


def _script_operand(argv: list[str]) -> str | None:
    """The script a segment runs: `bash X`, `source X`, `. X`, or a path-qualified program."""
    u = unwrap_run(argv)
    if not u:
        return None
    name = os.path.basename(u[0])
    if name in SHELLS:
        kind, value = _shell_invocation(u[1:])
        return value if kind == "script" else None
    if name in ("source", ".") and _words(u[1:]):
        return _words(u[1:])[0]
    return u[0] if "/" in u[0] else None


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


def _archives_plan(argv: list[str]) -> bool:
    argv = unwrap_run(argv)
    return bool(argv) and os.path.basename(argv[0]) == "openspec" and "archive" in _words(argv[1:])


ENV_BUILTINS = {"export", "unset", "source", ".", "declare", "typeset", "local", "readonly", "alias", "eval"}
# `name() {` or `function name` — a function can shadow the approved command (`gcloud() { … --project=prod; }`).
FUNCTION_DEF_RE = re.compile(r"(?:^|[\s;&|(){}])(?:function\s+[\w.:-]+|[\w.:-]+\s*\(\s*\))")


def _changes_environment(argv: list[str]) -> bool:
    """A segment that changes the shell environment for the commands after it: `export X=…`, `X=…` alone, `source f`
    (found by independent review: `export CLOUDSDK_CORE_PROJECT=prod; <approved gcloud command>`)."""
    rest, assigns = strip_wrappers(argv)
    return (assigns and not rest) or bool(rest and os.path.basename(rest[0]) in ENV_BUILTINS)


def matches_operation(argv: list[str], operations: list[str]) -> bool:
    """The command is an Approved Operation: its words, exactly as run (no wrapper stripped, so `sudo …` is not
    covered by an approval of `…`), equal the approved words. No extra arguments: the live acceptance run showed a
    prefix match let flags the owner never saw (a different --project, say) ride on an approved command."""
    return any(toks and argv == toks for toks in (_norm_tokens(op) for op in operations))


def verification_status(segs, verify_cmd: str) -> str | None:
    """'counted' when the declared verification command ran exactly as declared (same words; output redirection
    allowed) and its exit status is the tool's exit status: started at the beginning, after ; or && (not after ||)
    and followed only by && (found by independent review: `cmd && echo PASS || echo FAIL` exits 0 when cmd fails,
    and `cmd -k x` / `--collect-only` are not the declared run). 'masked' when it ran but its status was not
    observable or it ran with extra arguments; else None."""
    toks = _norm_tokens(verify_cmd)
    if not toks:
        return None
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
            return "counted"
        found = "masked"
    return found


# ---------------------------------------------------------------------------------------------- output


def emit(obj) -> None:
    print(json.dumps(obj))
    sys.exit(0)


def deny(reason: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": reason}})


def add_context(event: str, text: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


def describe(root: str, tasks: list[dict]) -> str:
    return "; ".join(f"{t['key']} ({t.get('state')}) next: {gt.next_action(root, t)}" for t in tasks)


def is_temp(path: str, data: dict) -> bool:
    bases = {tempfile.gettempdir(), "/tmp", "/private/tmp", "/var/tmp", os.environ.get("TMPDIR") or "/tmp"}
    if data.get("scratchpad_dir"):
        bases.add(str(data["scratchpad_dir"]))
    return any(under(path, Path(b)) for b in bases if b)


def under(path: str, base: Path) -> bool:
    real, b = os.path.realpath(path), os.path.realpath(str(base))
    return real == b or real.startswith(b + os.sep)


# ---------------------------------------------------------------------------------------------- events


def on_prompt(data: dict) -> None:
    prompt = data.get("prompt") or ""
    cwd = data.get("cwd") or os.getcwd()
    stripped = prompt.strip()
    if re.search(r"\bapprove", stripped, re.IGNORECASE) and not stripped.startswith("/"):
        root = gt.repo_root(cwd)
        waiting = [t for t in (gt.load_task(root, k) for k in gt.find_keys(stripped))
                   if t and t.get("state") == gt.AWAITING] if root else []
        if waiting:
            add_context("UserPromptSubmit", "[Groundwork task gate] This message is NOT a recorded approval. Groundwork "
                        "records an approval only when the owner types the slash command itself: " +
                        "; ".join(f"/gw-approve {t['key']} {t['approval'].get('code')}" for t in waiting) +
                        ". Tell the owner that; do not treat this message as approval.")
    res = gt.intake(cwd, prompt, str(data.get("session_id") or ""))
    if not res:
        # Any other prompt while a task waits on the owner (typically the owner answering its questions without
        # naming it) still gets that task's state, so the answer is applied to the right plan.
        cls = gt.classify(stripped)
        root = gt.repo_root(cwd) if stripped and stripped[0] not in "/<!" and not (cls and cls["kind"] == "question") else None
        waiting = [t for t in gt.gated_tasks(root) if t.get("state") in (gt.PLANNING, gt.AWAITING)] if root else []
        if waiting:
            add_context("UserPromptSubmit", "[Groundwork task ledger] Task(s) waiting on the owner in this repository "
                        "(apply the owner's message to them where it fits):\n" + "\n".join(gt.render(root, t) for t in waiting)[:1500])
        return
    root = res["root"]
    if res["action"] == "existing":
        text = "\n".join(gt.render(root, t) for t in res["tasks"])
        lead = ("[Groundwork task ledger] This prompt was not registered as a new task, because the task(s) below are "
                "waiting on the owner: treat it as the owner's input to them (for example answers to the plan's missing "
                "information). If it is separate work, ask the owner for a ticket key.\n"
                if res.get("suppressed") else
                "[Groundwork task ledger] State of the task(s) this prompt names (authoritative; enforced by the task gate):\n")
        add_context("UserPromptSubmit", lead + text[:2500])
    t = res["tasks"][0]
    risk = t.get("risk") or {}
    checklist = "\n".join(f"  - {c}" for c in t.get("checklist", [])) or "  - (none)"
    if t.get("tier") == gt.MATERIAL:
        status = res.get("openspec") or "?"
        plan = gt.plan_rel(t)
        create = "" if status in ("created", "exists") else f" Create it first: openspec new change {t['change']}."
        how = "was escalated from STANDARD to" if res.get("escalated") else "is registered as"
        text = (
            f"[Groundwork task intake] {t['key']} {how} a MATERIAL engineering task: risk {risk.get('level')} "
            f"({', '.join(risk.get('categories', []))}). Its plan is the OpenSpec change {plan}/ ({status}).{create}\n"
            "Groundwork enforces this lifecycle with hooks. Until the owner approves, edits are allowed only inside the "
            "plan directory, and Bash only for read-only commands. Implementation, deployment and other changes are denied.\n"
            "Do now:\n"
            "  1. Investigate read-only (Read/Grep/Glob, read-only git and cloud commands). Do not implement anything.\n"
            f"  2. Write the plan in {plan}/: proposal.md with ## Why, ## What Changes, ## Capabilities, ## Impact, and "
            "Groundwork's ## Prerequisites, ## Risks, ## Missing Information (one bullet per unknown), ## Estimate (a "
            "range plus your confidence or uncertainty), ## Scope (repository paths the change may touch, in backticks), "
            "## Verification (exact commands, in backticks) and, if it needs any, ## Approved Operations (each "
            "sensitive command, such as a deploy, written in full exactly as it will be run, with every flag and "
            "value, in backticks; only those exact commands will be allowed, and any other needs a new approval). Add specs/<capability>/spec.md with ADDED requirements "
            "and scenarios, and tasks.md with '- [ ]' checkboxes for the implementation and verification steps "
            "(archive the change only after completion, not as a task).\n"
            f"  3. Run: {gt.task_cli()} request-approval {t['key']}  (it validates the plan and prints the owner's code)\n"
            "  4. Tell the owner, briefly: risk, prerequisites, the missing information you need from them, the "
            "estimate, and the exact /gw-approve line it printed. Then stop. You cannot approve.\n"
            "Intake checklist (deterministic; record each as known, assumed or missing in the plan):\n"
            f"{checklist}\n"
            f"Mission, in the owner's words: {gt.clip(t.get('mission'), 400)}")
    else:
        text = (f"[Groundwork task intake] {t['key']} is tracked as a STANDARD task (no infrastructure, security, data, "
                "production or deployment signal), so it has no approval gate. Plan inline, implement with tests and "
                f"verify. When done: {gt.task_cli()} complete {t['key']}. If the work turns out to touch infrastructure, "
                "security, data or production, stop and tell the owner: it then needs the MATERIAL process."
                + (f"\nChecklist:\n{checklist}" if t.get("checklist") else ""))
    add_context("UserPromptSubmit", text)


def on_expansion(data: dict) -> None:
    name = str(data.get("command_name") or "")
    if name not in gt.OWNER_COMMANDS or data.get("expansion_type") not in (None, "slash_command"):
        return
    args = str(data.get("command_args") or "").split()
    root = gt.repo_root(data.get("cwd") or os.getcwd())
    if not root:
        emit({"decision": "block", "reason": "Groundwork: not inside a git repository, so there is no task ledger here."})
    if name == "gw-approve":
        if len(args) != 2 or not gt.KEY_SAFE.match(args[0].upper()):
            emit({"decision": "block", "reason": "Groundwork: usage /gw-approve <TASK-KEY> <approval-code>"})
        key = args[0].upper()
        ok, msg = gt.approve(root, key, args[1], str(data.get("session_id") or ""))
        if not ok:
            emit({"decision": "block", "reason": msg})
        plan = (gt.load_task(root, key) or {}).get("plan", {})
        ops = "; ".join(f"`{o}`" for o in plan.get("operations", [])) or "none"
        add_context("UserPromptExpansion", (
            f"[Groundwork task gate] {msg} The owner typed /gw-approve; Groundwork recorded it. You may now implement "
            f"{key}, only within its approved scope: {', '.join(f'`{s}`' for s in plan.get('scope', []))}. Sensitive "
            f"operations allowed, exactly as written: {ops}; any other is denied. Then: check every task in tasks.md; run each verification "
            f"command on its own, not piped ({'; '.join(f'`{v}`' for v in plan.get('verify', []))}); dispatch a "
            "foreground independent review subagent (subagent_type or name containing 'review') whose final response "
            "ends with a REVIEW RESULT block (Verdict: approve|changes-required, Must-fix: N); fix any MUST FIX and "
            f"re-review; then run: {gt.task_cli()} complete {key}; archive the OpenSpec change only after that. "
            "Editing proposal.md, design.md or specs voids this "
            "approval; ticking or annotating tasks.md does not, but approved tasks cannot be removed."))
    if len(args) != 1 or not gt.KEY_SAFE.match(args[0].upper()):
        emit({"decision": "block", "reason": "Groundwork: usage /gw-cancel <TASK-KEY>"})
    ok, msg = gt.cancel(root, args[0].upper())
    if not ok:
        emit({"decision": "block", "reason": msg})
    add_context("UserPromptExpansion", f"[Groundwork task gate] {msg}")


def _safe_read_only(command: str) -> bool:
    try:
        return command_read_only(command)
    except Exception:  # an internal error must not let an owner command through (found by independent review)
        return False


def on_pre(data: dict) -> None:
    tool = str(data.get("tool_name") or "")
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    cwd = data.get("cwd") or os.getcwd()
    if tool in READ_TOOLS:
        return
    # Owner commands are owner-only in every repository and every state (design D2).
    if tool == "Skill" and str(ti.get("skill", "")).lstrip("/").split(":")[-1].lower() in gt.OWNER_COMMANDS:
        deny("Groundwork: /gw-approve and /gw-cancel are owner-only commands; Claude cannot run them.")
    # Text naming an owner command is harmless in a file edit, a subagent prompt (its own calls are gated) or a
    # read-only command such as grep; anywhere else (a command that is not read-only, a scheduled prompt, a message
    # to another session, an MCP call) it could deliver the command as if typed, so it is denied.
    command = ti.get("command") if isinstance(ti.get("command"), str) else None
    if tool not in FILE_TOOLS and tool not in ("Agent", "Task") and OWNER_CMD_RE.search(json.dumps(ti)) and not (
            command is not None and tool != "PowerShell" and _safe_read_only(command) and len(ti) <= 6):
        deny("Groundwork: this call contains an owner-only command (/gw-approve or /gw-cancel). Claude must not run, "
             "send, schedule or script it; only the owner types it.")
    path = ""
    if tool in FILE_TOOLS:
        path = str(ti.get("file_path") or ti.get("notebook_path") or "")
        if path and not os.path.isabs(path):
            path = os.path.join(cwd, path)
        if path and (under(path, gt.tasks_root()) or
                     (under(path, gt.claude_dir() / "commands") and os.path.basename(path).startswith("gw-"))):
            deny("Groundwork: the task ledger and the owner commands cannot be changed by Claude.")
    root = (gt.repo_root(os.path.dirname(path)) if path else None) or gt.repo_root(cwd)
    if not root:
        return
    tasks = gt.gated_tasks(root)
    if not tasks:
        return
    try:
        gate(tool, ti, path, root, tasks, data)
    except SystemExit:
        raise
    except Exception as exc:
        deny(f"Groundwork task gate error while {', '.join(t['key'] for t in tasks)} is active "
             f"({type(exc).__name__}: {gt.clip(exc, 200)}); denying this call (fail closed).")


def gate(tool: str, ti: dict, path: str, root: str, tasks: list[dict], data: dict) -> None:
    approved = [t for t in tasks if gt.approval_valid(root, t)]
    keys = ", ".join(t["key"] for t in tasks)
    pending = not approved
    if tool in FILE_TOOLS:
        if not path:
            return
        cdir = gt.claude_dir()
        if under(path, cdir / "hooks") or os.path.realpath(path) in {
                os.path.realpath(str(cdir / n)) for n in ("settings.json", "settings.local.json")}:
            deny(f"Groundwork: Groundwork's hooks and settings cannot be changed while {keys} is gated.")
        rel = gt.rel_path(root, path)
        if rel is None:
            if is_temp(path, data):
                return
            deny(f"Groundwork task gate: {path} is outside the repository while {keys} is gated; only the repository "
                 "and temporary directories may be written.")
        if rel in (".claude/settings.json", ".claude/settings.local.json"):
            deny(f"Groundwork: project settings cannot be changed while {keys} is gated.")
        if gt.allowed_rel(root, rel, tasks):
            return
        if pending:
            deny(f"Groundwork task gate: implementation is blocked; the owner has not approved the plan. Blocked: "
                 f"write to {rel}. Allowed now: read-only investigation and edits inside "
                 f"{', '.join(gt.plan_rel(t) + '/' for t in tasks)}. Task: {describe(root, tasks)}")
        scope = "; ".join(f"{t['key']}: {', '.join(t.get('plan', {}).get('scope', []))}" for t in approved)
        deny(f"Groundwork task gate: unauthorized change. {rel} is outside the approved scope ({scope}). Stay within "
             "the approved scope, or change the plan's Scope and get a new owner approval.")
    if tool == "PowerShell":
        deny(f"Groundwork task gate: PowerShell commands cannot be checked; use Bash while {keys} is gated.")
    if tool == "Bash" or isinstance(ti.get("command"), str):
        # Any tool that runs a shell command (Bash, Monitor, and tools added later) is checked the same way
        # (found by independent review: Monitor's command ran unchecked).
        cmd = str(ti.get("command") or "")
        if pending:
            if command_read_only(cmd):
                return
            deny(f"Groundwork task gate: only read-only commands are allowed until the owner approves the plan "
                 f"(denied: {gt.clip(cmd, 160)}). Read-only means: listing/reading files, read-only git, openspec, "
                 "the Groundwork task CLI, and cloud/cluster list/describe/get; no output redirection, command "
                 f"substitution or scripts. Task: {describe(root, tasks)}")
        segs = split_segments(cmd)
        if segs is None:
            deny("Groundwork task gate: this command could not be parsed, so it cannot be checked; simplify it.")
        ops = [o for t in approved for o in t.get("plan", {}).get("operations", [])]
        for s in segs:
            label = segment_sensitive(s["argv"], data.get("cwd") or root)
            if label and not matches_operation(s["argv"], ops):
                deny(f"Groundwork task gate: {label} is not an Approved Operation of {keys} "
                     f"(approved: {'; '.join(ops) or 'none'}). Sensitive operations need the owner's approval in the "
                     "plan and run exactly as written, with no extra arguments; to change one, edit the plan and "
                     "request approval again.")
        if any(_archives_plan(s["argv"]) for s in segs):
            deny(f"Groundwork task gate: archive the OpenSpec change only after `{gt.task_cli()} complete` succeeds "
                 f"for {keys}. Archiving moves the approved plan, which voids the approval.")
        label = embedded_sensitive(cmd, segs, data.get("cwd") or root)
        if label:
            deny(f"Groundwork task gate: {label} is not an Approved Operation of {keys}. Sensitive operations need "
                 "the owner's approval in the plan.")
        if any(matches_operation(s["argv"], ops) for s in segs) and (
                any(_changes_environment(s["argv"]) for s in segs)
                or FUNCTION_DEF_RE.search((_prepare_command(cmd) or ("", [], []))[0])):
            deny("Groundwork task gate: run the Approved Operation on its own. This command also sets or exports "
                 "environment variables, defines a function or sources a file, which can change what the approved "
                 "command acts on (for example its project).")
        cdir = str(gt.claude_dir())
        # Any non-read-only command that names the config directory (also `cd ~/.claude && … settings.json`; found by
        # independent review) is denied while a task is gated. A project's own .claude/ files (rules, agents) are not.
        markers = PROTECTED_MARKERS + (cdir, "~/.claude", "$HOME/.claude", "${HOME}/.claude", "CLAUDE_CONFIG_DIR")
        config_words = ".claude" in cmd and re.search(r"settings|hooks|groundwork", cmd)
        if (any(m in cmd for m in markers) or config_words) and not command_read_only(cmd):
            deny(f"Groundwork: Groundwork's hooks, settings and task ledger cannot be changed while {keys} is gated.")
        return
    if tool.startswith("mcp__"):
        if mcp_read_only(tool) or any(tool in t.get("plan", {}).get("operations", []) for t in approved):
            return
        deny(f"Groundwork task gate: {tool} can change an external system and is not an Approved Operation of {keys}.")
    if tool == "EnterWorktree" or (tool in ("Agent", "Task") and str(ti.get("isolation") or "") in ("worktree", "remote")):
        deny(f"Groundwork task gate: work in another checkout escapes the scope audit while {keys} is gated.")


MCP_READ_FIRST = {"get", "list", "search", "read", "query", "fetch", "describe", "show", "view", "find", "lookup",
                  "check", "validate", "count", "whoami", "status", "download", "retrieve", "inspect", "preview",
                  "browse", "explain", "diff", "resolve"}
MCP_READ_LAST = {"read", "get", "list", "search", "query", "view", "status", "info", "details", "fetch"}
MCP_WRITE_WORDS = {"create", "update", "set", "delete", "remove", "add", "put", "post", "send", "run", "execute",
                   "write", "patch", "merge", "close", "assign", "move", "upload", "publish", "trigger", "cancel",
                   "approve", "start", "stop", "restart", "enable", "disable", "push", "apply", "deploy", "edit",
                   "insert", "drop", "archive", "invite", "share", "spawn", "fork", "rename", "label",
                   "mark", "trash", "submit", "subscribe", "unsubscribe", "reply", "comment"}
# `resolve` is a lookup only when it resolves an identifier-like thing; anything else (resolve_review_thread,
# resolve_finding, resolve_merge_conflicts …) is treated as a write — fail closed (found by independent review).
RESOLVE_LOOKUPS = {"id", "ids", "library", "package", "uri", "url", "symbol", "dns", "name", "path", "host",
                   "address", "ref", "reference", "alias", "version"}


def mcp_read_only(tool: str) -> bool:
    """Read-only by its verb: leading read verb, or a trailing read word with no write verb anywhere in the name
    (found by independent review: `update_status` and `run_query` were read as read-only). `resolve` is a write only
    for a thread/issue-like object (resolve_review_thread), not for a lookup (resolve-library-id)."""
    parts = tool.split("__")
    server = parts[1].lower() if len(parts) > 2 else ""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", parts[-1])  # getJiraIssue -> get_Jira_Issue
    words = [w for w in re.split(r"[^a-z0-9]+", name.lower()) if w]
    if "resolve" in words and not RESOLVE_LOOKUPS & set(words):
        return False
    if words and words[0] in re.split(r"[^a-z0-9]+", server):
        words = words[1:]
    if not words:
        return False
    if words[0] in MCP_READ_FIRST:
        return True
    if any(w in MCP_WRITE_WORDS for w in words):
        return False
    return words[-1] in MCP_READ_LAST


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


def on_post(data: dict) -> None:
    tool = str(data.get("tool_name") or "")
    event = str(data.get("hook_event_name") or "PostToolUse")
    if tool in READ_TOOLS or tool in FILE_TOOLS:
        return  # edit tools are gated by path before they run
    cwd = data.get("cwd") or os.getcwd()
    root = gt.repo_root(cwd)
    if not root:
        return
    tasks = gt.gated_tasks(root)
    if not tasks:
        return
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    notes = []
    approved = [t for t in tasks if gt.approval_valid(root, t)]
    if isinstance(ti.get("command"), str):
        segs = split_segments(ti["command"]) or []
        resp = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
        ok = event == "PostToolUse" and not resp.get("interrupted")
        detail = str(data.get("error") or "").splitlines()[0] if not ok and data.get("error") else ""
        # A background command has only started when this fires: its approved operation still counts (it may change
        # things), but it is never evidence of a verification result.
        evidence = tool == "Bash" and not ti.get("run_in_background")
        for t in approved:
            for v in t.get("plan", {}).get("verify", []) if evidence else []:
                status = verification_status(segs, v)
                if status == "counted":
                    gt.record_verification(root, t["key"], v, ok, detail)
                    notes.append(f"{t['key']}: verification `{v}` recorded as {'PASSED' if ok else 'FAILED'}.")
                elif status == "masked":
                    notes.append(f"{t['key']}: `{v}` ran with extra arguments, piped or chained, so it does not count as "
                                 "the declared verification. Run it exactly as declared, on its own.")
            ops = t.get("plan", {}).get("operations", [])
            for s in segs:
                if segment_sensitive(s["argv"], cwd) and matches_operation(s["argv"], ops):
                    gt.record_operation(root, t["key"], " ".join(s["argv"]))
                    notes.append(f"{t['key']}: approved operation recorded; verification must run after it.")
    if tool.startswith("mcp__"):
        for t in approved:
            if tool in t.get("plan", {}).get("operations", []):
                gt.record_operation(root, t["key"], tool)
                notes.append(f"{t['key']}: approved operation {tool} recorded; verification must run after it.")
    if tool in ("Agent", "Task") and is_review_call(tool, ti) and approved:
        resp = data.get("tool_response")
        if isinstance(resp, dict) and resp.get("status") not in (None, "completed"):
            notes.append(f"A review that has not finished ({resp.get('status')}) is not captured as evidence; run the "
                         "review in the foreground so its result is returned.")
        else:
            result = parse_review_result(_response_text(resp))
            reviewer = str(ti.get("subagent_type") or ti.get("name") or "reviewer")
            for t in approved:
                gt.record_review(root, t["key"], reviewer, result)
            mf = result.get("must_fix", 0 if result.get("verdict") == "approve" else None)
            notes.append(f"Review by {reviewer} recorded: " + ("no REVIEW RESULT block found, so it cannot count "
                         "toward completion." if mf is None else f"{mf} MUST FIX finding(s)."))
    bad = gt.scope_violations(root, tasks)  # after every tool that can act (read and edit tools returned above)
    void = [t["key"] for t in tasks if t.get("state") == gt.APPROVED and t not in approved]
    if bad and void:
        # The Scope stopped applying because the plan changed, not because the change itself was out of scope.
        notes.insert(0, "APPROVAL VOID: the plan (proposal, design or specs) of " + ", ".join(void) + " changed after "
                     "approval, so its Scope no longer applies and " + ", ".join(bad[:10]) + (" …" if len(bad) > 10
                     else "") + " cannot count as approved work. Restore the approved plan, or run "
                     f"{gt.task_cli()} request-approval {void[0]} and get the owner's new approval. Ticking or "
                     "annotating tasks.md does not void an approval.")
    elif bad:
        notes.insert(0, "UNAUTHORIZED CHANGE: " + ", ".join(bad[:10]) + (" …" if len(bad) > 10 else "") +
                     " changed outside the approved scope of " + ", ".join(t["key"] for t in tasks) +
                     ". Revert these changes now (git checkout -- <path> for a tracked file; delete a new file). "
                     "Completion is refused while any remain.")
    if notes:
        add_context(event, "[Groundwork task gate] " + " ".join(notes))


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
        elif event == "UserPromptExpansion":
            on_expansion(data)
        elif event == "PreToolUse":
            on_pre(data)  # fails closed itself once a gated task is known (see on_pre)
        elif event in ("PostToolUse", "PostToolUseFailure"):
            on_post(data)
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    sys.exit(0)


if __name__ == "__main__":
    main()
