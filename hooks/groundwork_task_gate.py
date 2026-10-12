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
REDIRECT_RE = re.compile(r"^(?:&>>?|>>?|>\||>&|<<<|<<-?|<&|<)$")
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
SENSITIVE_HEADS = ("gcloud", "kubectl", "terraform", "helm", "aws", "az", "gsutil", "bq", "ansible", "ssh", "scp",
                   "rsync", "curl", "wget", "psql", "mysql", "sqlplus", "mongosh", "redis-cli", "docker", "rm", "claude")
# Prefixes that run the command after them; unwrapped before the sensitivity check (found by independent review:
# `sudo gcloud … delete`, `watch kubectl delete …`, `setsid terraform destroy` were not classified as sensitive).
RUN_WRAPPERS = {"sudo": {"-u", "-g", "-C", "-h", "-p", "-U", "-r", "-t", "-D"}, "doas": {"-u", "-C"},
                "watch": {"-n", "--interval"}, "setsid": set(), "ionice": {"-c", "-n", "-p"},
                "chrt": set(), "taskset": set(), "unbuffer": set()}
RUN_WRAPPER_POSITIONALS = {"chrt": 1, "taskset": 1}  # chrt PRIORITY cmd …, taskset MASK cmd …
DB_CLIENTS = {"psql", "mysql", "sqlplus", "mongosh", "mongo", "redis-cli", "cqlsh", "sqlcmd", "sqlite3"}


def split_segments(cmd: str):
    """[{argv, writes, prev, next}] for each simple command, or None when the command cannot be parsed.
    `writes`: an output redirection to a real file. prev/next: the operator before/after the segment."""
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars="();<>|&\n")
        lex.whitespace = " \t\r"
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return None
    segments, cur, writes, prev = [], [], False, None
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in SEPARATORS:
            if cur:
                segments.append({"argv": cur, "writes": writes, "prev": prev, "next": tok})
            cur, writes, prev = [], False, tok
        elif REDIRECT_RE.match(tok):
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            if tok.startswith((">", "&>")) and not (tok == ">&" and target.isdigit()) and target not in DEV_SINKS:
                writes = True
            i += 1  # skip the redirection target / heredoc delimiter
        elif tok.isdigit() and i + 1 < len(tokens) and REDIRECT_RE.match(tokens[i + 1]):
            pass  # the "2" in "2>&1"
        else:
            cur.append(tok)
        i += 1
    if cur:
        segments.append({"argv": cur, "writes": writes, "prev": prev, "next": None})
    return segments


def strip_wrappers(argv: list[str]):
    """Drop env assignments and harmless wrappers. Returns (argv, had_assignments)."""
    i, assigns = 0, False
    while i < len(argv):
        t = argv[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            assigns, i = True, i + 1
        elif t in ("command", "builtin", "nohup", "time", "exec"):
            i += 1
        elif t == "env":
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 2 if argv[i] in ("-u", "--unset", "-C", "--chdir") else 1
        elif t == "nice":
            i += 1
            if i < len(argv) and argv[i] == "-n":
                i += 2
            elif i < len(argv) and argv[i].startswith("-"):
                i += 1
        elif t == "timeout":
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 2 if argv[i] in ("-s", "--signal", "-k", "--kill-after") else 1
            i += 1  # the duration
        elif t == "stdbuf":
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


def segment_read_only(argv: list[str], depth: int = 0) -> bool:
    argv, assigns = strip_wrappers(argv)
    if assigns:
        return False  # PATH=…, GIT_*=…, LD_*=… can change what a "read-only" command executes
    if not argv:
        return True
    head, args = argv[0], argv[1:]
    name = os.path.basename(head)
    if name in ("python3", "python") and len(args) >= 2 and os.path.realpath(args[0]) == installed_task_cli():
        return args[1] in TASK_SUBS
    if "/" in head:
        return False  # a path-qualified program may be anything (e.g. a script written into the plan directory)
    if name in SHELLS:
        if "-c" in args and args.index("-c") + 1 < len(args) and depth < 3:
            return command_read_only(args[args.index("-c") + 1], depth + 1)
        return False
    if name == "xargs":
        i = 0
        while i < len(args) and args[i].startswith("-"):
            i += 2 if args[i] in ("-I", "-n", "-P", "-L", "-d", "-E", "-s", "-a") else 1
        return i < len(args) and depth < 3 and segment_read_only(args[i:], depth + 1)
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
            i += 2 if argv[i] in value_flags else 1
        i += RUN_WRAPPER_POSITIONALS.get(name, 0)
        argv, _ = strip_wrappers(argv[i:])
    return argv


def _shell_command_arg(args: list[str]):
    """The command string of `sh -c CMD` (also -lc, -ec, `-o pipefail -c`); "" when the shell reads its commands
    from stdin (no script and no -c); None when it runs a script file."""
    i = 0
    while i < len(args):
        a = args[i]
        if re.match(r"^-[a-zA-Z]*c[a-zA-Z]*$", a):
            return args[i + 1] if i + 1 < len(args) else ""
        if a in ("-o", "+o", "-O", "+O", "--rcfile", "--init-file"):
            i += 2
            continue
        if not a.startswith(("-", "+")):
            return None
        i += 1
    return ""


def segment_sensitive(argv: list[str], cwd: str, depth: int = 0) -> str | None:
    """A label when the command changes systems outside the working tree (cloud, cluster, data, remote hosts),
    deletes recursively, starts a nested Claude Code session, or escapes the scope audit; else None."""
    argv = unwrap_run(argv)
    if not argv:
        return None
    name, args = os.path.basename(argv[0]), argv[1:]
    words = _words(args)
    if name == "eval" and depth < 3:
        return command_sensitive(" ".join(args), cwd, depth + 1)
    if name in SHELLS:
        inner = _shell_command_arg(args)
        if inner == "":
            return "commands piped into a shell (they cannot be checked)"
        if inner is not None:
            return command_sensitive(inner, cwd, depth + 1) if depth < 3 else "a deeply nested shell"
        return _script_sensitive(words[0], cwd, depth) if words else None
    if name == "claude":
        return "a nested Claude Code session"
    if name == "find":
        for flag in ("-exec", "-execdir", "-ok", "-okdir"):
            if flag in args:
                rest = args[args.index(flag) + 1:]
                end = next((k for k, a in enumerate(rest) if a in (";", "+")), len(rest))
                found = segment_sensitive(rest[:end], cwd, depth + 1) if depth < 3 else None
                if found:
                    return f"{found} (run by find {flag})"
    if "/" in argv[0] or argv[0].endswith(".sh"):
        found = _script_sensitive(argv[0], cwd, depth)
        if found:
            return found
    if name == "xargs":
        rest = [a for a in args if not a.startswith("-")]
        return segment_sensitive(rest, cwd, depth + 1) if rest and depth < 3 else None
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


def _script_sensitive(script: str, cwd: str, depth: int) -> str | None:
    path = script if os.path.isabs(script) else os.path.join(cwd, script)
    try:
        if depth >= 3 or not os.path.isfile(path) or os.path.getsize(path) > 200_000:
            return None
        text = Path(path).read_text(errors="replace")
    except OSError:
        return None
    if not (path.endswith(".sh") or re.match(r"#!\S*\b(?:ba|z|k|da)?sh\b|#!\S*env\s+(?:ba|z|k|da)?sh\b", text)):
        return None
    found = command_sensitive(text, cwd, depth + 1)
    return f"{found} inside {script}" if found else None


def command_sensitive(cmd: str, cwd: str, depth: int = 0) -> str | None:
    segs = split_segments(cmd)
    if segs is None:
        return "a command Groundwork could not parse"
    for s in segs:
        found = segment_sensitive(s["argv"], cwd, depth)
        if found:
            return found
    return None


def _norm_tokens(cmd: str) -> list[str] | None:
    try:
        return shlex.split(cmd)
    except ValueError:
        return None


def matches_operation(argv: list[str], operations: list[str]) -> bool:
    """The command is an Approved Operation: its words, exactly as run (no wrapper stripped, so `sudo …` is not
    covered by an approval of `…`), start with the approved words. A prefix match is accepted only for an operation
    of at least three words, so a bare `gcloud` or `kubectl apply` approves nothing broader."""
    for op in operations:
        toks = _norm_tokens(op)
        if toks and argv[: len(toks)] == toks and (len(argv) == len(toks) or len(toks) >= 3):
            return True
    return False


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
            "## Verification (exact commands, in backticks) and, if it needs any, ## Approved Operations (exact "
            "sensitive commands such as deploys, in backticks). Add specs/<capability>/spec.md with ADDED requirements "
            "and scenarios, and tasks.md with '- [ ]' checkboxes.\n"
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
            f"operations allowed: {ops}; any other is denied. Then: check every task in tasks.md; run each verification "
            f"command on its own, not piped ({'; '.join(f'`{v}`' for v in plan.get('verify', []))}); dispatch a "
            "foreground independent review subagent (subagent_type or name containing 'review') whose final response "
            "ends with a REVIEW RESULT block (Verdict: approve|changes-required, Must-fix: N); fix any MUST FIX and "
            f"re-review; then run: {gt.task_cli()} complete {key}. Editing the plan voids this approval."))
    if len(args) != 1 or not gt.KEY_SAFE.match(args[0].upper()):
        emit({"decision": "block", "reason": "Groundwork: usage /gw-cancel <TASK-KEY>"})
    ok, msg = gt.cancel(root, args[0].upper())
    if not ok:
        emit({"decision": "block", "reason": msg})
    add_context("UserPromptExpansion", f"[Groundwork task gate] {msg}")


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
            command is not None and tool != "PowerShell" and command_read_only(command) and len(ti) <= 6):
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
                     f"(approved: {'; '.join(ops) or 'none'}). Sensitive operations need the owner's approval in the plan.")
        if any(u in cmd for u in UNSAFE_SUBSTRINGS) and re.search(
                r"(?<![\w-])(?:" + "|".join(SENSITIVE_HEADS) + r")(?![\w-])", cmd):
            deny("Groundwork task gate: command substitution around a sensitive tool cannot be checked; run it directly.")
        cdir = str(gt.claude_dir())
        # Any non-read-only command that names the config directory at all (also `cd ~/.claude && … settings.json`;
        # found by independent review) is denied while a task is gated.
        markers = PROTECTED_MARKERS + (cdir, "~/.claude", "$HOME/.claude", "${HOME}/.claude", "CLAUDE_CONFIG_DIR")
        if any(m in cmd for m in markers) and not command_read_only(cmd):
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
RESOLVE_TARGETS = {"thread", "review", "comment", "conversation", "issue", "incident", "alert", "ticket"}


def mcp_read_only(tool: str) -> bool:
    """Read-only by its verb: leading read verb, or a trailing read word with no write verb anywhere in the name
    (found by independent review: `update_status` and `run_query` were read as read-only). `resolve` is a write only
    for a thread/issue-like object (resolve_review_thread), not for a lookup (resolve-library-id)."""
    parts = tool.split("__")
    server = parts[1].lower() if len(parts) > 2 else ""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", parts[-1])  # getJiraIssue -> get_Jira_Issue
    words = [w for w in re.split(r"[^a-z0-9]+", name.lower()) if w]
    if "resolve" in words and RESOLVE_TARGETS & set(words):
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
    if bad:
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
