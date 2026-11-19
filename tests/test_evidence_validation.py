#!/usr/bin/env python3
"""Regression cases for evidence validation (openspec/changes/harden-autonomy-evidence-review).

The reply check resolves repository citations in the final reply and asks once when one does not resolve.
Run directly: python3 tests/test_evidence_validation.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_reply_check import FULL, check, finish, load_module, run, transcript  # noqa: E402
import test_reply_check  # noqa: E402


def make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    (repo / "hooks").mkdir(parents=True)
    (repo / "hooks" / "app.py").write_text("".join(f"line {i}\n" for i in range(1, 41)))  # 40 lines
    (repo / "hooks" / "parser.py").write_text("x = 1\n" * 50)  # cited by test_reply_check.FULL
    (repo / "docs").mkdir()
    (repo / "docs" / "gone.md").write_text("old\n")
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    (repo / "docs" / "gone.md").unlink()  # deleted in the working tree, still in HEAD
    return repo


def test_citation_problems() -> None:
    print("evidence validation — repository citations resolve")
    mod = load_module()
    with tempfile.TemporaryDirectory() as d:
        repo = make_repo(Path(d))
        cp = lambda text: mod.citation_problems(text, str(repo))  # noqa: E731
        check("valid file:line -> nothing", cp("See `hooks/app.py:12`.") == [], cp("See `hooks/app.py:12`."))
        check("valid range -> nothing", cp("hooks/app.py:10-40") == [])
        check("valid bare name with line -> nothing", cp("app.py:40") == [])
        out = cp("See `hooks/missing.py:10`.")
        check("missing file -> named", len(out) == 1 and "hooks/missing.py:10" in out[0] and "no such file" in out[0], out)
        out = cp("hooks/app.py:41")
        check("line past the end -> named with the line count", len(out) == 1 and "40 lines" in out[0], out)
        out = cp("hooks/app.py:30-90")
        check("stale range -> named", len(out) == 1 and "30-90" in out[0], out)
        out = cp("hooks/app.py:9-3")
        check("reversed range -> invalid", len(out) == 1 and "not a valid line range" in out[0], out)
        out = cp("app.py:500")
        check("bare name past the end -> named", len(out) == 1 and "40 lines" in out[0], out)
        check("file deleted in the working tree but in HEAD -> nothing", cp("`docs/gone.md`") == [])
        check("URL path -> not checked", cp("https://example.com/hooks/missing.py:3") == [])
        check("absolute and home paths -> not checked", cp("/srv/hooks/missing.py:3 and ~/hooks/missing.py:3") == [])
        check("top directory not in the repo -> not checked", cp("other/missing.py:3 and src/x.py") == [])
        check("bare name not in the repo -> not checked", cp("nowhere.py:12") == [])
        check("version strings and dotted names -> not checked", cp("v2.1.316 and os.path and e.g.") == [])
        check("fenced code -> not checked", cp("```\nhooks/missing.py:1\n```") == [])
        check("not a repository -> nothing", mod.citation_problems("hooks/missing.py:1", d) == [])
    finish()


def test_stop_hook_citations() -> None:
    print("evidence validation — Stop hook")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        repo = make_repo(tmp)
        base = {"hook_event_name": "Stop", "transcript_path": str(transcript(tmp, ["Bash", "Edit"])),
                "stop_hook_active": False, "cwd": str(repo)}
        r = run({**base, "last_assistant_message": FULL})
        check("complete reply with resolvable references -> no output", r.stdout.strip() == "", r.stdout)
        bad = FULL + "\nAlso see `hooks/missing.py:3`.\n"
        r = run({**base, "last_assistant_message": bad})
        out = json.loads(r.stdout) if r.stdout.strip() else {}
        check("unresolved citation -> asked once", out.get("decision") == "block"
              and "hooks/missing.py:3" in out.get("reason", "") and "absolute path" in out.get("reason", ""), r.stdout)
        check("format parts already present are not requested", "is missing" not in out.get("reason", ""), out)
        r = run({**base, "stop_hook_active": True, "last_assistant_message": bad})
        check("never asks twice", r.stdout.strip() == "", r.stdout)
        chat = transcript(tmp, [], name="chat.jsonl")
        r = run({**base, "transcript_path": str(chat), "last_assistant_message": bad})
        check("chat turn with a bad citation -> untouched", r.stdout.strip() == "", r.stdout)
        r = run({**base, "last_assistant_message": "Done. See hooks/missing.py:3"})
        out = json.loads(r.stdout) if r.stdout.strip() else {}
        check("missing parts and a bad citation -> one combined request",
              out.get("decision") == "block" and "is missing" in out.get("reason", "")
              and "hooks/missing.py:3" in out.get("reason", ""), r.stdout)
    finish()


if __name__ == "__main__":
    for fn in (test_citation_problems, test_stop_hook_citations):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{test_reply_check.PASS} passed, {test_reply_check.FAIL} failed")
    sys.exit(1 if test_reply_check.FAIL else 0)
