#!/usr/bin/env python3
"""Deterministic checks for the task-routing rule and playbooks — no Claude Code needed.

Run: python3 tests/test_playbooks.py   (or: python3 -m pytest tests -q)
Proves the artefacts and the install layout. It does NOT prove that Claude routes correctly —
that is model behaviour; see scripts/check_routing.py for the live scenario check.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTER = REPO_ROOT / "rules" / "task-routing.md"
CONTRACT = REPO_ROOT / "rules" / "output-contract.md"
MAX_CONTRACT_LINES = 58  # was 50 pre-2.0; the Groundwork 2.0 "Review result" section (D3) needed a few more, still well under MAX_ROUTER_LINES's precedent of 60 for an always-loaded rule file
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
    check("router points at the global output contract", "## 5. Universal output contract" in router and "`output-contract.md`" in router)
    check("router distinguishes Playbook/Routine/Role/Skill/Tool (2.1)", "**Routine**" in router and "**Role**" in router and "**Skill**" in router and "**Tool**" in router)
    for sym in "◆◐◇▲■↳⌁":  # → stays allowed as an ordinary arrow in prose ("command → result")
        check(f"no legacy symbol {sym} left in contract or playbooks", sym not in CONTRACT.read_text() and not any(sym in q.read_text() for q in PLAYBOOKS.glob("*.md")))
    contract = CONTRACT.read_text()
    check("output contract exists and stays small", CONTRACT.is_file() and len(contract.splitlines()) <= MAX_CONTRACT_LINES, f"{len(contract.splitlines())} lines")
    for needle in ("## Layer 1", "## Layer 2", "## Layer 3", "Technical details", "Evidence & references",
                   "Omit any section that has nothing useful", "Never imply verification that did not happen",
                   "Do not print routing or playbook debug lines", "Clean output never hides",
                   "written in user language", "no file names or paths", "it never removes it",
                   "## Harness metadata", "HARNESS METADATA", "never as bullets", "never invented", "This block is what the telemetry hook records",
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
        agents_dir = cfg.parent / "launch-agents"
        env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", CLAUDE_CONFIG_DIR=str(cfg), NODE_USE_SYSTEM_CA="0",
                   GROUNDWORK_LAUNCH_AGENTS_DIR=str(agents_dir), GROUNDWORK_NO_LAUNCHCTL="1",
                   # Forces the launchd scheduling path deterministically regardless of the CI
                   # host's real platform (production-code override in groundwork_report.py's
                   # is_macos(), mirroring setup.sh's own GROUNDWORK_OS pattern; unset for real users).
                   GROUNDWORK_OS="darwin")
        for i in (1, 2):
            r = subprocess.run(["bash", str(REPO_ROOT / "install.sh")], capture_output=True, text=True, env=env, timeout=120)
            check(f"install run {i} exits 0", r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])
        installed = sorted(p.name for p in (cfg / "groundwork" / "playbooks").glob("*.md"))
        check("all ten playbooks installed", installed == sorted(f"{c}.md" for c in CATEGORIES), str(installed))
        check("router installed under rules/groundwork", (cfg / "rules" / "groundwork" / "task-routing.md").is_file())
        check("output contract installed under rules/groundwork", (cfg / "rules" / "groundwork" / "output-contract.md").is_file())
        version_text = (cfg / "groundwork" / "VERSION").read_text().strip() if (cfg / "groundwork" / "VERSION").exists() else ""
        check("VERSION written from CHANGELOG", re.fullmatch(r"\d+\.\d+\.\d+", version_text) is not None, version_text or "missing")
        check("telemetry hook installed", (cfg / "hooks" / "groundwork_telemetry.py").is_file())
        check("report generator installed", (cfg / "groundwork" / "bin" / "groundwork_report.py").is_file())
        check("report schedule applied on install (default weekly, one plist)", len(list(agents_dir.glob("*.plist"))) == 1 and json.loads((cfg / "groundwork" / "report.json").read_text())["schedule"] == "weekly")
        (cfg / "groundwork" / "reports").mkdir(exist_ok=True)
        (cfg / "groundwork" / "reports" / "dashboard.html").write_text("<html></html>")
        (cfg / "groundwork" / "telemetry").mkdir(exist_ok=True)
        (cfg / "groundwork" / "telemetry" / "events.jsonl").write_text("{}\n")
        (cfg / "groundwork" / "investigations").mkdir(exist_ok=True)
        (cfg / "groundwork" / "investigations" / "some-repo-abc123.md").write_text("# Investigation\n")
        check("no playbook installed under rules/", not list((cfg / "rules").rglob("research.md")))
        for cat in CATEGORIES:
            check(f"installed {cat}.md identical to repo",
                  (cfg / "groundwork" / "playbooks" / f"{cat}.md").read_bytes() == (PLAYBOOKS / f"{cat}.md").read_bytes())
        r = subprocess.run(["bash", str(REPO_ROOT / "uninstall.sh")], capture_output=True, text=True, env=env, timeout=60)
        check("uninstall exits 0", r.returncode == 0, r.stderr[-300:])
        check("uninstall removes the playbooks and VERSION", not (cfg / "groundwork" / "playbooks").exists() and not (cfg / "groundwork" / "VERSION").exists())
        check("uninstall keeps telemetry records", (cfg / "groundwork" / "telemetry" / "events.jsonl").is_file())
        check("uninstall keeps investigation-continuity files (Decision D2, your data)", (cfg / "groundwork" / "investigations" / "some-repo-abc123.md").is_file())
        check("uninstall keeps historical reports, removes generator and launchd job", (cfg / "groundwork" / "reports" / "dashboard.html").is_file() and not (cfg / "groundwork" / "bin").exists() and not list(agents_dir.glob("*.plist")))
        check("uninstall removes the telemetry hook", not (cfg / "hooks" / "groundwork_telemetry.py").exists())
        check("uninstall removes rules/groundwork", not (cfg / "rules" / "groundwork").exists())
    finish()


def test_install_node_version_check() -> None:
    print("install.sh Node version check (Groundwork 2.0 Phase 1 — install.sh previously checked presence only)")
    if shutil.which("bash") is None:
        print("  skip: bash not available")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfg = tmp / "claude"
        cfg.mkdir()
        (cfg / "settings.json").write_text("{}")

        agents_dir = tmp / "launch-agents"

        def stubbed_env(node_version: str) -> tuple[dict, Path]:
            bin_dir = tmp / f"bin-{node_version.replace('.', '_')}"
            bin_dir.mkdir()
            major, minor = node_version.split(".")[:2]
            (bin_dir / "node").write_text(
                f'#!/usr/bin/env bash\ncase "$1" in --version) echo "v{node_version}";; '
                f'-p) case "$2" in *"[0]"*) echo {major};; *"[1]"*) echo {minor};; *) echo {major};; esac;; esac\n'
            )
            (bin_dir / "claude").write_text('#!/usr/bin/env bash\ncase "$1" in --version) echo "2.1.258 (Claude Code)";; plugin) echo "ecc@ecc";; *) exit 0;; esac\n')
            # openspec MUST be stubbed too — an unstubbed run would invoke a real `openspec`
            # binary's install/config commands if one happens to be on the real developer
            # machine's PATH (found by independent review, M3): real risk, not hypothetical.
            (bin_dir / "openspec").write_text('#!/usr/bin/env bash\ncase "$1" in --version) echo "1.13.2";; *) exit 0;; esac\n')
            (bin_dir / "npm").write_text("#!/usr/bin/env bash\nexit 0\n")
            (bin_dir / "python3").write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
            for f in ("node", "claude", "openspec", "npm", "python3"):
                os.chmod(bin_dir / f, 0o755)
            # bin_dir first so its node/claude/openspec/npm/python3 stubs shadow any real ones on
            # PATH; the rest of the real PATH stays available for coreutils install.sh needs.
            # GROUNDWORK_NO_LAUNCHCTL + a redirected GROUNDWORK_LAUNCH_AGENTS_DIR are mandatory —
            # without them, a "good version" run on a real macOS developer machine would register
            # a real com.groundwork.report launchd job under their real ~/Library/LaunchAgents
            # (found by independent review, M3 — confirmed by simulation, not hypothetical).
            env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", CLAUDE_CONFIG_DIR=str(cfg),
                       NODE_USE_SYSTEM_CA="0", GROUNDWORK_LAUNCH_AGENTS_DIR=str(agents_dir),
                       GROUNDWORK_NO_LAUNCHCTL="1", GROUNDWORK_OS="linux")
            return env, bin_dir

        # Below OpenSpec's real floor (20.19.0) — install.sh must refuse before any other step.
        for bad_version in ("18.19.1", "20.18.9", "19.9.9"):
            env, _ = stubbed_env(bad_version)
            r = subprocess.run(["bash", str(REPO_ROOT / "install.sh")], capture_output=True, text=True, env=env, timeout=30)
            check(f"install.sh refuses Node {bad_version} (below 20.19.0)",
                  r.returncode == 1 and "20.19.0" in r.stdout and not (cfg / "groundwork").exists(),
                  r.stdout[-300:] + r.stderr[-300:])

        # At or above the floor — install.sh's own version check must not block (may still fail
        # later for unrelated reasons in this minimal stub, e.g. no real claude/openspec install
        # path; we only assert the Node check itself did not reject it).
        for good_version in ("20.19.0", "20.19.5", "22.1.0"):
            env, _ = stubbed_env(good_version)
            r = subprocess.run(["bash", str(REPO_ROOT / "install.sh")], capture_output=True, text=True, env=env, timeout=30)
            check(f"install.sh accepts Node {good_version} (Node check does not reject it)",
                  "is older than" not in r.stdout and "Node.js not found" not in r.stdout,
                  r.stdout[-300:] + r.stderr[-300:])
    finish()


_SETUP_SYSBIN_EXCLUDED = {"node", "npm", "npx", "corepack", "nodejs", "apt-get", "apt", "dnf", "apk", "brew"}


def _setup_filtered_sysbin(dest: Path) -> Path:
    """A PATH dir mirroring the real one via symlinks, minus node/npm/apt-get/etc, so a stub
    node/apt-get actually gets used instead of silently falling through to the real host's
    binaries (the same PATH-leak class independent review found in test_setup.py's Box)."""
    dest.mkdir(exist_ok=True)
    for real_dir in ("/usr/bin", "/bin", "/usr/local/bin"):
        p = Path(real_dir)
        if not p.is_dir():
            continue
        for entry in p.iterdir():
            if entry.name in _SETUP_SYSBIN_EXCLUDED or (dest / entry.name).exists():
                continue
            try:
                (dest / entry.name).symlink_to(entry)
            except OSError:
                pass
    return dest


def test_setup_node_still_too_old_after_install() -> None:
    print("setup.sh post-install Node-still-too-old messaging (Groundwork 2.0 Phase 1, independent-review finding M2)")
    if shutil.which("bash") is None:
        print("  skip: bash not available")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfg = tmp / "claude"
        cfg.mkdir()
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        sysbin = _setup_filtered_sysbin(tmp / "sysbin")
        (bin_dir / "claude").write_text('#!/usr/bin/env bash\ncase "$1" in --version) echo "2.1.258 (Claude Code)";; plugin) echo "ecc@ecc";; *) exit 0;; esac\n')
        os.chmod(bin_dir / "claude", 0o755)
        env = dict(os.environ, PATH=f"{bin_dir}:{sysbin}", HOME=str(tmp), CLAUDE_CONFIG_DIR=str(cfg), GROUNDWORK_OS="linux")
        common_args = ["bash", str(REPO_ROOT / "setup.sh"), "--non-interactive", "--install-prereqs",
                       "--no-agent-teams", "--schedule", "disabled"]

        # Case 1: node starts entirely absent; the stub apt-get "installs" a still-too-old nodejs
        # package (as real distro apt packages routinely do — the real-world case M2 covers).
        (bin_dir / "apt-get").write_text(
            '#!/usr/bin/env bash\n'
            'case "$*" in *nodejs*)\n'
            '  d="$(dirname "$0")"\n'
            '  printf \'#!/usr/bin/env bash\\ncase "$1" in --version) echo "v18.19.1";; '
            '-p) case "$2" in *"[0]"*) echo 18;; *"[1]"*) echo 19;; *) echo 18;; esac;; esac\\n\' > "$d/node"\n'
            '  chmod +x "$d/node"\n'
            '  printf \'#!/usr/bin/env bash\\nexit 0\\n\' > "$d/npm"\n'
            '  chmod +x "$d/npm"\n'
            '  ;;\nesac\nexit 0\n'
        )
        os.chmod(bin_dir / "apt-get", 0o755)
        for stale in ("node", "npm"):
            (bin_dir / stale).unlink(missing_ok=True)
        r = subprocess.run(common_args, capture_output=True, text=True, env=env, timeout=30)
        out1 = r.stdout + r.stderr  # die() writes to stderr; setup.sh's own convention, unlike install.sh's stdout-only one
        check("still-too-old-after-install: does not use the generic 'open a new terminal' message",
              "open a new terminal" not in out1, out1[-500:])
        check("still-too-old-after-install: names a version manager / NodeSource instead",
              "nvm-sh/nvm" in out1 and "NodeSource" in out1 and "18.19.1" in out1, out1[-500:])

        # Case 2: node stays genuinely absent even after the "install" (apt-get does nothing) —
        # the original, still-correct "open a new terminal" message must be unchanged.
        (bin_dir / "apt-get").write_text('#!/usr/bin/env bash\nexit 0\n')
        os.chmod(bin_dir / "apt-get", 0o755)
        for stale in ("node", "npm"):
            (bin_dir / stale).unlink(missing_ok=True)
        r = subprocess.run(common_args, capture_output=True, text=True, env=env, timeout=30)
        out2 = r.stdout + r.stderr
        check("genuinely-still-missing-after-install: keeps the 'open a new terminal' message",
              "open a new terminal" in out2 and "NodeSource" not in out2, out2[-500:])
    finish()


if __name__ == "__main__":
    for t in (test_router_and_playbooks, test_install_copies_playbooks, test_install_node_version_check,
              test_setup_node_still_too_old_after_install):
        try:
            t()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
