"""Mutation check for scripts/groundwork_copilot.py: each mutant removes or weakens one safety clause, and
tests/test_groundwork_copilot.py must then fail. A mutant that makes the tests hang (timeout) counts as caught.

Run from the repository root:

    python3 tests/mutation/mutate_copilot.py [mutant name ...]

It works on a COPY of the tracked files in a temporary directory, so the working tree is never modified and an
interrupted run cannot leave a mutated script behind. The tests that need tmux skip themselves when it is absent, and
a mutant that only they can catch (the tmux field order, -J) then shows as SURVIVED: run it where tmux is installed.
Not collected by pytest (the name does not start with test_)."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path.cwd()
WORK = Path(tempfile.mkdtemp(prefix="gw-mutate-copilot-"))
files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.split(b"\0")
for rel in filter(None, files):
    src = ROOT / rel.decode()
    if src.is_file():
        dst = WORK / rel.decode()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
TARGET = WORK / "scripts" / "groundwork_copilot.py"
ORIG = TARGET.read_text()
TIMEOUT_S = 240

MUTANTS = [
    ('no --safe-mode', 'CONTAINMENT_PRIMARY = ["--safe-mode"]', 'CONTAINMENT_PRIMARY = []'),
    ('prompt not on stdin', 'input=prompt, capture_output=True', 'input=None, capture_output=True'),
    ('--tools removed', '"--tools", "", "--no-session-persistence"', '"--no-session-persistence"'),
    ('no scratch cwd', 'timeout=CLAUDE_TIMEOUT_S, cwd=scratch)', 'timeout=CLAUDE_TIMEOUT_S, cwd=None)'),
    ('no fallback', 'if r.returncode != 0 and _UNKNOWN_SAFE_MODE.search', 'if False and _UNKNOWN_SAFE_MODE.search'),
    ('fallback on any failure that mentions it', '_UNKNOWN_SAFE_MODE.search(r.stderr or "")', '("--safe-mode" in (r.stderr or "") + (r.stdout or ""))'),
    ('fallback not announced', '"(your user-level hooks and settings still apply to this call)", file=sys.stderr)', '"(your user-level hooks and settings still apply to this call)", file=open(os.devnull, "w"))'),
    ('budget 25', 'BUDGET_USD = "0.25"', 'BUDGET_USD = "25"'),
    ('redact after cut', '    text = bound(text, CAPTURE_LINES, CAPTURE_CHARS)\n    text, _ = redact(text)\n    text = bound(text, lines)', '    text = bound(text, lines)\n    text, _ = redact(text)'),
    ('facts not redacted', 'facts, _ = redact(clean_text(project_facts(info["path"])))', 'facts = project_facts(info["path"])'),
    ('facts lines not cut', 'facts = "\\n".join(line[:FACT_LINE_CHARS] for line in facts.split("\\n"))', 'pass'),
    ('text not cleaned', '    text = clean_text(raw)\n', '    text = strip_ansi(raw)\n'),
    ('signature check allowed', '"-c", "log.showSignature=false", ', ''),
    ('git status back', '    last = _git(path, "log", "-1", "--format=%h %s") or "(no commits)"\n', '    _git(path, "status", "--porcelain")\n    last = _git(path, "log", "-1", "--format=%h %s") or "(no commits)"\n'),
    ('no ancestry check', 'if not is_ancestor(info["pid"], env):', 'if False:'),
    ('pane fields in the old order', '"#{pane_tty}\\t#{pane_pid}\\t#{pane_current_path}"', '"#{pane_tty}\\t#{pane_current_path}\\t#{pane_pid}"'),
    ('non-numeric pid accepted', '    if not pid.isdigit():\n        raise CopilotError(f"tmux did not report', '    if False:\n        raise CopilotError(f"tmux did not report'),
    ('unicode digit pane', 're.fullmatch(r"%[0-9]+", pane)', 're.fullmatch(r"%\\d+", pane)'),
    ('no tty compare', 'if not info["tty"].endswith("/" + mine):', 'if False:'),
    ('no -J on capture', '"capture-pane", "-p", "-J", ', '"capture-pane", "-p", '),
    ('constant boundary', 'boundary = secrets.token_hex(8)\n        while', 'boundary = "abc"\n        while'),
    ('no lines clamp', 'lines = max(1, min(args.lines, MAX_LINES_CAP))', 'lines = args.lines'),
    ('answer not sanitised', 'answer = printable(call_claude(prompt))', 'answer = call_claude(prompt)'),
    ('multi-line errors', 'super().__init__(" ".join(str(message).split())[:300])', 'super().__init__(str(message))'),
    ('empty answer accepted', '    if not answer:\n        raise CopilotError("claude returned an empty answer")\n', ''),
    ('char cap x10', 'MAX_CHARS = 16000', 'MAX_CHARS = 160000'),
    ('relative PATH allowed', '    if not os.path.isabs(found):\n        raise CopilotError(', '    if False:\n        raise CopilotError('),
    ('strict stdin decode', 'tail.decode("utf-8", "replace")', 'tail.decode("utf-8")'),
    ('closed stdin not handled', '            if fp is None:', '            if False:'),
    ('stdin tail not kept', 'tail = (tail + chunk)[-limit:]', 'tail = tail + chunk'),
    ('invocation not cut', '        text = cut_invocation(text)\n', '        pass\n'),
    ('tmux default timeout bound at definition', 'timeout = TOOL_TIMEOUT_S if timeout is None else timeout', 'timeout = timeout'),
    ('--json without notice', '"answer": answer, "notice": NOTICE}', '"answer": answer}'),
    ('--json dry-run without notice', '"sent": False, "prompt": prompt, "notice": NOTICE}', '"sent": False, "prompt": prompt}'),
    ('question not redacted', 'question, _ = redact(" ".join(clean_text(args.question or "").split())[:500])', 'question = " ".join(clean_text(args.question or "").split())[:500]'),
    ('SIGTERM not handled', 'signal.signal(signal.SIGTERM, _on_sigterm)', 'pass'),
    ('stdout encoding errors fatal', 'stream.reconfigure(errors="replace")', 'pass'),
    ('kv scanner off', '    text, n = _redact_kv(text)\n    count += n\n', ''),
    ('escaped closing quote of a name', 'if k + 1 < n and text[k] == "\\\\" and text[k + 1] in "\\"\'":', 'if False:'),
    ('unquoted value cut at ; and ,', '|[^\\s"\']+|["\']\\S*)"""', '|[^\\s"\';,]+|["\']\\S*)"""'),
    ('unterminated quote not redacted', '|[^\\s"\']+|["\']\\S*)"""', '|[^\\s"\']+)"""'),
    ('escaped-quoted value not redacted', '|\\\\"[^"\\\\]*\\\\"|\\\\\'[^\'\\\\]*\\\\\'', ''),
    ('terraform value object', 'if k < n and text[k] == "{":', 'if False:'),
    ('only 10 blanks', 'MAX_BLANKS = 40', 'MAX_BLANKS = 10'),
    ('authorization: first word only', '[^\\r\\n]+)"), r"\\1[redacted]"),', '[^\\s\\"\']+)"), r"\\1[redacted]"),'),
    ('token counts redacted', 'if (name.startswith("tokens") and _COUNT_VALUE.fullmatch(value)) or name.startswith("tokenizer"):', 'if False:'),
    ('PWD redacted', 'if name == "pwd" and value[:1] in ("/", "~"):', 'if False:'),
    ('benign values redacted', 'if not value or raw in _BENIGN_VALUES or value in _BENIGN_VALUES:', 'if False:'),
    ('key mention hides what follows', 'if _KEY_BODY.match(text, b.end()):', 'if True:'),
    ('unterminated key kept', 'if _KEY_BODY.match(text, b.end()):', 'if False:'),
    ('dangling END kept', 'if end and not _KEY_BEGIN.search(text[:end.start()]):', 'if False:'),
    ('invisible characters kept', ' and ord(c) not in _INVISIBLE', ''),
    ('private-use and unassigned kept', '"Zp", "Co", "Cn"}', '"Zp"}'),
]

# Mutants that cannot change behaviour, with the reason. They are not counted as caught or survived.
EQUIVALENT = {
    "fsmonitor allowed": "the tool no longer runs `git status` (the only command of the three it runs that reads the index), "
                         "so core.fsmonitor=false is defence in depth: the fsmonitor canary test passes with the flag removed",
}

survived = []
which = sys.argv[1:]
for name, old, new in MUTANTS:
    if which and name not in which:
        continue
    text = ORIG
    if old not in text:
        print(f"STALE (pattern not found): {name}")
        survived.append(name + " [pattern not found]")
        continue
    TARGET.write_text(text.replace(old, new, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "tests/test_groundwork_copilot.py", "-q", "-x"], cwd=WORK,
                           capture_output=True, text=True, timeout=TIMEOUT_S)
        caught, how = r.returncode != 0, "caught   "
    except subprocess.TimeoutExpired:
        caught, how = True, "caught (timeout) "
    finally:
        TARGET.write_text(ORIG)
    print((how if caught else "SURVIVED ") + name, flush=True)
    if not caught:
        survived.append(name)
shutil.rmtree(WORK, ignore_errors=True)
total = len([m for m in MUTANTS if not which or m[0] in which])
for name, why in EQUIVALENT.items():
    print(f"EQUIVALENT (not counted) {name}: {why}")
print(f"\n{total - len(survived)}/{total} caught; survivors: {survived}")
sys.exit(1 if survived else 0)
