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
    ("keyword check ignores quotes/redirections", TARGET, "if _command_word(seg) in _KEYWORDS:", 'if (seg.split() or [""])[0] in _KEYWORDS:'),
    ("backslash-newline allowed", TARGET, r'''"$'", '$"', "\\\n")):''', r'''"$'", '$"')):'''),
    ("banner spoofs a policy block", TARGET, 'return is_error and _REFUSED.match(text) is not None', 'return _REFUSED.match(text) is not None'),
    ("runtime writes ignored", TARGET, "if _writes_file(segment) or _fetch_writes(segment):", "if False:"),
    ("unknown tools ignored", TARGET, "if name not in _BENIGN_TOOLS:\n                mutate((idx, 0))", "if False:\n                mutate((idx, 0))"),
    ("local MCP writers ignored", TARGET, 'if not is_read and server != "github":\n                mutate((idx, 0))', 'if False:\n                mutate((idx, 0))'),
    ("--collectonly credited", TARGET, "--collectonly|", ""),
    ("make test-clean credited", TARGET, 'if follower and not (follower.isspace() or follower == "="):', "if False:"),
    ("no positive summary needed", TARGET, "facts.fail_count() or not facts.summary(runner)", "facts.fail_count()"),
    ("long review lines parsed", TARGET, "if len(stripped) > 200:", "if False:"),
    ("quoted review block accepted", TARGET, "if len(text[headings[-1].end() + consumed:].strip()) > 600:", "if False:"),
    ("hook feedback starts a turn", TELEM, ' or e.get("isMeta")', ""),
    ("notifications start a turn", TELEM, 'if isinstance(origin, dict) and origin.get("kind") != "human":', "if False:"),
    ("unattributable failure forgotten", TARGET, 'if facts.fail_count() or facts.failed_word():\n                            st["failing"]', 'if False:\n                            st["failing"]'),
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
    ('compaction request not recognised by its words', TELEM, '_entry_text(e).lstrip().startswith(_COMPACTION_PROMPT):\n        return True', 'False:\n        return True'),
    ('compaction request not recognised by a following boundary', TELEM, 'if later.get("subtype") == "compact_boundary" or later.get("isCompactSummary"):\n            return True', 'if False:\n            return True'),
    ('look-ahead from a typed prompt', TELEM, 'if e.get("turnOrigin") != "sdk":\n        return False', 'if False:\n        return False'),
    ('metadata heading with CRLF', TELEM, 'Harness metadata(?:\\*\\*)?[ \\t\\r]*$', 'Harness metadata(?:\\*\\*)?[ \\t]*$'),
    ('evidence derived with no time left', TELEM, ' and time_left >= MIN_EVIDENCE_S:', ':'),
    ('classifier and safety-check denial not a refusal', TARGET, '|for this (?:command|action) was denied)', ')'),
    ('runtime outcome read from test-runner words', TARGET, 'if (tests and not is_error and all(c == "|" for c in after)', 'if (not is_error and all(c == "|" for c in after)'),
    ('any runtime success clears every failed check', TARGET, 'st["runtime_failing"].discard(key)', 'st["runtime_failing"].clear()'),
    ('text-wide facts recomputed per segment', TARGET, '        if key not in self._c:', '        if True:'),
    ('deadline not checked between segments', TARGET, '            for j, segment in enumerate(segs):\n                if time.monotonic() > deadline:\n                    raise EvidenceBudgetExceeded(f"more than {budget_s:g} s of work")', '            for j, segment in enumerate(segs):'),
    ('deadline not checked while pairing tool calls', TARGET, '        if n % 2048 == 0 and time.monotonic() > deadline:\n            raise EvidenceBudgetExceeded(f"more than {budget_s:g} s of work")\n        content', '        content'),
    ('bare variable assignment is a change', TARGET, '    if len(words) == 1 and re.fullmatch(r"\\w+=\\S*", w):\n        return not _RISKY_ENV.search(w)', '    if False:\n        return not _RISKY_ENV.search(w)'),
    ('bare PATH= assignment is benign', TARGET, 'return not _RISKY_ENV.search(w)', 'return True'),
    ('ReadNotifications is a change', TARGET, ', "ListAgents", "ReadNotifications"}', ', "ListAgents"}'),
    ('--cert password not redacted', TARGET, '    (re.compile(r"(?:^|(?<=\\s))(--cert[= ]\\s*[^\\s:]*:)\\S+"), r"\\1[redacted]"),  # --cert file:password\n', ''),
    ('cookie value with an inner quoted part cut short', TARGET, '(?:[^\'\\"\\n]|(?<==)\\"[^\\"\\n]*\\")+', '[^\'\\"\\n]+'),
    ('unreadable transcript records evidence', TELEM, 'if telemetry_summary is not None and entries and', 'if telemetry_summary is not None and'),
    ('cookie redacted up to one token', TARGET, '(?:[^\'\\"\\n]|(?<==)\\"[^\\"\\n]*\\")+"), "cookie: [redacted]"', '\\S+"), "cookie: [redacted]"'),
    ('failed runtime check not recorded', TARGET, 'st["runtime_failing"].add(key)', 'pass'),
    ('later runtime success keeps the failure', TARGET, 'st["runtime_failing"].discard(key)', 'pass'),
    ('permission denial without a command not a refusal', TARGET, 'Permission (?:to use \\S+ (?:with|has been denied)', 'Permission (?:to use \\S+ (?:with)'),
    ('built-in safety check and classifier denial not a refusal', TARGET, '|for this (?:command|action) was denied)', ')'),
    ('user rejection not a refusal', TARGET, "|The user doesn't want to proceed with this tool use", ''),
    ('classifier without a verdict not a refusal', TARGET, '|The server-side auto mode classifier', ''),
    ('approval prompts not a refusal', TARGET, '|This (?:Bash )?command (?:requires approval|contains multiple operations)', ''),
    ('blocked tool use not a refusal', TARGET, '|<tool_use_error>Blocked:', ''),
    ('refusal wording searched, not anchored', TARGET, '_REFUSED.match(text)', '_REFUSED.search(text)'),
    ('compaction look-ahead window of 20 entries', TELEM, 'entries[i + 1:i + 201]', 'entries[i + 1:i + 21]'),
    ('compaction look-ahead ignores another prompt', TELEM, '        if is_human_prompt(later):\n            return False  # another prompt ends the look-ahead\n', ''),
    ('REVIEW RESULT heading with CRLF', TARGET, 'REVIEW RESULT(?:\\*\\*)?[ \\t\\r]*$', 'REVIEW RESULT(?:\\*\\*)?[ \\t]*$'),
    ('look-ahead runs past a tool use', TELEM, 'for b in content):\n            return False\n        if is_human_prompt(later):', 'for b in content):\n            pass\n        if is_human_prompt(later):'),
    ('OVERALL with unbounded blanks', TELEM, 'Overall:\\s{0,20}\\**\\s{0,20}(', 'Overall:\\s*\\**\\s*('),
    ('STATUS_HEAD with unbounded blanks', TELEM, '(?:^|\\n)[ \\t]{0,20}(?:#+[ \\t]{0,20})?\\**[ \\t]{0,20}(?:Status|Result)', '(?:^|\\n)[ \\t]*(?:#+[ \\t]*)?\\**[ \\t]*(?:Status|Result)'),
    ('LEAD_HEAD with unbounded blanks', TELEM, '(?:^|\\n)[ \\t]{0,20}(?:#+[ \\t]{0,20})?\\**[ \\t]{0,20}(?:Answer|Recommendation', '(?:^|\\n)[ \\t]*(?:#+[ \\t]*)?\\**[ \\t]*(?:Answer|Recommendation'),
    ('compaction request without the SDK origin', TELEM, '    if e.get("turnOrigin") != "sdk":\n        return False  # a typed prompt may quote the summariser\'s words; only an SDK-originated entry is a request\n', ''),
    ('current_turn loses the line that straddles two chunks', TELEM, 'lines = (f.read(take) + carry).split(', 'lines = (f.read(take)).split('),
    ('current_turn chunk growth uncapped', TELEM, 'step = min(step * 2, TAIL_STEP_CAP)', 'step = min(step * 2, TAIL_CAP)'),
    ('build_record gives current_turn no deadline', TELEM, 'current_turn(data.get("transcript_path", ""), deadline=HOOK_START + HOOK_BUDGET_S)', 'current_turn(data.get("transcript_path", ""))'),
    ('reference text cleaned before it is cut', TARGET, '_clip(str(s)[:16_000], 4000)', '_clip(s, 4000)'),
    ('--pass not redacted', TARGET, '|--pass(?:\\s+|=)|--proxy-pass(?:\\s+|=)|--key-pass(?:\\s+|=))', ')'),
    ('redact after clip (secret straddling the cap)', TARGET, 'return _clip(_redact(_clip(str(s)[:16_000], 4000)), n)', 'return _redact(_clip(s, n))'),
    ('NOTHING_LEFT with unbounded blanks', TELEM, '\\s{0,20}\\**\\s{0,20}:\\s{0,20}\\**\\s{0,20}(?:none|nothing)', '\\s*\\**\\s*:\\s*\\**\\s*(?:none|nothing)'),
    ('a passed deadline returns nothing', TELEM, 'if deadline is not None and time.monotonic() > deadline:\n                    return _Turn(entries, bool(summariser))', 'if deadline is not None and time.monotonic() > deadline:\n                    return []'),
    ("the summariser's own Stop writes a record", TELEM, 'if getattr(entries, "summariser", False):\n        return {}', 'if False:\n        return {}'),
    ('user-rejected is not a denial kind', TARGET, '_DENIAL_KINDS = {"user-rejected", ', '_DENIAL_KINDS = {'),
    ('permission-rule is not a denial kind', TARGET, '"permission-rule", ', ''),
    ('refusal wording trusted from an MCP server', TARGET, '(not name.startswith("mcp__") and _blocked_by_policy(is_error, text))', '_blocked_by_policy(is_error, text)'),
    ("'A variable in this command' not a refusal", TARGET, '(?:A variable in (?:braces in )?this command|', '(?:A variable in braces in this command|'),
    ("'Contains brace with quote character' not a refusal", TARGET, '|Contains brace with quote character', ''),
    ("'sed in … needs approval' not a refusal", TARGET, '|sed in .{0,200} needs approval', ''),
    ('spaced redirection in a runtime key', TARGET, 'elif re.fullmatch(r"\\d*>>?|&>>?", w):\n            skip = True', 'elif False:\n            skip = True'),
    ('a closed pipe is a traceback', TARGET, 'except BrokenPipeError:  # `groundwork evidence | head -3`', 'except ZeroDivisionError:  # `groundwork evidence | head -3`'),
    ('compaction request starts a turn', TELEM, 'if is_compaction_request(entries, i):\n                        if summariser is None:', 'if False:\n                        if summariser is None:'),
    ('unverifiable-command prompts not a refusal', TARGET, "|(?:A variable in (?:braces in )?this command|Quoted text in this command) can't be checked before it runs", ''),
    ('current_turn ignores its deadline', TELEM, 'if deadline is not None and time.monotonic() > deadline:\n                    return _Turn(entries, bool(summariser))', 'if False:\n                    return _Turn(entries, bool(summariser))'),
    ('runtime key drops flags', TARGET, '        elif not re.match(r"\\d*[<>]|&>", w):\n            key.append(w)', '        elif not re.match(r"\\d*[<>]|&>", w) and not w.startswith("-"):\n            key.append(w)'),
    ('runtime key drops env prefixes', TARGET, '    for w in segment.split():\n        if skip:', '    for w in segment[_PREFIX.match(segment).end():].split():\n        if skip:'),
    ('runtime check keyed by its command word only', TARGET, '    return tuple(key)', '    return tuple(segment.split()[:1])'),
    ("redirect in a runtime check's key", TARGET, '        elif not re.match(r"\\d*[<>]|&>", w):\n            key.append(w)', '        else:\n            key.append(w)'),
    ('the summariser flag ignores the parent chain', TELEM, 'summariser = descends_from(entries, i, entries[i].get("uuid"))', 'summariser = True'),
    ('the parent chain is never followed', TELEM, '        cur = by_uuid.get(cur.get("parentUuid"))', '        cur = None'),
    ('the chain walk is unbounded', TELEM, '    for _ in range(10_000):\n        if cur is None:', '    while True:\n        if cur is None:'),
    ("a sub-agent's assistant entry is the last assistant entry", TELEM, 'e.get("type") == "assistant" and not e.get("isSidechain")), None)', 'e.get("type") == "assistant"), None)'),
    ('an entry without a uuid descends from a request without one', TELEM, '    if not isinstance(root_uuid, str):\n        return False\n', ''),
    ('interrupted and cancelled calls are refused', TARGET, 'kind = e.get("toolDenialKind")\n                if isinstance(kind, str) and kind in _DENIAL_KINDS:', 'kind = e.get("toolDenialKind")\n                if kind:'),
    ('toolDenialKind ignored', TARGET, 'kind = e.get("toolDenialKind")\n                if isinstance(kind, str) and kind in _DENIAL_KINDS:', 'kind = e.get("toolDenialKind")\n                if False:'),
    ('an unhashable toolDenialKind raises', TARGET, 'if isinstance(kind, str) and kind in _DENIAL_KINDS:', 'if kind in _DENIAL_KINDS:'),
    ('clustered -u password not redacted', TARGET, '(?:-[A-Za-z]{0,30}u(?:\\s+|(?=[^\\s:]{1,200}:))|--user\\s+|--proxy-user\\s+)', '(?:-u(?:\\s+)|--user\\s+|--proxy-user\\s+)'),
    ('glued -uuser:pw not redacted', TARGET, '-[A-Za-z]{0,30}u(?:\\s+|(?=[^\\s:]{1,200}:))', '-[A-Za-z]{0,30}u(?:\\s+)'),
    ('-u user name without a hyphen', TARGET, '(?=[^\\s:]{1,200}:))|--user', '(?=[^\\s=-]{1,200}:))|--user'),
    ('-u option cluster unbounded', TARGET, '-[A-Za-z]{0,30}u(?:', '-[A-Za-z]*u(?:'),
    ('-u look-ahead unbounded', TARGET, '(?=[^\\s:]{1,200}:))|--user', '(?=[^\\s:]+:))|--user'),
    ('-u option cluster of 9 letters or more not redacted', TARGET, '-[A-Za-z]{0,30}u(?:\\s+|(?=[^\\s:]{1,200}:))', '-[A-Za-z]{0,8}u(?:\\s+|(?=[^\\s:]{1,200}:))'),
    ('-E file:password not redacted', TARGET, '-[A-Za-z]{0,30}E(?:\\s+(?=\\S{0,200}:)|(?=\\S{0,200}:))|', ''),
    ('-E option cluster unbounded', TARGET, '-[A-Za-z]{0,30}E(?:', '-[A-Za-z]*E(?:'),
    ('-E option cluster of 9 letters or more not redacted', TARGET, '-[A-Za-z]{0,30}E(?:', '-[A-Za-z]{0,8}E(?:'),
    ('clustered -b cookie not redacted', TARGET, '(?:-[A-Za-z]{0,30}b(?:\\s+|=)', '(?:-b(?:\\s+|=)'),
    ('glued -b cookie not redacted', TARGET, '|-[A-Za-z]{0,30}b(?=[^\\s=]{0,200}=)', ''),
    ('-b cookie not redacted', TARGET, '(?:-[A-Za-z]{0,30}b(?:\\s+|=)|-[A-Za-z]{0,30}b(?=[^\\s=]{0,200}=)|--cookie(?:\\s+|=))', '(?:--cookie(?:\\s+|=))'),
    ('-b option cluster unbounded (the glued form, whose look-ahead is the costly one)', TARGET, '|-[A-Za-z]{0,30}b(?=[^\\s=]{0,200}=)', '|-[A-Za-z]*b(?=[^\\s=]*=)'),
    ('-b option cluster of 9 letters or more not redacted', TARGET, '|-[A-Za-z]{0,30}b(?=[^\\s=]{0,200}=)', '|-[A-Za-z]{0,8}b(?=[^\\s=]{0,200}=)'),
    ('the closed pipe is only caught in main(), not at the final flush', TARGET, '        rc = main()\n        sys.stdout.flush()  # inside the try', '        rc = main()\n        pass  # inside the try'),
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
