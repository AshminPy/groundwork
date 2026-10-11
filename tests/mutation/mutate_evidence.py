"""Mutation check for hooks/groundwork_evidence.py and the telemetry hook's turn detection.

Each mutant removes or weakens one safety clause; tests/test_evidence.py must then fail. A mutant that makes the
tests hang (timeout) counts as caught: the clause it removed was bounding something.

Run from the repository root:

    python3 tests/mutation/mutate_evidence.py [mutant name ...]

It works on a COPY of the tracked files in a temporary directory, so the working tree is never modified and an
interrupted run cannot leave a mutated hook behind. Not collected by pytest (the name does not start with test_)."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path.cwd()
WORK = Path(tempfile.mkdtemp(prefix="gw-mutate-evidence-"))
files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.split(b"\0")
for rel in filter(None, files):
    src = ROOT / rel.decode()
    if src.is_file():
        dst = WORK / rel.decode()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
TARGET = WORK / "hooks" / "groundwork_evidence.py"
TELEM = WORK / "hooks" / "groundwork_telemetry.py"
ORIG = TARGET.read_text()
ORIG_T = TELEM.read_text()
TIMEOUT_S = 180

MUTANTS = [
    ("allow ${ expansion", TARGET, r'''">(", "${", "$'"''', r'''">(", "$'"'''),
    ("allow comments", TARGET, 'if c == "#" and (not cur or cur[-1] in " \\t\\n;&|()"):\n            return None', 'if False:\n            return None'),
    ("allow subshell parens", TARGET, 'if c in "()":\n            return None', 'if False:\n            return None'),
    ("allow control keywords", TARGET, "        if _command_word(seg) in _KEYWORDS:\n            return None", "        if False:\n            return None"),
    ("ignore order of verification", TARGET, 'pass_valid = st["pass"] is not None and st["pass"] > lm', 'pass_valid = st["pass"] is not None'),
    ("ignore order of runtime", TARGET, 'runtime_valid = st["runtime"] is not None and st["runtime"] > lm', 'runtime_valid = st["runtime"] is not None'),
    ("unattributed run keeps earlier pass", TARGET, 'st["pass"] = None  # a test-shaped run', 'pass  # a test-shaped run'),
    ("first review block wins", TARGET, "for line in _lines_from(text, headings[-1].end(), 120):", "for line in _lines_from(text, headings[0].end(), 120):"),
    ("'preview' is a reviewer", TARGET, '_REVIEW_KIND = re.compile(r"(?<![a-z])review")', '_REVIEW_KIND = re.compile(r"review")'),
    ("background run credited", TARGET, 'if not runs or background:', 'if not runs:'),
    ("help/version credited", TARGET, 'runs = not _NO_RUN.search(rest)', 'runs = True'),
    ("curl without --fail credited", TARGET, '(word == "curl" and not fail)', 'False'),
    ("any python script is a test", TARGET, 'if re.match(r"python3?\\s", rest) and not _PY_TEST_SCRIPT.match(rest):\n        return None', 'pass'),
    ("sidechain not filtered", TARGET, 'entries = [e for e in entries if isinstance(e, dict) and not e.get("isSidechain")]', 'entries = [e for e in entries if isinstance(e, dict)]'),
    ("redact after clip (secret straddling the cap)", TARGET, 'return _clip(_redact(_clip(s, 4000)), n)', 'return _redact(_clip(s, n))'),
    ("no control-char strip", TARGET, 's = " ".join(_drop_invisible(_ANSI.sub("", str(s))).split())', 's = " ".join(str(s).split())'),
    ("URL userinfo kept", TARGET, "return f\"{p.scheme}://{p.netloc.rsplit('@', 1)[-1]}{p.path}\"", 'return f"{p.scheme}://{p.netloc}{p.path}"'),
    ("failing scope cleared by any pass", TARGET, 'failing[runner] = {k for k in failing[runner] if k[0] != cwd}', 'failing.pop(runner, None)'),
    ("empty MCP result credited", TARGET, "t = text.strip()\n    if t.lower() in", "t = text.strip()\n    if False and t.lower() in"),
    ("mutating MCP tool credited", TARGET, 'and not (_tool_words(tool) & _MUTATING_WORDS)', ''),
    ("per-kind cap removed", TARGET, 'if len(bucket) >= COLLECT_PER_KIND:', 'if False:'),
    ("cross-project transcript fallback", TARGET, '            return best\n    return None\n', '            return best\n    import glob\n    c = sorted(glob.glob(str(cfg / "projects" / "*" / "*.jsonl")), key=os.path.getmtime)\n    return Path(c[-1]) if c else None\n'),
    ("write redirect not a change", TARGET, 'return ">" in rest', 'return False'),
    ("find -delete treated as read", TARGET, 'return not any(w in _FIND_WRITES for w in words)\n    if words[0] == "sed":', 'return True\n    if words[0] == "sed":'),
    ("read behind a failing reader credited", TARGET, 'return bool(text.strip()) and not _READ_ERROR.search(text)', 'return bool(text.strip())'),
    ("non-review agent not a change", TARGET, 'mutate((idx, 0))  # a general-purpose subagent may edit files', 'pass'),
    ("ambiguous command not a change", TARGET, 'mutate((idx, 0))  # could have changed anything; nothing is credited', 'pass'),
    ("unreadable transcript records evidence", TELEM, 'if telemetry_summary is not None and entries:', 'if telemetry_summary is not None:'),
    ("keyword check ignores quotes/redirections", TARGET, "if _command_word(seg) in _KEYWORDS:", 'if (seg.split() or [""])[0] in _KEYWORDS:'),
    ("backslash-newline allowed", TARGET, r'''"$'", '$"', "\\\n")):''', r'''"$'", '$"')):'''),
    ("banner spoofs a policy block", TARGET, 'return is_error and re.match(r"PreToolUse:\\S+ hook error", text) is not None', 'return re.match(r"PreToolUse:\\S+ hook error", text) is not None'),
    ("runtime writes ignored", TARGET, "if _writes_file(segment) or _fetch_writes(segment):", "if False:"),
    ("unknown tools ignored", TARGET, "if name not in _BENIGN_TOOLS:\n                mutate((idx, 0))", "if False:\n                mutate((idx, 0))"),
    ("local MCP writers ignored", TARGET, 'if not is_read and server != "github":\n                mutate((idx, 0))', 'if False:\n                mutate((idx, 0))'),
    ("--collectonly credited", TARGET, "--collectonly|", ""),
    ("make test-clean credited", TARGET, 'if follower and not (follower.isspace() or follower == "="):', "if False:"),
    ("no positive summary needed", TARGET, "_FAIL_COUNT.search(text) or not _positive_summary(runner, text)", "_FAIL_COUNT.search(text)"),
    ("long review lines parsed", TARGET, "if len(stripped) > 200:", "if False:"),
    ("quoted review block accepted", TARGET, "if len(text[headings[-1].end() + consumed:].strip()) > 600:", "if False:"),
    ("hook feedback starts a turn", TELEM, ' or e.get("isMeta")', ""),
    ("notifications start a turn", TELEM, 'if isinstance(origin, dict) and origin.get("kind") != "human":', "if False:"),
    ("unattributable failure forgotten", TARGET, 'if _FAIL_COUNT.search(text) or "FAILED" in text:\n                            st["failing"]', 'if False:\n                            st["failing"]'),
    ("cwd ignored in scope", TARGET, "cwd = _cwd_of(segs, j)", 'cwd = ""'),
    ("selection flags dropped from scope", TARGET, "        else:\n            scope.append(t)", '        elif not t.startswith("-"):\n            scope.append(t)'),
    ("receipt command lowers its own estimate", TARGET, 'if w == "groundwork":', 'if False:'),
    ("edit-only turn is NONE", TARGET, "        if not changed:\n            return \"NONE\"", "        if True:\n            return \"NONE\""),
    ("review blocks joined with a space", TARGET, 'return "\\n".join(str(b.get("text", ""))', 'return " ".join(str(b.get("text", ""))'),
    ("risky env prefix trusted", TARGET, "if _RISKY_ENV.search(segment[:_PREFIX.match(segment).end()]):", "if False:"),
    ("long commands parsed", TARGET, "len(text) > MAX_COMMAND_CHARS or ", ""),
    ("curl --request POST credited", TARGET, 'elif name in ("--request", "--method"):', 'elif name in ():'),
    ("sub-agent transcript picked", TARGET, 'if not c.name.startswith("agent-")', "if True"),
    ("MCP hyphenated reads missed", TARGET, 'READ_VERB = re.compile(r"(?:^|[_-])(?:get|list|read|search|query|describe|fetch|show|view)(?:[_-]|$)")', 'READ_VERB = re.compile(r"(?:^|_)(?:get|list|read|search|query|describe|fetch|show|view)(?:_|$)")'),
    ("quoted > is a redirection", TARGET, "    rest = re.sub(r\"'[^']*'|", "    rest = re.sub(r\"ZZZ|"),
    ("git -C unrecognised", TARGET, 'while len(words) > 2 and words[1] in ("-C", "-c"):', "while False:"),
    ("declared label: last word", TARGET, 't = _drop_invisible(_ANSI.sub("", str(declared or ""))).upper()[:60]', 't = _drop_invisible(_ANSI.sub("", str(declared or ""))).upper()[:3]'),
    ('npm summary: leading \\s* before ^ (quadratic)', TARGET, '(?m:^[ \\t]*(?:PASS|ok)\\b)', '(?m:^\\s*(?:PASS|ok)\\b)'),
    ('result field key unchecked', TARGET, 'if not _FIELD_KEY.fullmatch(key):\n        return None', 'if False:\n        return None'),
    ('no segment cap', TARGET, 'if len(pieces) > MAX_SEGMENTS:\n        return None', 'if False:\n        return None'),
    ('no work budget', TARGET, 'if time.monotonic() > deadline:\n            raise EvidenceBudgetExceeded(f"more than {budget_s:g} s of work")', 'if False:\n            raise EvidenceBudgetExceeded("x")'),
    ('budget bound at definition', TARGET, 'budget_s = WORK_BUDGET_S if budget_s is None else budget_s', 'budget_s = 3.0 if budget_s is None else budget_s'),
    ('lone surrogates kept', TARGET, '{"Cc", "Cf", "Cs", "Zl"', '{"Cc", "Cf", "Zl"'),
    ('unreadable transcript path raises', TARGET, 'except (OSError, ValueError):  # an unsearchable directory', 'except ZeroDivisionError:  # an unsearchable directory'),
    ('stdout encoding strict', TARGET, 'stream.reconfigure(errors="replace")', 'stream.reconfigure(errors="strict")'),
    ('budget overrun is a generic error', TARGET, 'except EvidenceBudgetExceeded:\n        return _unknown', 'except KeyError:\n        return _unknown'),
    ('unmodelled changes not counted', TARGET, 'if not edit:\n            sig["other_changes"] += 1', 'if False:\n            sig["other_changes"] += 1'),
    ('redirect notice credited as a fetch', TARGET, ' and not _REDIRECT.match(text)', ''),
    ('empty output credited', TARGET, 'if not stripped or _NO_OUTPUT.fullmatch(stripped) or _NOTHING_RAN.search(text):', 'if _NO_OUTPUT.fullmatch(stripped) or _NOTHING_RAN.search(text):'),
    ('no-output placeholder credited', TARGET, 'if not stripped or _NO_OUTPUT.fullmatch(stripped) or _NOTHING_RAN.search(text):', 'if not stripped or _NOTHING_RAN.search(text):'),
    ("'nothing to be done' credited", TARGET, 'if not stripped or _NO_OUTPUT.fullmatch(stripped) or _NOTHING_RAN.search(text):', 'if not stripped or _NO_OUTPUT.fullmatch(stripped):'),
    ('go: no tests to run credited', TARGET, '^ok\\b(?![^\\n]*\\[no tests to run\\])', '^ok\\b'),
    ('cookie redacted up to one token', TARGET, '[^\'\\"\\n]+"), "cookie: [redacted]"', '\\S+"), "cookie: [redacted]"'),
    ('glued -u not redacted', TARGET, '(?:^|(?<=\\s))-u[^\\s:=]+:\\S+', '(?!x)x'),
    ('MCP in-place editors trusted', TARGET, '"replace", "edit", "rename", "clear", "truncate", ', ''),
    ('clustered -d/-F/-T not seen', TARGET, 'elif c in "dFT":', 'elif c in "":'),
    ('option letters case-insensitive', TARGET, 'elif c in "dFT":', 'elif c in "dft":'),
    ('clustered -X not read', TARGET, 'elif c == "X":', 'elif c == "\\0":'),
    ('-f (fail) not read', TARGET, 'if c == "f":\n                    fail = True', 'if c == "f" and False:\n                    fail = True'),
    ('--upload-file not an action', TARGET, '"--upload-file", ', ''),
    ('--request not read', TARGET, 'if value(val if eq else "").upper() not in ("GET", "HEAD"):', 'if False:'),
    ('clustered -O not a write', TARGET, 'elif c == "O":\n                    writes = True', 'elif c == "\\0":\n                    writes = True'),
    ('-o /dev/null is a write', TARGET, '_NO_FILE = ("/dev/null", "-")', '_NO_FILE = ()'),
    ('wget without --spider is not a write', TARGET, 'if word == "wget" and "--spider" not in rest.split():\n        return True', 'if False:\n        return True'),
    ('unreadable curl line credited', TARGET, 'except ValueError:\n        return False, True, True', 'except ValueError:\n        return True, False, False'),
    ('review findings in an off layout ignored', TARGET, 'if (must_fix or 0) > 0 or verdict == "changes-required" or _PLAIN_FINDINGS.search(tail[:2000]):', 'if False:'),
    ('plain findings line ignored', TARGET, ' or _PLAIN_FINDINGS.search(tail[:2000])', ''),
    ('legacy Task tool ignored', TARGET, 'elif name in ("Agent", "Task"):', 'elif name in ("Agent",):'),
    ('failed Edit counts as a change', TARGET, 'if fp and not is_error:', 'if fp:'),
    ('0 passed counts as a pass', TARGET, '_PASS_COUNT = re.compile(r"\\b[1-9]\\d*\\s+passed\\b")', '_PASS_COUNT = re.compile(r"\\b\\d+\\s+passed\\b")'),
    # round 5 (security review): failed runtime checks, -b cookies, command words, bounded work
    ('failed runtime check is not a cap', TARGET, '    if sig.get("runtime_failed"):\n        capped = True', '    if False:\n        capped = True'),
    ('failed runtime check not recorded', TARGET, 'st["runtime_failing"] = True', 'pass'),
    ('later runtime success keeps the failure', TARGET, 'st["runtime_failing"] = False  # the last runtime result wins', 'pass  # the last runtime result wins'),
    ('-b cookie not redacted', TARGET, '(?:-b|--cookie)(?:\\s+|=)', '(?:--cookie)(?:\\s+|=)'),
    ('read-only git word is a prefix match', TARGET, 'rev-parse))(?=\\s|$)")\n# A deliberately', 'rev-parse))")\n# A deliberately'),
    ('review lines unbounded', TARGET, 'while pos < n and len(out) < limit:', 'while pos < n:'),
    ('evidence budget ignores the time the hook used', TELEM, 'budget_s=min(EVIDENCE_BUDGET_S, time_left)', 'budget_s=EVIDENCE_BUDGET_S'),
    ('tail read capped per step, not in total', TELEM, 'take = min(step, pos, TAIL_CAP - (size - pos))', 'take = min(step, pos)'),
    # round 6 (correctness review): turn boundary, redirects, lone failure, pipefail in a stage, make
    ('compaction summary starts a turn', TELEM, ' or e.get("isCompactSummary")', ''),
    ('redirect token in a test scope', TARGET, 'elif re.match(r"\\d*>|&>|\\d*<", t) or cosmetic.match(t):', 'elif cosmetic.match(t):'),
    ('redirect target in a test scope', TARGET, 'elif re.fullmatch(r"\\d*>>?|&>>?", t):\n            skip = True', 'elif False:\n            skip = True'),
    ('make up to date is a pass', TARGET, '|(?m:^make\\S*: [^\\n]* is up to date)|', '|'),
    ('pipefail in a pipeline stage applies', TARGET, ' and (not conns or conns[0] != "|")', ''),
    ('lone failure is NONE', TARGET, 'if not sig.get("inspected_any") and (sig["tests_last_ok"] is False or sig.get("runtime_failed")):', 'if False:'),
]

survived = []
which = sys.argv[1:]  # optional: run only the mutants with these names
for name, path, old, new in MUTANTS:
    if which and name not in which:
        continue
    text = path.read_text()
    if old not in text:
        print(f"STALE (pattern not found): {name}")
        survived.append(name + " [pattern not found]")
        continue
    path.write_text(text.replace(old, new, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "tests/test_evidence.py", "-q", "-x"], cwd=WORK,
                           capture_output=True, text=True, timeout=TIMEOUT_S)
        caught, how = r.returncode != 0, "caught   "
    except subprocess.TimeoutExpired:
        caught, how = True, "caught (timeout) "
    finally:
        TARGET.write_text(ORIG)
        TELEM.write_text(ORIG_T)
    print((how if caught else "SURVIVED ") + name, flush=True)
    if not caught:
        survived.append(name)
shutil.rmtree(WORK, ignore_errors=True)
total = len([m for m in MUTANTS if not which or m[0] in which])
print(f"\n{total - len(survived)}/{total} caught; survivors: {survived}")
sys.exit(1 if survived else 0)
