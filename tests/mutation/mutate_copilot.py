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
    ('facts not redacted', 'facts, _ = redact(clean_text(project_facts(info["path"]))[:FACTS_CHARS])', 'facts = project_facts(info["path"])'),
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
    ('question not redacted', 'question = redact(" ".join(clean_text((args.question or "")[:20_000]).split()))[0][:500]', 'question = " ".join(clean_text((args.question or "")[:20_000]).split())[:500]'),
    ('SIGTERM not handled', 'signal.signal(signal.SIGTERM, _on_sigterm)', 'pass'),
    ('stdout encoding errors fatal', 'stream.reconfigure(errors="replace")', 'pass'),
    ('kv scanner off', '    text, n = _redact_kv(text)\n    count += n\n', ''),
    ('escaped closing quote of a name', 'if k + 1 < n and text[k] == "\\\\" and text[k + 1] in "\\"\'":', 'if False:'),
    ('unquoted value cut at ; and ,', '|[^\\s"\']+|["\']\\S*)"""', '|[^\\s"\';,]+|["\']\\S*)"""'),
    ('unterminated quote not redacted', '|[^\\s"\']+|["\']\\S*)"""', '|[^\\s"\']+)"""'),
    ('escaped-quoted value not redacted', '|\\\\"[^"\\\\]*\\\\"|\\\\\'[^\'\\\\]*\\\\\'', ''),
    ('terraform value object', 'if k < n and text[k] == "{":', 'if False:'),
    ('only 10 blanks', 'MAX_BLANKS = 40', 'MAX_BLANKS = 10'),
    ('token counts redacted', 'if (name.startswith("tokens") and not long_value and _COUNT_VALUE.fullmatch(value) and not _SECRET_WORD.search(name)) or _TOKENIZER_NAME.fullmatch(name):', 'if False:'),
    ('PWD redacted', 'if name == "pwd" and value[:1] in ("/", "~"):', 'if False:'),
    ('benign values redacted', 'if not long_value and (not value or raw in _BENIGN_VALUES or value in _BENIGN_VALUES):', 'if False:'),
    ('key mention hides what follows', 'if _KEY_BODY.match(text, b.end()):', 'if True:'),
    ('unterminated key kept', 'if _KEY_BODY.match(text, b.end()):', 'if False:'),
    ('dangling END kept', 'if end and not _KEY_BEGIN.search(text[:end.start()]):', 'if False:'),
    ('invisible characters kept', ' and ord(c) not in _INVISIBLE', ''),
    ('private-use and unassigned kept', '"Zp", "Co", "Cn"}', '"Zp"}'),
    ('mentions not neutralised', 'return neutralize_mentions(\n        "You are helping', 'return (\n        "You are helping'),
    ('mentions neutralised at line start only', '_MENTION = re.compile(r"(?<!\\w)@|@(?!\\w)")', '_MENTION = re.compile(r"(?m)^@")'),
    ('mentions neutralised after whitespace only', '_MENTION = re.compile(r"(?<!\\w)@|@(?!\\w)")', '_MENTION = re.compile(r"(?m)(^|(?<=\\s))@(?=\\S)")'),
    ('every at sign neutralised', '_MENTION = re.compile(r"(?<!\\w)@|@(?!\\w)")', '_MENTION = re.compile(r"@")'),
    ('URL password: old terminator', '[^\\s/]*?@(?=(?:[\\w.-]+|\\[[0-9A-Fa-f:.]+\\])(?::\\d+)?(?![\\w@-]|\\.\\w))', '[^\\s/]*?@(?=(?:[\\w.-]+|\\[[0-9A-Fa-f:.]+\\])(?::\\d+)?(?:[/\\s\\"\'<>]|$))'),
    ('URL token: old terminator', '[^\\s/@:]+@(?=(?:[\\w.-]+|\\[[0-9A-Fa-f:.]+\\])(?::\\d+)?(?![\\w@-]|\\.\\w))', '[^\\s/@:]+@(?=(?:[\\w.-]+|\\[[0-9A-Fa-f:.]+\\])(?::\\d+)?(?:[/\\s\\"\'<>]|$))'),
    ('URL password: host may end at a dot', '[^\\s/]*?@(?=(?:[\\w.-]+|\\[[0-9A-Fa-f:.]+\\])(?::\\d+)?(?![\\w@-]|\\.\\w))', '[^\\s/]*?@(?=(?:[\\w.-]+|\\[[0-9A-Fa-f:.]+\\])(?::\\d+)?(?![\\w@-]))'),
    ('fence boundary collision unchecked', 'while boundary in output or boundary in facts:', 'while False:'),
    ('redaction count from the whole capture', 'redactions = len(_REDACTED_MARK.findall(text)) + len(_REDACTED_MARK.findall(facts))', 'redactions = len(_REDACTED_MARK.findall(text)) + len(_REDACTED_MARK.findall(facts)) + redact(clean_text(raw))[1]'),
    ('error line not sanitised', 'print(f"groundwork copilot: {printable(str(e))}", file=sys.stderr)', 'print(f"groundwork copilot: {str(e)}", file=sys.stderr)'),
    ('paragraph separator kept', '"Zl", "Zp", "Co"', '"Zl", "Co"'),
    ('quoted-key cookie header missed', 'cookie[\\\\"\']{0,4}[ \\t]{0,5}:', 'cookie[ \\t]{0,5}:'),
    ('any tokenizer-prefixed name exempt', '_TOKENIZER_NAME.fullmatch(name)', 'name.startswith("tokenizer")'),
    ('question cut before redaction', 'question = redact(" ".join(clean_text((args.question or "")[:20_000]).split()))[0][:500]', 'question = redact(" ".join(clean_text((args.question or "")[:20_000]).split())[:500])[0]'),
    ('secret-named token counts exempt', ' and not _SECRET_WORD.search(name)', ''),
    ('option cluster -sSb not matched', '(?:-[A-Za-z]*b|--cookie)', '(?:-b|--cookie)'),
    ('authorization key after a literal escape missed', '(?:\\b|(?<=_)|(?<=\\\\n)|(?<=\\\\r)|(?<=\\\\t))((?:proxy-)?authorization', '\\b((?:proxy-)?authorization'),
    ('escaped-JSON Authorization key missed', 'authorization[\\\\"\']{0,4}', 'authorization["\']?'),
    ('cookie key after a literal \\r\\n missed', '(?:\\b|(?<=_)|(?<=\\\\n)|(?<=\\\\r)|(?<=\\\\t))((?:set-)?cookie[\\\\"\']{0,4}', '\\b((?:set-)?cookie[\\\\"\']{0,4}'),
    ('ANSI-C quoted jar not matched', "\\$'(?:[^'\\\\]|\\\\.)*'|", ''),
    ('escaped quote inside a quoted jar not handled', '"(?=(?:[^"\\\\\\r\\n]|\\\\.)*=)(?:[^"\\\\]|\\\\.)*"', '"(?=[^"\\r\\n]*=)[^"]*"'),
    ("quoted -b value needs no '='", "|'(?=[^'\\r\\n]*=)[^']*'|", "|'[^']*'|"),
    ("unquoted -b value needs no '='", '|[^\\s\'"$\\\\]*=\\S*)', '|\\S+)'),
    ('quoted-key pattern eats the word value', '(?!["\']value["\'][ \\t]*[:=])([\'"])', '([\'"])'),
    ('name/value pairs missed', '["\']?value["\']?[ \\t]*[:=][ \\t]*)(?:"[^"\\r\\n]*"|', '["\']?valuex["\']?[ \\t]*[:=][ \\t]*)(?:"[^"\\r\\n]*"|'),
    ('server directives missed', '(?:proxy_set_header|proxy_pass_header|add_header|fastcgi_param|', '(?:proxy_pass_headerx|'),
    ('curl -v added cookie missed', '(?:Added|Replaced)', '(?:Addedx|Replacedx)'),
    ('auth anywhere in a tokens name', '(?:^|[_.-])auth(?:orization)?(?:$|[_.-])', 'auth'),
    ('missing tool is a raw exception', 'raise CopilotError(f"\'{name}\' is not installed or not on PATH")', 'raise FileNotFoundError(name)'),
    ('authorization: first word only', '(?:\\[(?!\\])[^\\]]*\\]|\\[(?!\\])[\\s\\S]*|"[^"]*"|\'[^\']*\'|[^\\r\\n]+)', '(?:"[^"]*"|\'[^\']*\'|[^\\s\\r\\n]+)'),
    ('authorization array not followed', '(?:\\[(?!\\])[^\\]]*\\]|\\[(?!\\])[\\s\\S]*|"[^"]*"|\'[^\']*\'|[^\\r\\n]+)', '(?:"[^"]*"|\'[^\']*\'|[^\\r\\n]+)'),
    ('authorization: empty brackets end the redaction (Go %#v)', '(?:\\[(?!\\])[^\\]]*\\]|\\[(?!\\])[\\s\\S]*|"[^"]*"|', '(?:\\[[^\\]]*\\]|\\[[\\s\\S]*|"[^"]*"|'),
    ('cookie list not followed through its brackets', '(?:\\[(?!\\])[^\\]]*\\]|\\[(?!\\])[\\s\\S]*|[^\\r\\n]+)', '(?:[^\\r\\n]+)'),
    ('cookie: empty brackets end the redaction (Go %#v)', '(?:\\[(?!\\])[^\\]]*\\]|\\[(?!\\])[\\s\\S]*|[^\\r\\n]+)', '(?:\\[[^\\]]*\\]|\\[[\\s\\S]*|[^\\r\\n]+)'),
    ('unclosed cookie list not redacted to the end of the text', '|\\[(?!\\])[\\s\\S]*|[^\\r\\n]+)', '|[^\\r\\n]+)'),
    ('cookie list closing bracket capped at 16,000 characters', '(?:\\[(?!\\])[^\\]]*\\]|\\[(?!\\])[\\s\\S]*|[^\\r\\n]+)', '(?:\\[(?!\\])[^\\]]{0,16000}\\]|[^\\r\\n]+)'),
    ('folded cookie header not followed', 'if anchor is not None and j > i:', 'if False:'),
    ('folded cookie: continuation lines capped at ten', 'while j < n and _FOLD_LINE.match(lines[j]):', 'while j < n and j - i < 10 and _FOLD_LINE.match(lines[j]):'),
    ('YAML list at column 0 not followed', '_FOLD_LINE = re.compile(r"(?:[ \\t]+|-[ \\t]+)[^\\r\\n]")', '_FOLD_LINE = re.compile(r"(?:[ \\t]+)[^\\r\\n]")'),
    ('folded cookie key only at the start of a line', '_FOLD_KEY = re.compile(r"(?i)(?:\\b|(?<=_))(?:set-)?cookie', '_FOLD_KEY = re.compile(r"(?i)^(?:set-)?cookie'),
    ("folded first line ending in ';' ignored", 'if stripped_len and line[stripped_len - 1] == ";" and keys[0] < stripped_len:', 'if False:'),
    ('empty-valued cookie key ignored', 'elif keys[-1] >= stripped_len:', 'elif False:'),
    ('folded cookie function not called', 'text, n = _redact_folded(text)\n    count += n\n', ''),
    ('glued quoted -b not matched', '(?:[ \\t=]+|(?:\\\\{1,4}[trn])+|(?=[\'"\\\\$]))', '(?:[ \\t=]+|(?:\\\\{1,4}[trn])+)'),
    ('literal backslash-t separator not matched', '(?:[ \\t=]+|(?:\\\\{1,4}[trn])+|', '(?:[ \\t=]+|'),
    ('escaped double-quoted jar not matched', '|\\\\{1,4}"[^"]*?\\\\{1,4}"|\\\\{1,4}\'', "|\\\\{1,4}'"),
    ('escaped single-quoted jar not matched', "|\\\\{1,4}'[^']*?\\\\{1,4}'|", '|'),
    ('dollar double-quoted jar not matched', '|\\$"(?:[^"\\\\]|\\\\.)*"|', '|'),
    ('dollar escaped double-quoted jar not matched', '|\\$\\\\{1,4}"[^"]*?\\\\{1,4}"', ''),
    ('quoted key + quoted value (rawHeaders, tuples) missed', '[ \\t]*,\\s*)(?!["\']value["\'][ \\t]*[:=])([\'"])(?:(?!\\2)[^\\r\\n])*\\2', '[ \\t]*,\\s*)(?!["\']value["\'][ \\t]*[:=])([\'"])(?!x)x\\2'),
    ('quoted key: value on the next line missed', '[ \\t]*,\\s*)(?!["\']value', '[ \\t]*,[ \\t]*)(?!["\']value'),
    ('name/value pairs: value on the next line missed', '["\']?[\\s,\\-]*["\']?value', '["\']?[ \\t]*["\']?value'),
    ('quoted key and value: blank chain restored (quadratic)', '[ \\t]*,\\s*)(?!["\']value', '[ \\t]*,[ \\t]*\\r?\\n?[ \\t]*)(?!["\']value'),
    ('name/value pairs: blank chain restored (quadratic)', '["\']?[\\s,\\-]*["\']?value', '["\']?[ \\t]*,?[ \\t]*\\r?\\n?[ \\t]*-?[ \\t]*["\']?value'),
    ('kv: an exempt name hides the secret flag inside its value', '        raw = vm.group(0).strip(', '        pos = vm.end()\n        raw = vm.group(0).strip('),
    ('kv: the value probe is unbounded', 'limit = min(n, k + PROBE_CHARS)', 'limit = n'),
    ('kv: a long value is not read in full when redacted', '        if long_value:\n            vm = _VALUE_RE.match(text, k)', '        if False:\n            vm = _VALUE_RE.match(text, k)'),
    ('kv: a long value can be a benign word or a count', 'if not long_value and (not value or raw in _BENIGN_VALUES or value in _BENIGN_VALUES):', 'if (not value or raw in _BENIGN_VALUES or value in _BENIGN_VALUES):'),
    ('kv: a long digit prefix is a count', '(name.startswith("tokens") and not long_value and _COUNT_VALUE', '(name.startswith("tokens") and _COUNT_VALUE'),
    ('JWT starts after a hyphen (quadratic)', '(?<![\\w-])(eyJ)[A-Za-z0-9_-]{8,}', '\\b(eyJ)[A-Za-z0-9_-]{8,}'),
    ('git facts not bounded before redaction', 'clean_text(project_facts(info["path"]))[:FACTS_CHARS]', 'clean_text(project_facts(info["path"]))'),
    ('folded cookie key without escaped quotes', 'cookie[\\\\\\"\']{0,4}[ \\t]*:")', 'cookie[\\"\']?[ \\t]*:")'),
    ('kv: a quote whose closer is past the probe is conclusive', '(vm.end() >= limit or (quoted and not _CLOSED_RE.match(text, k, limit)))', 'vm.end() >= limit'),
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
