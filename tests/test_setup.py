#!/usr/bin/env python3
"""Deterministic checks for setup.sh — the onboarding wrapper. No Claude services, no launchd.

Run: python3 tests/test_setup.py   (or: python3 -m pytest tests -q)
Every run uses a temporary CLAUDE_CONFIG_DIR, a temporary backup root, stubbed claude/openspec/npm
binaries on PATH, launchctl stubbed out, and the wrapper's own test run skipped.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SETUP = REPO_ROOT / "setup.sh"

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


class Box:
    """One isolated environment: config dir, backup root, stub binaries."""

    def __init__(self, root: Path, name="claude"):
        self.root = root
        self.cfg = root / name
        self.backups = root / "backups"
        self.agents = root / "launch-agents"
        bin_dir = root / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        (bin_dir / "claude").write_text('#!/usr/bin/env bash\ncase "$1" in --version) echo "2.1.258 (Claude Code)";; plugin) echo "ecc@ecc";; *) exit 0;; esac\n')
        (bin_dir / "openspec").write_text('#!/usr/bin/env bash\ncase "$1" in --version) echo "1.12.0";; *) exit 0;; esac\n')
        (bin_dir / "npm").write_text('#!/usr/bin/env bash\nexit 0\n')
        for f in ("claude", "openspec", "npm"):
            os.chmod(bin_dir / f, 0o755)
        self.env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", CLAUDE_CONFIG_DIR=str(self.cfg),
                        GROUNDWORK_BACKUP_DIR=str(self.backups), GROUNDWORK_LAUNCH_AGENTS_DIR=str(self.agents),
                        GROUNDWORK_NO_LAUNCHCTL="1", NODE_USE_SYSTEM_CA="0", GROUNDWORK_SETUP_SKIP_TESTS="1")
        self.env.pop("GROUNDWORK_INSTALLER", None)

    def run(self, *args, stdin: str = "", extra=None) -> subprocess.CompletedProcess:
        env = dict(self.env)
        env.update(extra or {})
        return subprocess.run(["bash", str(SETUP), *args], input=stdin, capture_output=True, text=True, env=env, timeout=300)

    def settings(self) -> dict:
        return json.loads((self.cfg / "settings.json").read_text())

    def backup_dirs(self) -> list:
        return sorted(p for p in self.backups.glob("groundwork-*") if p.is_dir()) if self.backups.exists() else []


def seed_existing(cfg: Path) -> None:
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "settings.json").write_text(json.dumps({"env": {"KEEP": "1"}, "custom": True}, indent=2) + "\n")
    (cfg / "my-notes.md").write_text("mine\n")
    (cfg / "groundwork" / "telemetry").mkdir(parents=True, exist_ok=True)
    (cfg / "groundwork" / "telemetry" / "events.jsonl").write_text('{"schema": 2, "ts": "2026-09-20T10:00:00Z"}\n')


def test_setup() -> None:
    print("setup.sh")
    if shutil.which("bash") is None:
        print("  skip: bash not available")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # ---- no existing config dir, non-interactive, work profile, weekly (defaults)
        a = Box(tmp / "a")
        r = a.run("--non-interactive", "--profile", "work")
        check("fresh machine: setup exits 0", r.returncode == 0, r.stdout[-800:] + r.stderr[-800:])
        check("fresh machine: backup created with existed=no and no claude copy", len(a.backup_dirs()) == 1 and "existed=no" in (a.backup_dirs()[0] / "BACKUP-INFO.txt").read_text() and not (a.backup_dirs()[0] / "claude").exists())
        check("fresh machine: installed (VERSION, rules, playbooks, hooks, generator)", (a.cfg / "groundwork" / "VERSION").is_file() and len(list((a.cfg / "rules" / "groundwork").glob("*.md"))) == 5 and len(list((a.cfg / "groundwork" / "playbooks").glob("*.md"))) == 10 and (a.cfg / "hooks" / "groundwork_telemetry.py").is_file() and (a.cfg / "groundwork" / "bin" / "groundwork_report.py").is_file())
        check("work profile set through settings env", a.settings()["env"].get("GROUNDWORK_PROFILE") == "work", json.dumps(a.settings().get("env")))
        check("agent teams disabled by default", "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" not in a.settings().get("env", {}))
        check("weekly schedule by default (config + one plist)", json.loads((a.cfg / "groundwork" / "report.json").read_text())["schedule"] == "weekly" and len(list(a.agents.glob("*.plist"))) == 1)
        check("first dashboard generated", (a.cfg / "groundwork" / "reports" / "dashboard.html").is_file())
        check("summary printed", all(x in r.stdout for x in ("installed successfully.", "Profile:       work", "Agent Teams:   disabled", "Reports:       weekly", "Validation:    skipped", "./setup.sh --verify", "./setup.sh --rollback")), r.stdout[-900:])
        check("backup owner-only", (a.backup_dirs()[0].stat().st_mode & 0o777) == 0o700)

        # ---- verify success, then failure
        r = a.run("--verify")
        check("verify: PASS overall, exit 0, all rows present", r.returncode == 0 and "Overall             PASS" in r.stdout and all(x in r.stdout for x in ("Groundwork version", "Rules", "Playbooks", "Hooks", "ECC", "OpenSpec", "Telemetry", "Dashboard", "Reporting schedule")), r.stdout)
        check("verify changes nothing", len(a.backup_dirs()) == 1)
        (a.cfg / "groundwork" / "VERSION").unlink()
        shutil.rmtree(a.cfg / "groundwork" / "playbooks")
        r = a.run("--verify")
        check("verify after damage: NOT CONFIGURED / FAIL rows, exit 1", r.returncode == 1 and "NOT CONFIGURED" in r.stdout and "Playbooks           FAIL" in r.stdout and "Overall             FAIL" in r.stdout, r.stdout)

        # ---- existing config, interactive answers: personal, no teams, daily; repeated run; backups not overwritten
        b = Box(tmp / "b")
        seed_existing(b.cfg)
        r = b.run(stdin="2\n1\n2\n")
        check("existing config: interactive setup exits 0", r.returncode == 0, r.stdout[-800:] + r.stderr[-800:])
        bk = b.backup_dirs()
        check("existing config: full copy in the backup incl. user files and telemetry", len(bk) == 1 and (bk[0] / "claude" / "my-notes.md").read_text() == "mine\n" and (bk[0] / "claude" / "groundwork" / "telemetry" / "events.jsonl").is_file() and "existed=yes" in (bk[0] / "BACKUP-INFO.txt").read_text())
        check("existing config: user settings preserved and merged", b.settings()["env"]["KEEP"] == "1" and b.settings()["custom"] is True)
        check("personal profile, daily schedule from the prompts", b.settings()["env"]["GROUNDWORK_PROFILE"] == "personal" and json.loads((b.cfg / "groundwork" / "report.json").read_text())["schedule"] == "daily", r.stdout[-600:])
        check("telemetry file untouched by setup", (b.cfg / "groundwork" / "telemetry" / "events.jsonl").read_text().startswith('{"schema": 2'))
        r2 = b.run("--non-interactive", "--profile", "personal", "--schedule", "monthly")
        bk2 = b.backup_dirs()
        check("repeated setup: exits 0, second backup added, first backup intact", r2.returncode == 0 and len(bk2) == 2 and (bk2[0] / "claude" / "my-notes.md").read_text() == "mine\n", r2.stdout[-400:])
        hooks = [h["command"] for ev in b.settings()["hooks"].values() for g in ev for h in g["hooks"]]
        check("repeated setup: idempotent settings (4 hook entries once, profile kept)", len(hooks) == 4 and b.settings()["env"]["GROUNDWORK_PROFILE"] == "personal" and json.loads((b.cfg / "groundwork" / "report.json").read_text())["schedule"] == "monthly")

        # ---- agent teams enabled; yearly + disabled schedules; other profile via prompt
        c = Box(tmp / "c")
        r = c.run("--non-interactive", "--profile", "Ops-Team_1", "--agent-teams", "--schedule", "yearly")
        check("agent teams enabled -> env flag set, yearly schedule, profile lower-cased", r.returncode == 0 and c.settings()["env"].get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1" and json.loads((c.cfg / "groundwork" / "report.json").read_text())["schedule"] == "yearly" and c.settings()["env"]["GROUNDWORK_PROFILE"] == "ops-team_1", r.stdout[-500:] + r.stderr[-300:])
        r = c.run("--non-interactive", "--no-agent-teams", "--schedule", "disabled")
        check("disabled schedule -> no plist, config disabled", r.returncode == 0 and not list(c.agents.glob("*.plist")) and json.loads((c.cfg / "groundwork" / "report.json").read_text())["schedule"] == "disabled")
        d = Box(tmp / "d")
        r = d.run(stdin="3\nlab-box\n2\n3\n")
        check("'Other' profile prompt, teams yes, monthly", r.returncode == 0 and d.settings()["env"]["GROUNDWORK_PROFILE"] == "lab-box" and d.settings()["env"].get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1" and json.loads((d.cfg / "groundwork" / "report.json").read_text())["schedule"] == "monthly", r.stdout[-500:] + r.stderr[-300:])
        r = d.run("--non-interactive", "--profile", "bad profile!")
        check("invalid profile rejected", r.returncode != 0 and "profile must be" in r.stderr)
        r = d.run("--non-interactive", "--schedule", "hourly")
        check("invalid schedule rejected", r.returncode != 0 and "schedule must be" in r.stderr)

        # ---- installer failure: backup exists, original config untouched, rollback hint printed
        e = Box(tmp / "e")
        seed_existing(e.cfg)
        bad = tmp / "bad-install.sh"
        bad.write_text("#!/usr/bin/env bash\necho 'simulated installer failure' >&2\nexit 7\n")
        r = e.run("--non-interactive", "--profile", "work", extra={"GROUNDWORK_INSTALLER": str(bad)})
        check("installer failure: non-zero exit, clear message, backup path and rollback command shown", r.returncode == 7 and "Setup FAILED" in r.stdout and "Backup:" in r.stdout and "./setup.sh --rollback" in r.stdout, r.stdout[-600:] + r.stderr[-300:])
        check("installer failure: original config untouched", e.settings() == {"env": {"KEEP": "1"}, "custom": True} and (e.cfg / "my-notes.md").is_file())

        # ---- missing prerequisite: stop before backing up
        f = Box(tmp / "f")
        seed_existing(f.cfg)
        clean = tmp / "f" / "cleanbin"   # node, git, python3 real; npm/openspec stubs; no claude anywhere on this PATH
        clean.mkdir()
        for tool in ("node", "git"):
            os.symlink(shutil.which(tool), clean / tool)
        (clean / "python3").write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')  # a symlinked framework python can hang; exec via a wrapper
        os.chmod(clean / "python3", 0o755)
        for stub in ("npm", "openspec"):
            shutil.copy(tmp / "f" / "bin" / stub, clean / stub)
        no_claude = dict(f.env, PATH=f"{clean}:/usr/bin:/bin", HOME=str(tmp / "f" / "home"))
        (tmp / "f" / "home").mkdir()
        r = subprocess.run(["bash", str(SETUP), "--non-interactive"], capture_output=True, text=True, env=no_claude, timeout=60)
        check("missing prerequisite: fails clearly, nothing changed, no backup made", r.returncode == 1 and "Missing prerequisites" in r.stdout and not f.backups.exists() and not (f.cfg / "groundwork" / "VERSION").exists(), r.stdout + r.stderr)

        # ---- rollback: latest backup restored, current setup moved aside (telemetry kept there), schedule removed
        g = Box(tmp / "g")
        seed_existing(g.cfg)
        r = g.run("--non-interactive", "--profile", "work")
        (g.cfg / "groundwork" / "telemetry" / "events.jsonl").write_text('{"schema": 2, "ts": "2026-09-21T10:00:00Z"}\n{"schema": 2, "ts": "2026-09-21T11:00:00Z"}\n')
        r = g.run("--rollback")
        disabled = sorted(p for p in g.root.glob("claude-groundwork-disabled-*") if p.is_dir())
        check("rollback: exit 0, messages", r.returncode == 0 and "Current setup saved to:" in r.stdout and "Restored:" in r.stdout and "Rollback complete." in r.stdout and "Restart Claude Code." in r.stdout, r.stdout + r.stderr)
        check("rollback: pre-Groundwork config restored exactly", g.settings() == {"env": {"KEEP": "1"}, "custom": True} and (g.cfg / "my-notes.md").read_text() == "mine\n" and not (g.cfg / "groundwork" / "VERSION").exists())
        check("rollback: current setup kept in a disabled copy with its telemetry and reports", len(disabled) == 1 and (disabled[0] / "groundwork" / "reports" / "dashboard.html").is_file() and len((disabled[0] / "groundwork" / "telemetry" / "events.jsonl").read_text().splitlines()) == 2)
        check("rollback: backup itself untouched, launchd job removed", (g.backup_dirs()[0] / "claude" / "my-notes.md").is_file() and not list(g.agents.glob("*.plist")))
        r = g.run("--verify")
        check("verify after rollback: NOT CONFIGURED, exit 1", r.returncode == 1 and "NOT CONFIGURED" in r.stdout)

        # ---- rollback with no prior config: current moved aside, config dir left absent
        h = Box(tmp / "h")
        r = h.run("--non-interactive")
        r = h.run("--rollback")
        check("rollback of a fresh-machine install: config dir absent afterwards, setup moved aside", r.returncode == 0 and not h.cfg.exists() and len(list(h.root.glob("claude-groundwork-disabled-*"))) == 1 and "left absent" in r.stdout, r.stdout + r.stderr)

        # ---- multiple backups: newest wins; ambiguous timestamps refused; explicit dir accepted; no backups refused
        i = Box(tmp / "i")
        seed_existing(i.cfg)
        i.run("--non-interactive", "--profile", "work")
        (i.cfg / "marker-after-first.txt").write_text("1")
        i.run("--non-interactive", "--profile", "work")
        bk = i.backup_dirs()
        check("multiple backups: two distinct dirs", len(bk) == 2 and bk[0] != bk[1])
        r = i.run("--rollback")
        check("multiple backups: newest restored (contains marker-after-first)", r.returncode == 0 and (i.cfg / "marker-after-first.txt").is_file() and str(bk[1]) in r.stdout, r.stdout + r.stderr)
        amb = i.backups / (bk[1].name + "-1")
        shutil.copytree(bk[1], amb)
        r = i.run("--rollback")
        check("ambiguous backups (same timestamp): refused, no change", r.returncode == 1 and "ambiguous" in r.stderr and (i.cfg / "marker-after-first.txt").is_file(), r.stderr)
        r = i.run("--rollback", str(bk[0]))
        check("explicit backup dir accepted (oldest: no marker file)", r.returncode == 0 and not (i.cfg / "marker-after-first.txt").exists() and (i.cfg / "my-notes.md").is_file(), r.stdout + r.stderr)
        j = Box(tmp / "j")
        seed_existing(j.cfg)
        r = j.run("--rollback")
        check("no backups: refused with a clear message, config untouched", r.returncode == 1 and "nothing to roll back to" in r.stderr and (j.cfg / "my-notes.md").is_file())
        (j.backups).mkdir()
        (j.backups / "groundwork-20260101-000000").mkdir()
        r = j.run("--rollback")
        check("backup without BACKUP-INFO.txt: refused", r.returncode == 1 and "BACKUP-INFO" in r.stderr)
        foreign = j.backups / "groundwork-20260102-000000"
        foreign.mkdir()
        (foreign / "BACKUP-INFO.txt").write_text("source=/somewhere/else\nexisted=no\n")
        r = j.run("--rollback")
        check("backup from another config dir: refused", r.returncode == 1 and "refusing to guess" in r.stderr)

        # ---- review findings: flags without values, combined modes, backup without a claude/ copy
        r = d.run("--non-interactive", "--profile")
        check("--profile without a value: clear error, exit 1", r.returncode == 1 and "requires a value" in r.stderr, r.stdout + r.stderr)
        r = d.run("--schedule")
        check("--schedule without a value: clear error", r.returncode == 1 and "requires a value" in r.stderr)
        r = d.run("--verify", "--rollback")
        check("two mode flags refused", r.returncode == 1 and "cannot combine" in r.stderr)
        m = Box(tmp / "m")
        seed_existing(m.cfg)
        m.backups.mkdir()
        broken = m.backups / "groundwork-20260301-000000"
        broken.mkdir()
        (broken / "BACKUP-INFO.txt").write_text(f"source={m.cfg}\nexisted=yes\n")
        r = m.run("--rollback")
        moved = list(m.root.glob("claude-groundwork-disabled-*"))
        check("backup without claude/ copy: reassuring message names the moved-aside dir, nothing lost", r.returncode == 1 and "your current setup is intact at" in r.stderr and len(moved) == 1 and (moved[0] / "my-notes.md").is_file(), r.stderr)

        # ---- prerequisites: OS-aware, opt-in installation with stub package managers
        def prereq_box(name, os_kind, stubs):
            """A box whose PATH holds only: python3 wrapper, real git (via /usr/bin), coreutils, and the given stubs."""
            root = tmp / name
            b = Box(root)
            clean = root / "cleanbin"; clean.mkdir(); tools = root / "installed"; tools.mkdir()
            (clean / "python3").write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n'); os.chmod(clean / "python3", 0o755)
            (clean / "openspec").write_text('#!/usr/bin/env bash\ncase "$1" in --version) echo "1.12.0";; *) exit 0;; esac\n'); os.chmod(clean / "openspec", 0o755)
            (clean / "npm").write_text('#!/usr/bin/env bash\nexit 0\n'); os.chmod(clean / "npm", 0o755)
            mk = lambda n, body: ((clean / n).write_text(body), os.chmod(clean / n, 0o755))
            node_stub = 'case "$1" in --version) echo v22.1.0;; -p) echo 22;; esac\n'
            claude_stub = 'case "$1" in --version) echo "2.1.258 (Claude Code)";; plugin) echo "ecc@ecc";; *) exit 0;; esac\n'
            # package-manager stubs "install" by dropping tool stubs into the installed/ dir (on PATH) and logging the call
            installer = (f'#!/usr/bin/env bash\necho "$0 $*" >> "{root}/pm.log"\n'
                         f'case "$*" in *node*|*nodejs*) printf \'#!/usr/bin/env bash\\n{node_stub}\' > "{tools}/node"; chmod +x "{tools}/node";; esac\n'
                         f'case "$*" in *claude*) printf \'#!/usr/bin/env bash\\n{claude_stub}\' > "{tools}/claude"; chmod +x "{tools}/claude";; esac\nexit 0\n')
            for st in stubs:
                if st in ("brew", "apt-get", "dnf", "apk"):
                    mk(st, installer)
                elif st == "sudo":
                    mk("sudo", '#!/usr/bin/env bash\n[ "$1" = -n ] && exit 0\nexec "$@"\n')
                elif st == "curl":   # the official native installer is `curl … | bash`; the stub prints a script that installs the claude stub
                    mk("curl", f'#!/usr/bin/env bash\nprintf \'printf "#!/usr/bin/env bash\\\\n{claude_stub}" > "{tools}/claude"; chmod +x "{tools}/claude"\\n\'\n')
                elif st == "node":
                    mk("node", "#!/usr/bin/env bash\n" + node_stub)
                elif st == "oldnode":
                    mk("node", '#!/usr/bin/env bash\ncase "$1" in --version) echo v16.20.0;; -p) echo 16;; esac\n')
                elif st == "claude":
                    mk("claude", "#!/usr/bin/env bash\n" + claude_stub)
            b.env["PATH"] = f"{clean}:{tools}:/usr/bin:/bin"
            b.env["HOME"] = str(root / "home"); (root / "home").mkdir()
            b.env["GROUNDWORK_OS"] = os_kind
            return b, root

        pb, root = prereq_box("p1", "darwin", ["brew", "claude"])
        r = pb.run("--non-interactive", "--install-prereqs", "--profile", "work")
        log = (root / "pm.log").read_text() if (root / "pm.log").exists() else ""
        check("macOS: missing node installed via Homebrew, setup completes", r.returncode == 0 and "install node" in log and "claude" not in log and "Prereqs added: yes (brew)" in r.stdout and (pb.cfg / "groundwork" / "VERSION").is_file(), r.stdout[-700:] + r.stderr[-400:] + log)
        pb, root = prereq_box("p0", "darwin", ["brew", "node"])
        r = pb.run("--non-interactive", "--install-prereqs")
        check("Claude Code missing: never installed by the script — stops with the official link, nothing changed", r.returncode == 1 and "code.claude.com/docs/en/setup" in r.stderr and not (root / "pm.log").exists() and not pb.backups.exists(), r.stdout + r.stderr)
        pb, root = prereq_box("p2", "darwin", ["claude"])
        r = pb.run("--non-interactive", "--install-prereqs")
        check("macOS without Homebrew: stops, prints the official Homebrew command, nothing changed", r.returncode == 1 and "raw.githubusercontent.com/Homebrew/install/HEAD/install.sh" in r.stdout and "Homebrew not found" in r.stderr and not pb.backups.exists(), r.stdout + r.stderr)
        pb, root = prereq_box("p3", "linux", ["apt-get", "sudo", "claude"])
        r = pb.run("--non-interactive", "--install-prereqs", "--profile", "work")
        log = (root / "pm.log").read_text() if (root / "pm.log").exists() else ""
        check("Linux (apt): node + npm via apt with sudo, setup completes", r.returncode == 0 and "install -y nodejs npm" in log and "Prereqs added: yes (apt)" in r.stdout, r.stdout[-700:] + r.stderr[-400:] + log)
        pb, root = prereq_box("p4", "linux", ["dnf", "sudo", "claude"])
        r = pb.run("--non-interactive", "--install-prereqs")
        check("Linux (dnf) path", r.returncode == 0 and "dnf install -y nodejs npm" in (root / "pm.log").read_text(), r.stdout[-400:] + r.stderr[-300:])
        pb, root = prereq_box("p5", "linux", ["sudo", "claude"])
        r = pb.run("--non-interactive", "--install-prereqs")
        check("Linux without apt/dnf/apk: stops with instructions, nothing changed", r.returncode == 1 and "no supported package manager" in r.stderr and not pb.backups.exists(), r.stderr)
        pb, root = prereq_box("p6", "darwin", ["brew", "claude"])
        r = pb.run("--non-interactive")
        check("non-interactive without --install-prereqs: lists the exact commands and stops before any backup", r.returncode == 1 and "brew install node" in r.stdout and "--install-prereqs" in r.stderr and not pb.backups.exists(), r.stdout + r.stderr)
        r = pb.run("--non-interactive", "--no-install-prereqs")
        check("--no-install-prereqs: never installs", r.returncode == 1 and "--no-install-prereqs given" in r.stderr and not (root / "pm.log").exists())
        r = pb.run(stdin="n\n")
        check("interactive 'n' to the install question: stops, nothing installed", r.returncode == 1 and "not installing" in r.stderr and not (root / "pm.log").exists(), r.stdout + r.stderr)
        r = pb.run(stdin="y\n1\n1\n1\n")
        check("interactive 'y': installs, then continues with the three questions", r.returncode == 0 and (root / "pm.log").is_file() and "installed successfully" in r.stdout, r.stdout[-600:] + r.stderr[-300:])
        pb, root = prereq_box("p7", "darwin", ["brew", "oldnode", "claude"])
        r = pb.run("--non-interactive", "--install-prereqs")
        check("Node too old: left to the user's version manager, clear message, nothing installed", r.returncode == 1 and "older than 18" in r.stderr and not (root / "pm.log").exists(), r.stderr)

        # ---- uninstall delegation: playbooks/rules/hooks/bin gone, telemetry and reports kept, profile env removed
        k = Box(tmp / "k")
        seed_existing(k.cfg)
        k.run("--non-interactive", "--profile", "work")
        r = k.run("--uninstall")
        check("uninstall: delegates to uninstall.sh (exit 0)", r.returncode == 0, r.stdout[-400:] + r.stderr[-300:])
        check("uninstall: Groundwork removed, telemetry and reports kept, user files kept", not (k.cfg / "groundwork" / "playbooks").exists() and not (k.cfg / "groundwork" / "bin").exists() and not (k.cfg / "rules" / "groundwork").exists() and (k.cfg / "groundwork" / "telemetry" / "events.jsonl").is_file() and (k.cfg / "groundwork" / "reports" / "dashboard.html").is_file() and (k.cfg / "my-notes.md").is_file())
        check("uninstall: profile env and hooks unmerged, user env kept", "GROUNDWORK_PROFILE" not in k.settings().get("env", {}) and k.settings()["env"]["KEEP"] == "1" and not any("groundwork" in h["command"] for ev in k.settings().get("hooks", {}).values() for g in ev for h in g["hooks"]))

        # ---- paths with spaces
        sp = tmp / "gw space dir"
        l = Box(sp, name="claude cfg")
        seed_existing(l.cfg)
        r = l.run("--non-interactive", "--profile", "work")
        check("paths with spaces: setup ok, backup and dashboard written", r.returncode == 0 and (l.cfg / "groundwork" / "reports" / "dashboard.html").is_file() and (l.backup_dirs()[0] / "claude" / "my-notes.md").is_file(), r.stdout[-500:] + r.stderr[-300:])
        r = l.run("--rollback")
        check("paths with spaces: rollback ok", r.returncode == 0 and (l.cfg / "my-notes.md").is_file() and not (l.cfg / "groundwork" / "VERSION").exists(), r.stdout + r.stderr)
    finish()


if __name__ == "__main__":
    try:
        test_setup()
    except AssertionError:
        pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
