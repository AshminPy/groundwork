#!/usr/bin/env python3
"""Deterministic checks for the task-routing rule and playbooks — no Claude Code needed.

Run: python3 tests/test_playbooks.py   (or: python3 -m pytest tests -q)
Proves the artefacts and the install layout. It does NOT prove that Claude routes correctly —
that is model behaviour; see scripts/check_routing.py for the live scenario check.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTER = REPO_ROOT / "rules" / "task-routing.md"
CONTRACT = REPO_ROOT / "rules" / "output-contract.md"
MAX_CONTRACT_LINES = 50
PLAYBOOKS = REPO_ROOT / "playbooks"
CATEGORIES = ["research", "explain", "design", "plan", "implement",
              "troubleshoot", "validate", "audit", "deploy", "document"]
SECTIONS = ["## Goal", "## Workflow", "## Evidence", "## Ask Before Acting When",
            "## Completion Criteria", "## Output Format"]
MAX_PLAYBOOK_BYTES = 4000
MAX_ROUTER_LINES = 60

_FAILURES: list[str] = []
PASS = FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        _FAILURES.append(f"{name}  {detail}")
        print(f"  FAIL {name}  {detail}")


def finish() -> None:
    failures = list(_FAILURES)
    _FAILURES.clear()
    assert not failures, "\n".join(failures)


def test_router_and_playbooks() -> None:
    print("task-routing.md / playbooks")
    router = ROUTER.read_text()
    check("router exists and stays small", ROUTER.is_file() and len(router.splitlines()) <= MAX_ROUTER_LINES,
          f"{len(router.splitlines())} lines")
    check("router names the playbook path", "~/.claude/groundwork/playbooks/" in router)
    check("router says the existing rule wins on conflict", "existing rule wins" in router)
    check("router carries the material-ambiguity rule", "Ask before acting only when" in router)
    check("router points at the global output contract", "## 4. Universal output contract" in router and "`output-contract.md`" in router)
    for sym in "◆◐◇▲■↳⌁":  # → stays allowed as an ordinary arrow in prose ("command → result")
        check(f"no legacy symbol {sym} left in contract or playbooks", sym not in CONTRACT.read_text() and not any(sym in q.read_text() for q in PLAYBOOKS.glob("*.md")))
    contract = CONTRACT.read_text()
    check("output contract exists and stays small", CONTRACT.is_file() and len(contract.splitlines()) <= MAX_CONTRACT_LINES, f"{len(contract.splitlines())} lines")
    for needle in ("## Layer 1", "## Layer 2", "## Layer 3", "Technical details", "Evidence & references",
                   "Omit any section that has nothing useful", "Never imply verification that did not happen",
                   "Do not print routing or playbook debug lines", "Clean output never hides",
                   "written in user language", "no file names or paths", "it never removes it",
                   "## Checklist style", "`[x]` completed or verified", "`[ ]` pending", "`[!]` an important risk",
                   "`[-]` not applicable", "no emojis or decorative symbols", "never on every sentence",
                   "never to imply failure", "Heading `Technical details`", "Heading `Evidence & references`"):
        check(f"output contract contains: {needle[:40]}", needle in contract)
    for cat in CATEGORIES:
        check(f"router lists {cat.upper()}", f"| {cat.upper()} |" in router)
        pb = PLAYBOOKS / f"{cat}.md"
        check(f"playbook {cat}.md exists", pb.is_file())
        if not pb.is_file():
            continue
        text = pb.read_text()
        missing = [s for s in SECTIONS if s not in text]
        check(f"{cat}.md has the six sections", not missing, f"missing {missing}")
        check(f"{cat}.md within {MAX_PLAYBOOK_BYTES} bytes", len(text.encode()) <= MAX_PLAYBOOK_BYTES, str(len(text.encode())))
        check(f"{cat}.md does not restate the router's category table", "| RESEARCH |" not in text)
        check(f"{cat}.md inherits the global layers instead of restating them", "per `output-contract.md`" in text and "## Layer" not in text)
    extra = sorted(p.stem for p in PLAYBOOKS.glob("*.md") if p.stem not in CATEGORIES)
    check("no undeclared playbooks", not extra, str(extra))
    check("implement.md keeps the completion block (existing rule wins)",
          "Code / Tests / Reviewed / Merged / Deployed / Live validated" in (PLAYBOOKS / "implement.md").read_text())
    check("router installed rule list includes output-contract", (REPO_ROOT / "rules" / "output-contract.md").is_file())
    # a playbook's Output Format must still cover what its own Completion Criteria demand
    check("research.md output names Unknowns (its completion criteria require them)", "**Unknowns**" in (PLAYBOOKS / "research.md").read_text())
    check("design.md output keeps a visible risks heading", "risks**" in (PLAYBOOKS / "design.md").read_text())
    check("no playbook lives under rules/", not list((REPO_ROOT / "rules").rglob("research.md")))
    finish()


def test_install_copies_playbooks() -> None:
    print("install.sh / uninstall.sh (temp CLAUDE_CONFIG_DIR, stubbed claude/openspec)")
    if shutil.which("bash") is None:
        print("  skip: bash not available")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfg = tmp / "claude"
        cfg.mkdir()
        (cfg / "settings.json").write_text("{}")
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text('#!/usr/bin/env bash\ncase "$1" in --version) echo "2.1.258 (Claude Code)";; plugin) echo "ecc@ecc";; *) exit 0;; esac\n')
        (bin_dir / "openspec").write_text('#!/usr/bin/env bash\ncase "$1" in --version) echo "1.12.0";; *) exit 0;; esac\n')
        for f in ("claude", "openspec"):
            os.chmod(bin_dir / f, 0o755)
        env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", CLAUDE_CONFIG_DIR=str(cfg), NODE_USE_SYSTEM_CA="0")
        for i in (1, 2):
            r = subprocess.run(["bash", str(REPO_ROOT / "install.sh")], capture_output=True, text=True, env=env, timeout=120)
            check(f"install run {i} exits 0", r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])
        installed = sorted(p.name for p in (cfg / "groundwork" / "playbooks").glob("*.md"))
        check("all ten playbooks installed", installed == sorted(f"{c}.md" for c in CATEGORIES), str(installed))
        check("router installed under rules/groundwork", (cfg / "rules" / "groundwork" / "task-routing.md").is_file())
        check("output contract installed under rules/groundwork", (cfg / "rules" / "groundwork" / "output-contract.md").is_file())
        check("no playbook installed under rules/", not list((cfg / "rules").rglob("research.md")))
        for cat in CATEGORIES:
            check(f"installed {cat}.md identical to repo",
                  (cfg / "groundwork" / "playbooks" / f"{cat}.md").read_bytes() == (PLAYBOOKS / f"{cat}.md").read_bytes())
        r = subprocess.run(["bash", str(REPO_ROOT / "uninstall.sh")], capture_output=True, text=True, env=env, timeout=60)
        check("uninstall exits 0", r.returncode == 0, r.stderr[-300:])
        check("uninstall removes the playbooks directory", not (cfg / "groundwork").exists())
        check("uninstall removes rules/groundwork", not (cfg / "rules" / "groundwork").exists())
    finish()


if __name__ == "__main__":
    for t in (test_router_and_playbooks, test_install_copies_playbooks):
        try:
            t()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
