#!/usr/bin/env python3
"""Evidence receipt — what a turn actually inspected or ran, and the evidence-confidence ceiling that
supports, estimated deterministically from the session transcript, never from the model's tone.

Used two ways:
  * imported by groundwork_telemetry.py (Stop hook), which records only the confidence label and
    counts/booleans — never a path, URL or command (the telemetry privacy rule is unchanged);
  * run as `groundwork evidence` (forwarded here by the groundwork CLI), which prints the full
    receipt — the references — on demand for the user. Nothing here is persisted.

Why the transcript: every tool_use block has a matching tool_result carrying a boolean `is_error`
(keyed by tool_use_id), so "what was read, fetched, run, and whether it worked" is already recorded
by Claude Code itself. The hook-event route (PostToolUse) cannot supply it: those events are not
fired for calls denied or cancelled, and persisting tool inputs there would breach telemetry privacy.

Three things stay separate:
  validation state      did the required activities happen (declared in Harness metadata)
  evidence confidence   how strong and complete the observed evidence is (this module)
  references            where the user can inspect that evidence (this module, on demand)

The label is a best-effort, deterministic estimate — not a probability, never produced by asking the
model how sure it is, and NOT a guarantee that it cannot be too high. It is built from recognised
signals, and two design rules keep it cautious:
  * order matters: a passing test, a runtime observation or a clean review counts only if nothing
    that could change the tree happened after it (an Edit/Write, or any Bash command that is not on
    a short list of known read-only commands);
  * anything that cannot be read with certainty is not credited (see _split) and a test-shaped run
    whose result cannot be attributed withdraws an earlier pass.

  NONE    nothing was inspected or run this turn
  LOW     files/repo were read, or a check failed, or things changed and nothing verified them since
  MEDIUM  something verified after the last change: tests passed, or a runtime observation
          succeeded, or an external source was fetched — and no failing check or review finding
          contradicts it
  HIGH    tests passed AND a runtime observation succeeded AND every independent review launched
          since the last change reported zero MUST FIX AND the repo or an external source was inspected
  UNKNOWN the transcript could not be read (never upgraded to a label)

Known gaps, stated rather than hidden (the label can be too high in these cases):
  * a Bash command is judged from its text: environment effects (PATH, aliases, functions or files
    defined by an earlier `source`/`export`), arguments that expand from variables, and tools that
    wrap others (`docker run … pytest`, `make` targets that do not test) are not modelled;
  * a recognised read-only command is trusted to be read-only; remote state changes (git push, MCP
    writes, curl POST) do not count as local changes;
  * a "runtime observation" is a recognised observation command that exited 0 — whether the observed
    system is healthy is not judged; "external source" means a fetch succeeded, not that it is authoritative;
  * a review counts only when its own tool_result carries a REVIEW RESULT block (a background agent's
    report arrives as a later message and is not credited); a forged block inside a subagent's text
    would be credited, the same residual the review gate documents;
  * `pytest | tail`-style runs are judged by the runner's own `N passed` / `N failed` summary, and a
    piped read-only command by a short list of error phrases — both heuristics.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from groundwork_shared import TEST_CMD  # same test-command pattern the other hooks use
except Exception:
    TEST_CMD = re.compile(r"(?!x)x")  # fail-open: no test detection rather than a crash

LABELS = ("NONE", "LOW", "MEDIUM", "HIGH")
RANK = {name: i for i, name in enumerate(LABELS)}
MAX_REFS = 60
REF_CAP = 140
COLLECT_PER_KIND = 500  # bound memory on a huge turn without letting reads crowd out tests/reviews

READ_TOOLS = {"Read", "LS", "NotebookRead"}
SEARCH_TOOLS = {"Grep", "Glob"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_VERB = re.compile(r"(?:^|[_-])(?:get|list|read|search|query|describe|fetch|show|view)(?:[_-]|$)")
_BENIGN_TOOLS = {"TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskStop", "TaskOutput", "AskUserQuestion", "ToolSearch",
                 "EnterPlanMode", "ExitPlanMode", "ListMcpResourcesTool", "ReadMcpResourceTool", "ReadMcpResourceDirTool", "BashOutput",
                 "KillShell", "KillBash", "Monitor", "ScheduleWakeup", "ListAgents"}  # cannot change the working tree; any other unknown tool is treated as a change
_MUTATING_WORDS = {
    "create", "update", "delete", "remove", "write", "send", "post", "put", "patch", "push", "merge", "execute",
    "run", "trigger", "upsert", "insert", "set", "add", "archive", "close", "reply", "forward", "share", "move",
    "copy", "apply", "import", "upload", "submit", "assign", "cancel", "approve", "label", "unlabel", "mark",
    "trash", "restore", "duplicate", "convert", "spawn", "stop", "fork", "enable", "disable"}
_REVIEW_KIND = re.compile(r"(?<![a-z])review")  # "preview-writer" is not a reviewer

_PREFIX = re.compile(r"(?:\w+=\S*\s+)*(?:python3?\s+-m\s+|uv\s+run\s+|poetry\s+run\s+|npx\s+)?")
_REPO_CMD = re.compile(
    r"(?:cat|head|tail|less|sed\s+-n|grep|rg|ag|find|ls|tree|wc|"
    r"git\s+(?:log|show|diff|status|blame|ls-files|rev-parse))\b")
# A deliberately conservative list: a command not matched here is simply not counted as runtime.
_RUNTIME_CMD = re.compile(
    r"(?:kubectl\s+(?:get|describe|logs|top|rollout\s+status)|helm\s+(?:status|list|get)|"
    r"gcloud\s+(?!config\b|auth\b|info\b|components\b|help\b|version\b|init\b|topic\b)(?:\S+\s+)*?(?:describe|list)|"
    r"aws\s+(?!configure\b|help\b)\S+\s+(?:describe|list|get)\S*|"
    r"az\s+(?!account\b|configure\b|config\b|version\b|login\b|help\b)(?:\S+\s+)*?(?:show|list)|"
    r"docker\s+(?:ps|logs|inspect|stats)|systemctl\s+status|journalctl|curl|wget|"
    r"groundwork\s+doctor)\b")
_PIPEFAIL = re.compile(r"set\s+-[a-z]*o\s+pipefail\b")
_PIPEFAIL_OFF = re.compile(r"set\s+\+[a-z]*o\s+pipefail\b")
_FILTERS = {"tail", "head", "tee", "cat", "wc"}  # pass-through filters commonly appended to a command
_SILENT = {"cd", "pushd", "popd", "export", "unset", "set", "true", ":", "source", ".", "umask"}  # print nothing
_BENIGN_WORDS = {
    "cd", "pushd", "popd", "pwd", "echo", "printf", "true", "false", ":", "test", "[", "export", "unset", "set",
    "ls", "ll", "cat", "head", "tail", "wc", "grep", "egrep", "fgrep", "rg", "ag", "tree", "stat", "file", "du", "df",
    "which", "type", "date", "whoami", "id", "uname", "sort", "uniq", "cut", "tr", "column", "jq", "basename",
    "dirname", "realpath", "readlink", "sleep", "less", "more"}
_BENIGN_GIT = {"log", "show", "diff", "status", "blame", "ls-files", "rev-parse", "add", "commit", "push", "fetch"}
_FIND_WRITES = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fls", "-fprintf"}
_NO_RUN = re.compile(
    r"(?:^|\s)(?:--collect-only|--co|--version|--help|--fixtures|--fixtures-per-test|--markers|--setup-plan|"
    r"--collectonly|--setup-only|--no-run|--list|--list-sessions|--listenvs|--listenvs-all|--notest|--listTests|-help|-list|-version|-h|-V|--client)"
    r"(?:\s|=|$)")
_CURL_FAIL = re.compile(r"(?:^|\s)(?:--fail(?:-with-body)?|-[A-Za-z]*f[A-Za-z]*)(?:\s|$)")
_CURL_ACTION = re.compile(r"(?:^|\s)(?:-X\s*(?!GET\b|HEAD\b)\w+|--request(?:=|\s+)(?!GET\b|HEAD\b)\w+|--method(?:=|\s+)(?!GET\b|HEAD\b)\w+|"
                          r"-d|--data\S*|--json|--post-data|--post-file|--body-data|--body-file|-F|--form\S*|-T|--upload-file)(?:\s|=|$)", re.I)
_RISKY_ENV = re.compile(r"(?:^|\s)(?:PATH|PYTHONPATH|PYTHONSTARTUP|PYTEST_\w+|LD_\w+|DYLD_\w+|NODE_OPTIONS|BASH_ENV|ENV|GIT_\w+)=")
_WRITE_FLAG = re.compile(r"(?:^|\s)(?:-o|-O|--output|--output-document)(?:\s|=|$)")
_PY_TEST_SCRIPT = re.compile(r"python3?\s+(?:-[A-Za-z]\S*\s+)*(?:\S*/)?(?:test_\S*|\S*_tests?|run_?tests?)\.py\b")
_KEYWORDS = {
    "exit", "return", "trap", "eval", "exec", "if", "then", "else", "elif", "fi", "for", "while", "until", "do", "done",
    "case", "esac", "select", "function", "!", "{", "}", "coproc", "break", "continue", "wait", "alias", "unalias",
    "builtin", "command", "source", "."}
_FAIL_COUNT = re.compile(r"\b[1-9]\d*\s+(?:failed|errors?)\b")
_PASS_COUNT = re.compile(r"\b[1-9]\d*\s+passed\b")
_READ_ERROR = re.compile(
    r"(?i)no such file|cannot access|permission denied|not a git repository|fatal:|unknown revision|bad revision|"
    r"command not found|is a directory|invalid option|unrecognized option|usage:")
PRIORITY = {"review": 0, "test": 1, "runtime": 2, "repo": 3, "url": 4, "mcp": 5, "file": 6, "search": 7, "command": 8}

_RESULT_HEADING = re.compile(r"^[ \t]*(?:#+[ \t]*|\*\*)?REVIEW RESULT(?:\*\*)?[ \t]*$", re.MULTILINE | re.IGNORECASE)
_RESULT_FIELD = re.compile(r"^[ \t]*(?:[-*][ \t]*)?\**[ \t]*([A-Za-z][A-Za-z -]*?)[ \t]*\**[ \t]*:[ \t]*\**[ \t]*(.+?)[ \t]*$")

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_SECRETS = [  # (pattern, replacement) applied in order to every printed reference
    (re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)[^\s/@]+@"), r"\1[redacted]@"),
    (re.compile(r"(?<![\w.%+-])[\w.%+-]+:[^\s/@:]+@(?=[\w-]+\.)"), "[redacted]@"),
    (re.compile(r"(?i)\b(?:proxy-)?authorization\s*[:=]\s*\S+(?:\s+\S+)?"), "authorization: [redacted]"),
    (re.compile(r"(?i)\bbearer\s+\S+"), "bearer [redacted]"),
    (re.compile(r"(?i)\b(?:set-)?cookie\s*:\s*\S+"), "cookie: [redacted]"),
    (re.compile(r"(?i)(?:^|(?<=\s))(?:-u|--user|--proxy-user)\s+\S+"), "-u [redacted]"),
    (re.compile(r"(?i)(--?[\w-]{0,30}(?:token|password|passwd|secret|api[_-]?key|access[_-]?key|private[_-]?key|credential|auth)[\w-]{0,30})(?:=|\s+)\S+"),
     r"\1 [redacted]"),
    (re.compile(r"(?i)\b\w{0,30}(?:token|secret|password|passwd|pwd|api[_-]?key|access[_-]?key|private[_-]?key|credential)\w{0,30}\s*[=:]\s*\S+"),
     "[redacted]"),
    (re.compile(r"(?i)([?&](?:key|token|access_token|api_key|apikey|auth|sig|signature|secret|password|passwd|pwd|code)=)[^&\s#]+"),
     r"\1[redacted]"),
    (re.compile(r"hooks\.slack\.com/services/\S+"), "hooks.slack.com/services/[redacted]"),
    (re.compile(r"gh[pousr]_\w{10,}|github_pat_\w{20,}|sk-[A-Za-z0-9_-]{10,}|(?:AKIA|ASIA)[0-9A-Z]{12,}|xox[abprs]-[\w-]{10,}|"
                r"glpat-[\w-]{10,}|eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]*"), "[redacted]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "[redacted]"),
]


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict))
    return ""


_DROP_CATEGORIES = {"Cc", "Cf", "Zl", "Zp", "Co", "Cn"}  # control, format (bidi, zero-width, tag), separators, private/unassigned


def _drop_invisible(s: str) -> str:
    """Characters that are not visible text become a space (control, format, line/paragraph separator, private use,
    unassigned): ESC, bidi overrides, zero-width and tag characters included."""
    return "".join(" " if unicodedata.category(c) in _DROP_CATEGORIES else c for c in s)


def _clip(s, n: int = REF_CAP) -> str:
    """One printable line: control, escape and bidi characters become spaces, whitespace collapses, length is capped.
    Everything the receipt prints from untrusted text goes through here."""
    s = " ".join(_drop_invisible(_ANSI.sub("", str(s))).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _redact(s: str) -> str:
    for pattern, replacement in _SECRETS:
        s = pattern.sub(replacement, s)
    return s


def _safe(s, n: int = REF_CAP) -> str:
    """Redact first, then clip: a secret cut in half by the cap would no longer match its pattern."""
    return _clip(_redact(_clip(s, 4000)), n)  # 4000 bounds the regex work per reference (every pattern is bounded)


def _command_word(seg: str) -> str:
    """The word that names the command of a segment: environment assignments and leading redirections are skipped
    and quotes/backslashes removed ('exit', "exit", \\exit and `>/dev/null exit` are all `exit`)."""
    words = seg[_PREFIX.match(seg).end():].split()
    i = 0
    while i < len(words) and re.match(r"^(?:\d*[<>]|&>)", words[i]):
        i += 1 if re.search(r"[<>&]\S", words[i]) else 2
    return re.sub(r"[\\'\"]", "", words[i]) if i < len(words) else ""


def _split(command: str):
    """(segments, connectors) or None when the command cannot be split unambiguously.

    Quotes and backslash escapes are respected. Everything this module cannot model with certainty
    returns None, and a command that returns None is credited with nothing (and counts as a possible
    change): heredocs, command/process substitution, `${…}`, `$'…'`/`$"…"`, comments, subshells and
    groups, unbalanced quotes, background jobs, and any segment that starts with a shell keyword that
    changes control flow or the exit status (`exit`, `trap`, `if`, `for`, `!`, …). A wrong split could
    credit a test that never ran."""
    text = command.strip()
    if not text or len(text) > 20_000 or any(t in text for t in ("<<", "`", "$(", "<(", ">(", "${", "$'", '$"', "\\\n")):
        return None  # (a backslash-newline continues a line, which can turn a later # into a comment)
    pieces, cur, quote, i = [], [], None, 0

    def flush(conn):
        seg = "".join(cur).strip()
        cur.clear()
        if seg:
            pieces.append([seg, conn])
            return True
        return conn in (";", "\n")  # an empty piece is only harmless before ; or a newline

    while i < len(text):
        c = text[i]
        if quote:
            cur.append(c)
            if c == "\\" and quote == '"' and i + 1 < len(text):
                cur.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c == "\\" and i + 1 < len(text):
            cur.append(text[i:i + 2])
            i += 2
            continue
        if c in "'\"":
            quote = c
            cur.append(c)
            i += 1
            continue
        if c == "#" and (not cur or cur[-1] in " \t\n;&|()"):
            return None  # an unquoted word-initial # starts a comment: the rest of the line does not run
        if c in "()":
            return None  # subshell, group or function definition
        two = text[i:i + 2]
        if two in ("&&", "||"):
            if not flush(two):
                return None
            i += 2
            continue
        if c in ";|\n":
            if not flush(c):
                return None
            i += 1
            continue
        if c == "&":
            prev, nxt = (text[i - 1] if i else ""), (text[i + 1] if i + 1 < len(text) else "")
            if prev in "<>" or nxt == ">":  # 2>&1, &>file: a redirection, not a connector
                cur.append(c)
                i += 1
                continue
            return None  # a background job has no exit status to credit
        cur.append(c)
        i += 1
    if quote:
        return None
    last = "".join(cur).strip()
    if last:
        pieces.append([last, None])
    elif pieces:
        pieces[-1][1] = None  # a trailing ; or newline
    if not pieces:
        return None
    segs = [p[0] for p in pieces]
    for seg in segs:
        if _command_word(seg) in _KEYWORDS:
            return None
    return segs, [p[1] for p in pieces[:-1]]


def _runner_verdict(text: str):
    """True/False from a test runner's own summary line, else None. Used only when a recognised test
    command's output went through a pass-through filter such as `| tail`, whose exit status says nothing."""
    if _FAIL_COUNT.search(text) or "FAILED" in text:
        return False
    return True if _PASS_COUNT.search(text) else None


def _first_word(segment: str) -> str:
    words = segment.split()
    return words[0] if words else ""


def _pure_filter(segment: str) -> bool:
    """A pass-through filter that reads the pipe: tail/head/cat/wc with only flags or numbers, or tee (which
    also passes its input through). `cat old.log` or `head file` read a file instead and are not pure."""
    words = segment.split()
    if not words or words[0] not in _FILTERS:
        return False
    if words[0] == "tee":
        return True
    return all(w.startswith("-") or w.isdigit() for w in words[1:])


def _outcome(i: int, segs: list, conns: list, pipefail: bool, is_error: bool, text: str):
    """Did segment i succeed? True/False when the command's exit status (or the runner's own summary)
    speaks for it, None when it cannot be attributed."""
    if "||" in conns:
        return None
    after = conns[i:]
    if all(c == "&&" or (pipefail and c == "|") for c in after):
        return not is_error
    if (not is_error and all(c == "|" for c in after) and all(_pure_filter(segs[j]) for j in range(i + 1, len(segs)))
            and all(_first_word(segs[j]) in _SILENT for j in range(i))):
        return _runner_verdict(text)
    return None


def _read_ok(i: int, segs: list, conns: list, pipefail: bool, is_error: bool, text: str) -> bool:
    """Did a read-only command (first in its pipeline) really read something? Exit status when it speaks for
    the command; otherwise (`cat f | head`) a non-empty output with none of a short list of error phrases."""
    if "||" in conns or is_error:
        return False
    after = conns[i:]
    if all(c == "&&" or (pipefail and c == "|") for c in after):
        return True
    if (all(c == "|" for c in after) and all(_pure_filter(segs[j]) for j in range(i + 1, len(segs)))
            and all(_first_word(segs[j]) in _SILENT for j in range(i))):
        return bool(text.strip()) and not _READ_ERROR.search(text)
    return False


def _starts(pattern, segment: str) -> bool:
    return pattern.match(segment, _PREFIX.match(segment).end()) is not None


def _writes_file(segment: str) -> bool:
    """A redirection to a file other than /dev/null (fd duplications like 2>&1 are not writes; quoted text is not a redirection)."""
    rest = re.sub(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"", "''", segment)
    rest = re.sub(r"\d*>&\d+|&>>?\s*/dev/null|\d*>>?\s*/dev/null", "", rest)
    return ">" in rest


def _test_info(segment: str):
    """None when the segment is not a test command, else (runner, scope, runs): `runs` is False for
    invocations that only list, print help/version or dry-run, which verify nothing."""
    start = _PREFIX.match(segment).end()
    m = TEST_CMD.match(segment, start)
    if m is None:
        return None
    follower = segment[m.end():m.end() + 1]
    if follower and not (follower.isspace() or follower == "="):
        return None  # `make test-clean`, `npm run test:clean`: a different target, not the test runner
    rest = segment[start:]
    tokens = rest.split()
    if re.match(r"python3?\s", rest) and not _PY_TEST_SCRIPT.match(rest):
        return None  # a script that merely lives under tests/ (fixture generators, seeders) is not a test run
    runner = (m.group(1) or "script").strip() if m.lastindex else "script"
    runs = not _NO_RUN.search(rest)
    if runner in ("make test",) and any(t in ("-n", "--dry-run", "--just-print", "--recon") for t in tokens):
        runs = False
    if runner in ("tox", "nox") and any(t in ("-l", "-a") for t in tokens):
        runs = False
    if runner == "go test" and "-n" in tokens:
        runs = False
    cosmetic = re.compile(r"-(?:q+|v+|s|x|l)$|--(?:quiet|verbose|tb|color|durations|no-header|disable-warnings)(?:=.*)?$")
    scope = tuple(sorted(t for t in tokens[len(runner.split()):] if not cosmetic.match(t)))
    return runner, scope, runs


_SUMMARY = (  # a positive "tests really ran and passed" line, per runner family
    (re.compile(r"^(?:pytest|py\.test)\b"), _PASS_COUNT),
    (re.compile(r"^(?:tox|nox)\b"), re.compile(r"(?i)\bpassed\b|congratulations|: OK\b|was successful")),
    (re.compile(r"^unittest\b"), re.compile(r"(?m)^Ran [1-9]\d* tests?\b")),
    (re.compile(r"^cargo test\b"), re.compile(r"test result: ok\. [1-9]\d* passed")),
    (re.compile(r"^go test\b"), re.compile(r"(?m)^(?:ok|PASS)\b")),
    (re.compile(r"^(?:npm|yarn)\b"), re.compile(r"(?i)\b[1-9]\d* (?:passed|passing)\b|Tests:\s+(?:\d+ \w+, )?[1-9]\d* passed|(?m:^\s*(?:PASS|ok)\b)")),
)


def _positive_summary(runner: str, text: str) -> bool:
    """Does the output carry the runner's own positive summary? Runners without a known summary line are accepted
    on exit status plus non-empty output."""
    for family, pattern in _SUMMARY:
        if family.match(runner):
            return pattern.search(text) is not None
    return True


def _cwd_of(segs: list, j: int) -> str:
    """The directory the j-th segment runs in, as far as the text of earlier `cd` segments says."""
    for seg in reversed(segs[:j]):
        words = seg.split()
        if words and words[0] == "cd":
            return words[1] if len(words) > 1 else "~"
    return ""


def _runtime_shape_ok(segment: str) -> bool:
    """A recognised runtime command that really observes: not help/version, and curl/wget only with a URL
    (curl also with --fail, otherwise an HTTP 500 still exits 0) and not as an upload or POST."""
    rest = segment[_PREFIX.match(segment).end():]
    if _NO_RUN.search(rest):
        return False
    word = _first_word(rest)
    if word in ("curl", "wget"):
        if not re.search(r"https?://", rest) or _CURL_ACTION.search(rest):
            return False
        if word == "curl" and not _CURL_FAIL.search(rest):
            return False
    return True


def _is_repo_read(segment: str) -> bool:
    if not _starts(_REPO_CMD, segment):
        return False
    words = segment[_PREFIX.match(segment).end():].split()
    if words[0] == "find":
        return not any(w in _FIND_WRITES for w in words)
    if words[0] == "sed":
        return not any(w.startswith("-i") or w.startswith("--in-place") for w in words)
    return True


def _benign(segment: str) -> bool:
    """On the short list of commands that do not change the working tree (git commands that only read or
    record, listing and printing commands). Anything else is treated as a possible change."""
    words = segment[_PREFIX.match(segment).end():].split()
    if not words:
        return True  # only a variable assignment
    w = words[0]
    if w == "groundwork":
        return words[1:2] in (["evidence"], ["version"], ["copilot"])  # the receipt command must not lower its own estimate
    if w == "git":
        while len(words) > 2 and words[1] in ("-C", "-c"):
            words = [words[0], *words[3:]]  # git -C <path> / -c k=v before the subcommand
        sub = words[1] if len(words) > 1 else ""
        if sub == "branch":
            return all(a in ("-a", "-r", "-v", "-vv", "--list", "--show-current", "--all") for a in words[2:])
        if sub == "remote":
            return words[2:] in ([], ["-v"])
        if sub == "stash":
            return words[2:3] == ["list"]
        if sub == "worktree":
            return words[2:3] == ["list"]
        return sub in _BENIGN_GIT
    if w == "find":
        return not any(a in _FIND_WRITES for a in words)
    if w == "sed":
        return "-n" in words[1:2] and not any(a.startswith("-i") or a.startswith("--in-place") for a in words)
    if w == "sort":
        return not any(a == "-o" or a.startswith("--output") for a in words)
    return w in _BENIGN_WORDS


def _substantive(text: str) -> bool:
    """A tool result that actually returned something (not empty, `[]`, `{}`, or a no-match notice)."""
    t = text.strip()
    if t.lower() in ("", "[]", "{}", "null", "none", "[ ]", "no results", "no matches found", "no files found"):
        return False
    return not re.match(r"(?i)(?:no (?:matches|results|files|items)\b|not found\b)", t)


def _tool_words(tool: str) -> set:
    return {w.lower() for w in re.split(r"[_\-\s]+|(?<=[a-z])(?=[A-Z])", tool) if w}


def _blocked_by_policy(is_error: bool, text: str) -> bool:
    """A PreToolUse hook (e.g. a fact-forcing gate) refused the call: it never ran, so it is not evidence."""
    return is_error and re.match(r"PreToolUse:\S+ hook error", text) is not None


def _review_state(text: str):
    """(state, verdict, must_fix) from the LAST `REVIEW RESULT` heading block in a reviewer's result.
    state: 'clean' (Verdict approve and Must-fix exactly a bare 0), 'findings' (a parsed block that is not
    clean), or 'unparsed' (no heading, or a block that does not parse). Same heading/field tolerance as the
    review gate (hooks/require_material_review.py), but the last block wins and the count must be a bare integer."""
    headings = list(_RESULT_HEADING.finditer(text or ""))
    if not headings:
        return "unparsed", None, None
    fields, consumed = {}, 0
    for line in text[headings[-1].end():].splitlines(keepends=True):
        stripped = line.strip()
        if len(stripped) > 200:  # no field is this long; also bounds the regex work
            break
        if not stripped:
            if fields:
                break
            consumed += len(line)
            continue
        f = _RESULT_FIELD.match(stripped)
        if not f:
            if fields:
                break
            consumed += len(line)
            continue
        fields[f.group(1).strip().lower()] = f.group(2).strip().strip("*").strip()
        consumed += len(line)
    if len(text[headings[-1].end() + consumed:].strip()) > 600:
        return "unparsed", None, None  # a block quoted in the middle of a longer report is not the reviewer's final result
    verdict = fields.get("verdict", "").lower().replace("_", "-").replace(" ", "-")
    verdict = {"approve": "approve", "approved": "approve", "changes-required": "changes-required"}.get(verdict)
    raw = fields.get("must-fix", fields.get("must fix", ""))
    must_fix = int(raw) if re.fullmatch(r"\d{1,6}", raw) else None
    if verdict is None or must_fix is None:
        return "unparsed", verdict, must_fix
    return ("clean" if verdict == "approve" and must_fix == 0 else "findings"), verdict, must_fix


def _gh_ref(name: str, inp: dict) -> str:
    owner, repo = inp.get("owner"), inp.get("repo")
    base = f"{owner}/{repo}" if owner and repo else "github"
    for key in ("pullNumber", "issue_number", "number"):
        if inp.get(key) is not None:
            return f"{base}#{inp[key]}"
    for key in ("sha", "ref", "path"):
        if inp.get(key):
            return f"{base}:{inp[key]}"
    return f"{base} ({name.split('__')[-1]})"


def _url_ref(url: str) -> str:
    try:
        p = urlsplit(str(url).strip())  # query and fragment can carry tokens; userinfo carries credentials
    except ValueError:
        return "[unparseable url]"
    if p.netloc:
        return f"{p.scheme}://{p.netloc.rsplit('@', 1)[-1]}{p.path}"
    return _clip(url, 60)


def derive_evidence(entries: list) -> dict:
    """entries: the transcript entries of one turn. Returns {confidence, signals, references, reasons}."""
    entries = [e for e in entries if isinstance(e, dict) and not e.get("isSidechain")]
    uses = {}      # tool_use_id -> (name, input)
    order = []     # tool_use_ids in call order
    results = {}   # tool_use_id -> (is_error, text)
    for e in entries:
        content = (e.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use" and b.get("id"):
                uses[b["id"]] = (str(b.get("name", "")), b.get("input") if isinstance(b.get("input"), dict) else {})
                order.append(b["id"])
            elif b.get("type") == "tool_result" and b.get("tool_use_id"):
                results[b["tool_use_id"]] = (bool(b.get("is_error")), _text(b.get("content")))

    refs = {}
    dropped = [0]
    sig = {"repo_inspected": False, "external_source": False, "searches": 0, "tests_ran": 0,
           "tests_last_ok": None, "runtime_observed": False, "review": "none", "edits": 0, "tool_errors": 0,
           "other_changes": 0, "stale_verification": False}
    edited = set()
    st = {"mut": (-1, -1), "pass": None, "runtime": None, "failing": {}, "reviews": [], "inspected_review": False,
          "runtime_ever": False, "pass_ever": False}

    def add(kind, ref, ok=None, cap=REF_CAP):
        bucket = refs.setdefault(kind, [])
        if len(bucket) >= COLLECT_PER_KIND:
            dropped[0] += 1
            return
        item = {"kind": kind, "ref": _safe(ref, cap)}
        if ok is not None:
            item["ok"] = ok
        bucket.append(item)

    def mutate(pos):
        st["mut"] = pos

    for idx, uid in enumerate(order):
        name, inp = uses[uid]
        if uid not in results:
            continue  # still running, or never answered: no outcome, no evidence
        is_error, text = results[uid]
        if _blocked_by_policy(is_error, text):
            continue
        if is_error:
            sig["tool_errors"] += 1
        if name in EDIT_TOOLS:
            fp = str(inp.get("file_path") or inp.get("notebook_path") or "")
            if fp and not is_error:
                edited.add(fp)
                mutate((idx, 0))
        elif name in READ_TOOLS:
            if not is_error:
                sig["repo_inspected"] = True
                add("file", inp.get("file_path") or inp.get("path") or name)
        elif name in SEARCH_TOOLS:
            if not is_error and _substantive(text):
                sig["repo_inspected"] = True
                add("search", f"{name.lower()} {inp.get('pattern') or ''} in {inp.get('path') or '.'}")
        elif name == "WebFetch":
            if not is_error and _substantive(text):
                sig["external_source"] = True
                add("url", _url_ref(inp.get("url", "")))
        elif name == "WebSearch":
            sig["searches"] += 1  # search snippets are not an inspected source
        elif name in ("Agent", "Task"):
            kind = f"{inp.get('subagent_type', '')} {inp.get('name', '')}".lower()
            if _REVIEW_KIND.search(kind):
                if not is_error:
                    state, verdict, must_fix = _review_state(text)
                    label = str(inp.get("subagent_type") or inp.get("name") or "agent")
                    st["reviews"].append(((idx, 0), state))
                    if state == "unparsed":
                        add("review", f"{label} → no parseable REVIEW RESULT block in its result", False)
                    else:
                        st["inspected_review"] = True
                        add("review", f"{label} → {verdict}, must-fix {must_fix}", state == "clean")
            else:
                mutate((idx, 0))  # a general-purpose subagent may edit files
        elif name.startswith("mcp__"):
            parts = name.split("__")
            server, tool = parts[1] if len(parts) > 1 else "?", parts[-1]
            is_read = bool(READ_VERB.search(tool)) and not (_tool_words(tool) & _MUTATING_WORDS)
            if not is_read and server != "github":
                mutate((idx, 0))  # a local MCP writer (filesystem, code editor) changes the tree; the GitHub server only the remote
            if not is_error and is_read and _substantive(text):
                if server == "github":
                    sig["repo_inspected"] = True
                    add("repo", _gh_ref(name, inp))
                else:
                    sig["external_source"] = True
                    add("mcp", f"{server}/{tool}")
        elif name == "Bash":
            background = bool(inp.get("run_in_background"))  # the result is only "started": nothing ran to completion
            parsed = _split(str(inp.get("command") or ""))
            if parsed is None:
                mutate((idx, 0))  # could have changed anything; nothing is credited
                continue
            segs, conns = parsed
            pipefail = (bool(_PIPEFAIL.match(segs[0])) and bool(conns) and conns[0] in (";", "&&", "\n")
                        and not any(_PIPEFAIL_OFF.match(sg) for sg in segs))
            prev_recognised = False
            for j, segment in enumerate(segs):
                pos = (idx, j)
                follows_recognised = prev_recognised and j > 0 and conns[j - 1] == "|"
                prev_recognised = False
                if _RISKY_ENV.search(segment[:_PREFIX.match(segment).end()]):
                    sig["other_changes"] += 1  # PATH=…, PYTEST_ADDOPTS=…: the command is not what it looks like
                    mutate(pos)
                    continue
                tinfo = _test_info(segment)
                if tinfo is not None:
                    prev_recognised = True
                    runner, scope, runs = tinfo
                    if not runs or background:
                        continue  # lists/help/version/dry-run, or not finished: neither evidence nor a change
                    ok = _outcome(j, segs, conns, pipefail, is_error, text)
                    if ok is True and (_FAIL_COUNT.search(text) or not _positive_summary(runner, text)
                                       or (re.search(r"\bskipped\b", text) and not _PASS_COUNT.search(text))):
                        ok = None  # exit 0 but nothing demonstrably ran, or the output contradicts the exit status
                    cwd = _cwd_of(segs, j)
                    if ok is None:
                        st["pass"] = None  # a test-shaped run whose result cannot be attributed withdraws an earlier pass
                        if _FAIL_COUNT.search(text) or "FAILED" in text:
                            st["failing"].setdefault(runner, set()).add((cwd, scope))  # ...and a visible failure still caps the label
                        continue
                    sig["tests_ran"] += 1
                    add("test", segment, ok, cap=100)
                    if ok:
                        st["pass"], st["pass_ever"] = pos, True
                        failing = st["failing"]
                        if scope == ():
                            if runner in failing:
                                failing[runner] = {k for k in failing[runner] if k[0] != cwd}
                        elif runner in failing:
                            failing[runner].discard((cwd, scope))
                        if runner in failing and not failing[runner]:
                            del failing[runner]
                    else:
                        st["failing"].setdefault(runner, set()).add((cwd, scope))
                    continue
                if _starts(_RUNTIME_CMD, segment):
                    prev_recognised = True
                    if _writes_file(segment) or _WRITE_FLAG.search(segment):
                        sig["other_changes"] += 1  # `curl … > src/a.py`, `wget -O f`, `kubectl get … > f`: it wrote a file
                        mutate(pos)
                        continue
                    if _runtime_shape_ok(segment) and not background \
                            and _outcome(j, segs, conns, pipefail, is_error, text) is True:
                        st["runtime"], st["runtime_ever"] = pos, True
                        add("runtime", segment, True, cap=100)
                    continue
                if _is_repo_read(segment):
                    prev_recognised = True
                    if _writes_file(segment):
                        sig["other_changes"] += 1
                        mutate(pos)
                    elif j == 0 and not background and _read_ok(j, segs, conns, pipefail, is_error, text):
                        sig["repo_inspected"] = True  # only the command itself, not a filter later in a pipeline
                        add("command", segment, cap=100)
                    continue
                if follows_recognised and _first_word(segment) in _FILTERS and not _writes_file(segment):
                    prev_recognised = True  # an output filter on a recognised command (`pytest | tail`, `… | tee log`)
                    continue
                if _benign(segment) and not _writes_file(segment):
                    continue
                sig["other_changes"] += 1  # not on the known read-only list: it may have changed the tree
                mutate(pos)
        else:
            if name not in _BENIGN_TOOLS:
                mutate((idx, 0))  # Skill, SlashCommand, PowerShell, a tool this version has never seen: it may have changed things
    sig["edits"] = len(edited)

    lm = st["mut"]
    failing = any(st["failing"].values())
    pass_valid = st["pass"] is not None and st["pass"] > lm
    runtime_valid = st["runtime"] is not None and st["runtime"] > lm
    sig["tests_last_ok"] = False if failing else (True if pass_valid else None)
    sig["runtime_observed"] = runtime_valid
    sig["stale_verification"] = bool((st["pass_ever"] or st["runtime_ever"]) and not (pass_valid or runtime_valid))
    fresh = [s for p, s in st["reviews"] if p > lm]
    if fresh:
        sig["review"] = "findings" if "findings" in fresh else "unparsed" if "unparsed" in fresh else "clean"
    elif st["reviews"]:
        sig["review"] = "stale"
    sig["review_findings_unconfirmed"] = bool(sig["review"] == "stale" and any(s == "findings" for _, s in st["reviews"]))
    sig["inspected_any"] = bool(sig["repo_inspected"] or sig["external_source"] or sig["tests_ran"]
                                or st["runtime_ever"] or st["inspected_review"])
    label, reasons = _confidence(sig)

    flat = [r for kind in refs for r in refs[kind]]
    seen, unique = set(), []
    for r in flat:
        key = (r["kind"], r["ref"], r.get("ok"))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda r: PRIORITY.get(r["kind"], 9))  # stable: the strongest kinds survive the cut
    return {"confidence": label, "signals": sig, "references": unique[:MAX_REFS],
            "references_omitted": dropped[0] + max(0, len(unique) - MAX_REFS), "reasons": reasons}


def _confidence(sig: dict):
    """(label, reasons) — the rule documented in the module docstring, in one place."""
    changed = sig["edits"] + sig["other_changes"]
    if not sig.get("inspected_any"):
        if not changed:
            return "NONE", ["nothing was inspected or run this turn"]
        return "LOW", [f"{sig['edits']} file edit(s) and {sig['other_changes']} other command(s) may have changed things; "
                       "nothing was inspected and nothing verified them"]
    verified = sig["tests_last_ok"] is True or sig["runtime_observed"]
    changes = sig["edits"] + sig["other_changes"]
    reasons, capped = [], False
    if sig["tests_last_ok"] is False:
        capped = True
        reasons.append("a recognised test run failed and was not re-run to a pass")
    if sig["review"] == "findings":
        capped = True
        reasons.append("an independent review since the last change reported MUST FIX findings")
    if sig.get("review_findings_unconfirmed"):
        capped = True
        reasons.append("a review reported MUST FIX findings and no review has run since the later changes")
    if changes and not verified:
        capped = True
        reasons.append(f"{sig['edits']} file edit(s) and {sig['other_changes']} other command(s) may have changed things "
                       "and no passing test or runtime observation came after them")
    if capped:
        return "LOW", reasons
    if sig["tests_last_ok"] is True and sig["runtime_observed"] and sig["review"] == "clean" \
            and (sig["repo_inspected"] or sig["external_source"]):
        return "HIGH", ["tests passed, a runtime observation succeeded, and every review since the last change reported zero MUST FIX"]
    if verified or sig["external_source"]:
        if sig["tests_last_ok"] is not True:
            reasons.append("no passing test run recognised after the last change")
        if not sig["runtime_observed"]:
            reasons.append("no runtime observation recognised after the last change")
        if sig["review"] == "stale":
            reasons.append("the independent review predates later changes")
        elif sig["review"] == "unparsed":
            reasons.append("a review ran but its result had no parseable REVIEW RESULT block")
        elif sig["review"] != "clean":
            reasons.append("no independent review with a parsed REVIEW RESULT of zero MUST FIX")
        if sig["stale_verification"]:
            reasons.append("an earlier passing check predates later changes and is not counted")
        if not (sig["repo_inspected"] or sig["external_source"]):
            reasons.append("no repository file or external source was inspected")
        return "MEDIUM", reasons
    return "LOW", ["only files or the repository were read; nothing verified, fetched or ran"]


# ------------------------------------------------------------------ hook-facing summary
def telemetry_summary(entries: list) -> dict:
    """What the Stop hook may persist: the label and counts/booleans. No path, URL or command."""
    ev = derive_evidence(entries)
    s = ev["signals"]
    return {"confidence": ev["confidence"],
            "signals": {"repo_inspected": s["repo_inspected"], "external_source": s["external_source"],
                        "tests_ran": s["tests_ran"], "tests_last_ok": s["tests_last_ok"],
                        "runtime_observed": s["runtime_observed"], "review": s["review"],
                        "edits": s["edits"], "tool_errors": s["tool_errors"]}}


def declared_label(declared):
    """The confidence label a response states, tolerant of punctuation and styling ('High.', '**HIGH**',
    'HIGH (ish)', 'MEDIUM/HIGH' -> the higher), or None when it states none."""
    t = _drop_invisible(_ANSI.sub("", str(declared or ""))).upper()[:60]
    m = re.search(r"\b(NONE|LOW|MEDIUM|HIGH)\b(?:\s*[/\-]\s*(NONE|LOW|MEDIUM|HIGH)\b)?", t)
    if not m:
        return None
    return max((g for g in m.groups() if g), key=lambda g: RANK[g])


def declared_exceeds(declared: str, observed: str):
    """True/False when both are known labels, else None — the model's stated label vs the ceiling."""
    d, o = declared_label(declared), (observed or "").strip().upper()
    if d in RANK and o in RANK:
        return RANK[d] > RANK[o]
    return None


# ------------------------------------------------------------------ CLI
def _default_transcript() -> Path | None:
    """Newest transcript of THIS directory's project, looking in the parent directories too (the shell's
    working directory may be a subfolder of the project). Never another project's transcript: showing one
    project's receipt as 'the last turn' of another would be wrong, so the answer is None instead."""
    cfg = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    here = Path(os.getcwd())
    for directory in (here, *here.parents):
        base = cfg / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(directory))
        best, best_mtime = None, -1.0
        try:
            candidates = list(base.glob("*.jsonl"))
        except OSError:
            continue
        for p in (c for c in candidates if not c.name.startswith("agent-")):
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue  # a dangling symlink or a file that vanished
            if mtime > best_mtime:
                best, best_mtime = p, mtime
        if best is not None:
            return best
    return None


def _last_assistant_text(entries: list) -> str:
    for e in reversed(entries):
        if e.get("type") == "assistant":
            t = _text((e.get("message") or {}).get("content"))
            if t.strip():
                return t
    return ""


def _unknown(args, reason: str, transcript=None) -> int:
    out = {"confidence": "UNKNOWN", "reasons": [reason], "references": [], "transcript": transcript}
    print(json.dumps(out) if args.json else f"Evidence confidence: UNKNOWN — {reason}")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="groundwork evidence",
        description="Print the evidence receipt for the last turn of a session: what was actually "
                    "inspected or run, and the evidence-confidence ceiling that supports. Read-only.")
    ap.add_argument("--transcript", help="transcript .jsonl to read (default: the newest for this directory's project)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    try:
        path = Path(args.transcript).expanduser() if args.transcript else _default_transcript()
    except (RuntimeError, OSError):
        path = None
    if path is None or not path.is_file():
        return _unknown(args, "that transcript is not a readable file" if args.transcript else
                        "no readable transcript found for this directory (run it from the project, or pass --transcript)")
    try:
        from groundwork_telemetry import current_turn, parse_metadata  # lazy: telemetry imports this module
        entries = current_turn(str(path))
    except Exception:
        entries = []
    if not entries:
        return _unknown(args, f"could not read {_clip(path, 200)}", str(path))
    try:
        ev = derive_evidence(entries)
    except Exception as exc:  # a transcript shape this version did not anticipate must not become a traceback
        return _unknown(args, f"the transcript could not be analysed ({type(exc).__name__})", str(path))
    declared = ""
    try:
        declared = parse_metadata(_last_assistant_text(entries)).get("confidence", "")
    except Exception:
        pass
    declared_clean = _clip(declared, 40)
    over = declared_exceeds(declared, ev["confidence"])
    ev.update({"transcript": str(path), "declared_confidence": declared_clean or None, "declared_exceeds_observed": over})
    if args.json:
        print(json.dumps(ev, indent=2))
        return 0
    print(f"Evidence confidence (ceiling estimate): {ev['confidence']}")
    for r in ev["reasons"]:
        print(f"  - {r}")
    if declared_clean:
        verdict = "EXCEEDS what was observed" if over else "within the observed ceiling" if over is False else "not a recognised label"
        print(f"Declared in the last response: {declared_clean} — {verdict}")
    s = ev["signals"]
    print(f"Signals: repo_inspected={s['repo_inspected']} external_source={s['external_source']} tests_ran={s['tests_ran']} "
          f"tests_last_ok={s['tests_last_ok']} runtime_observed={s['runtime_observed']} review={s['review']} "
          f"edits={s['edits']} other_changes={s['other_changes']} tool_errors={s['tool_errors']}")
    omitted = ev.get("references_omitted", 0)
    print(f"Transcript: {_clip(path, 300)}")
    print(f"References ({len(ev['references'])}{f' shown, {omitted} more omitted — strongest kinds first' if omitted else ''}, from {_clip(path.name, 80)}):")
    for r in ev["references"]:
        mark = "" if "ok" not in r else " [ok]" if r["ok"] else " [failed]"
        print(f"  {r['kind']:<8} {r['ref']}{mark}")
    print("Validation state is separate: this is evidence quality, not a statement that required checks were done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
