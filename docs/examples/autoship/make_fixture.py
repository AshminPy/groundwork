#!/usr/bin/env python3
"""Write the disposable Autoship demo repository used by docs/AUTOSHIP.md.

    python3 docs/examples/autoship/make_fixture.py /tmp/autoship-demo [--wrong-test]

It creates a tiny git repository (no remote) holding a legacy duration parser, a test suite that fails against it,
an OpenSpec change with acceptance scenarios, and GOAL.txt (the /goal condition the page documents). With
--wrong-test one expectation contradicts the spec (2d -> 172801), to show the loop stopping as BLOCKED instead of
claiming success. Nothing here touches the Groundwork repository or any other directory.
"""
import os
import subprocess
import sys
from pathlib import Path

FILES = {
    "durations.py": '''"""Parse human duration strings such as '1h30m' into seconds."""
import re

_UNITS = {"s": 1, "m": 60, "h": 3600}


def parse_duration(text: str) -> int:
    total = 0
    for amount, unit in re.findall(r"(\\d+)([smh])", text):
        total += int(amount) * _UNITS[unit]
    return total
''',
    "README.md": '# durations\n\n`parse_duration("1h30m")` returns seconds.\n',
    "tests/test_durations.py": '''import subprocess
import sys

import pytest

from durations import parse_duration


@pytest.mark.parametrize("text,seconds", [
    ("45s", 45),
    ("1h30m", 5400),
    ("1h 30m", 5400),
    ("2d", 172800),
    ("1d2h3m4s", 93784),
    ("1H30M", 5400),
])
def test_valid(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["", "90", "1x", "1h1h", "1 h", "-5s", "h", "1h30"])
def test_invalid(text):
    with pytest.raises(ValueError):
        parse_duration(text)


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "durations_cli", *args], capture_output=True, text=True)


def test_cli_prints_seconds():
    r = run_cli("1h30m")
    assert r.returncode == 0 and r.stdout.strip() == "5400"


def test_cli_rejects_invalid():
    r = run_cli("90")
    assert r.returncode == 2 and r.stdout == "" and "90" in r.stderr
''',
    "openspec/changes/extend-durations/proposal.md": '''## Why
Operators write durations like `2d` and `1H30M`; the parser silently ignores what it does not understand and returns 0.

## What Changes
- `parse_duration` supports days, is case-insensitive, and raises ValueError on anything it does not fully understand.
- A command line `python -m durations_cli <text>` prints the seconds, or exits 2 with a message on stderr.
- README documents both.
''',
    "openspec/changes/extend-durations/tasks.md": '''## 1. Implementation
- [ ] 1.1 `parse_duration` supports s, m, h, d (case-insensitive), allows spaces between tokens only, and raises ValueError for empty, unit-less, unknown-unit, repeated-unit, negative and trailing-number input
- [ ] 1.2 `durations_cli.py`: `python -m durations_cli <text>` prints the seconds; invalid input prints a message naming the input to stderr, nothing to stdout, exit code 2
- [ ] 1.3 README documents the units, the strictness and the command line

## 2. Verification
- [ ] 2.1 `python3 -m pytest -q` passes
- [ ] 2.2 Independent fresh-context review reports Must-fix: 0
''',
    "openspec/changes/extend-durations/specs/durations/spec.md": '''# durations Specification

## Purpose
Turn a human duration string into seconds, strictly.

## ADDED Requirements

### Requirement: Strict parsing
`parse_duration` SHALL return the total seconds of one or more `<digits><unit>` tokens, where unit is one of s, m, h, d in either case, tokens may be separated by single spaces, a unit appears at most once, and anything else raises ValueError.

#### Scenario: Combined
- **WHEN** the input is `1d2h3m4s`
- **THEN** the result is 93784

#### Scenario: Not a duration
- **WHEN** the input is empty, `90`, `1x`, `1h1h`, `1 h`, `-5s`, `h` or `1h30`
- **THEN** ValueError is raised

### Requirement: Command line
`python -m durations_cli <text>` SHALL print the seconds and exit 0, or print a message that includes the input to stderr, print nothing to stdout, and exit 2.
''',
    "GOAL.txt": '''/goal Implement the OpenSpec change in openspec/changes/extend-durations in this repository (read its proposal.md, specs/durations/spec.md and tasks.md first). Start by running `python3 -m pytest -q` once, before changing anything, so the baseline failures are in the transcript. Either (A) all of these hold: every task in tasks.md is checked off; `python3 -m pytest -q` exits 0 and its passing summary line appears in the transcript; an independent fresh-context reviewer subagent started with the Agent tool (give it the file paths and the spec, not your conclusions) reviewed the change and the final REVIEW RESULT of the most recent review shows Must-fix: 0 (if a review reports Must-fix greater than 0: fix each finding, rerun the tests, and dispatch a fresh reviewer); nothing under tests/ is modified; nothing is committed, pushed or deployed; your final message states what was tested, the review outcome and what remains unverified, claiming nothing that was not observed. Or (B) the work is genuinely blocked: if a failing test contradicts the spec, or the same test still fails after 3 fix attempts, do NOT edit tests; write BLOCKED.md containing the exact failing test output, which requirement or test is at fault and the attempts made, then stop, and your final message must say BLOCKED and must not claim success. Bound: stop after 20 turns.
''',
}


def main(argv) -> int:
    flags = [a for a in argv[1:] if a.startswith("--")]
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 1 or any(f != "--wrong-test" for f in flags):
        print(__doc__)
        return 2
    target = Path(args[0])
    if target.exists() and any(target.iterdir()):
        print(f"refusing: {target} exists and is not empty")
        return 1
    files = dict(FILES)
    if "--wrong-test" in flags:
        files["tests/test_durations.py"] = files["tests/test_durations.py"].replace('("2d", 172800)', '("2d", 172801)')
    for rel, text in files.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    env = {"GIT_AUTHOR_NAME": "demo", "GIT_AUTHOR_EMAIL": "demo@example.invalid",
           "GIT_COMMITTER_NAME": "demo", "GIT_COMMITTER_EMAIL": "demo@example.invalid", "PATH": os.environ["PATH"]}
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "baseline"]):
        subprocess.run(cmd, cwd=target, check=True, env=env)
    print(f"fixture written to {target} (git repository, no remote). Run the loop from there; see docs/AUTOSHIP.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
