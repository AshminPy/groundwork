#!/usr/bin/env python3
"""Deterministic checks for setup.sh — the onboarding wrapper. No Claude services, no launchd.

Run: python3 tests/test_setup.py   (or: python3 -m pytest tests -q)
Every run uses a temporary CLAUDE_CONFIG_DIR, a temporary backup root, stubbed claude/openspec/npm
binaries on PATH, launchctl stubbed out, and the wrapper's own test run skipped.
"""
import atexit
import json
import os
import shutil
import subprocess
import sys
import time
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SETUP = REPO_ROOT / "setup.sh"

_FAILURES: list[str] = []
PASS = FAIL = 0

# Some CI/sandbox base images ship a real, older Node at /usr/bin or /bin (unrelated to any
# version manager). A prereq_box() PATH that included those directories wholesale let that
# real Node leak into "should be absent" test boxes, making setup.sh correctly (per its own
# documented behavior: an existing-but-old Node is never auto-upgraded, only a genuinely
# absent one is auto-installed) treat "absent" boxes as "present but too old" instead —
# masked before Groundwork 2.0's Node-floor fix because 18.x used to satisfy the old,
# incorrect NODE_MIN=18 check by coincidence. Fix: a filtered coreutils dir, built once,
# that symlinks every real /usr/bin and /bin executable except node/npm/npx/corepack/nodejs,
# so genuinely-absent-Node boxes stay genuinely absent while every other real system tool
# (git, sed, mkdir, chmod, ...) remains available. Test-only; no production code involved.
_FILTERED_SYSBIN: Path | None = None
# Node/npm (see above) plus every package manager setup.sh detects — this sandbox's own base
# image is Debian-based and ships a real apt-get, which the same leak class made detect_pm()
# find ahead of a test box's intended (or intentionally absent) package-manager stub. `claude`
# and `openspec` are excluded too, defense-in-depth: every test already places its own stub
# earlier on PATH, so a real one here would normally stay shadowed, but a host that happens to
# ship either at /usr/local/bin should never be able to leak in silently.
_EXCLUDED_FROM_SYSBIN = {"node", "npm", "npx", "corepack", "nodejs", "apt-get", "apt", "dnf", "apk", "brew",
                          "claude", "openspec"}


def filtered_sysbin() -> Path:
    global _FILTERED_SYSBIN
    if _FILTERED_SYSBIN is not None:
        return _FILTERED_SYSBIN
    d = Path(tempfile.mkdtemp(prefix="groundwork-test-sysbin-"))
    atexit.register(shutil.rmtree, d, ignore_errors=True)  # test-only scratch dir; never leak it across runs
    for real_dir in ("/usr/bin", "/bin", "/usr/local/bin"):
        p = Path(real_dir)
        if not p.is_dir():
            continue
        for entry in p.iterdir():
            if entry.name in _EXCLUDED_FROM_SYSBIN or (d / entry.name).exists():
                continue
            try:
                (d / entry.name).symlink_to(entry)
            except OSError:
                pass
    _FILTERED_SYSBIN = d
    return d


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
                        GROUNDWORK_NO_LAUNCHCTL="1", NODE_USE_SYSTEM_CA="0", GROUNDWORK_SETUP_SKIP_TESTS="1",
                        # Forces the launchd scheduling path deterministically regardless of the CI
                        # host's real platform (production-code override, mirrors prereq_box's use
                        # of GROUNDWORK_OS for the same reason); real users never set this.
                        GROUNDWORK_OS="darwin")
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
        # Backup dirs are named to the second (groundwork-YYYYMMDD-HHMMSS); on a fast host the
        # two installs above can land in the same second, and setup.sh's own rollback picker
        # then correctly refuses as "ambiguous" between the bare and -1-suffixed name (a real,
        # narrow, pre-existing edge case in latest_backup() this test doesn't intend to exercise
        # here — its own dedicated case for that is below). Force distinct seconds deterministically.
        time.sleep(1.1)
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
            b.env["PATH"] = f"{clean}:{tools}:{filtered_sysbin()}"
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
        check("Node too old: left to the user's version manager, clear message, nothing installed", r.returncode == 1 and "older than 20.19.0" in r.stderr and not (root / "pm.log").exists(), r.stderr)

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


def test_verify_reports_ecc_version() -> None:
    print("setup.sh --verify ECC version reporting (Groundwork 2.0 Phase 1, independent-review finding M5)")
    if shutil.which("bash") is None:
        print("  skip: bash not available")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        a = Box(tmp / "a")
        r = a.run("--non-interactive", "--profile", "work")
        check("setup for ECC-version test exits 0", r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])

        # Realistic multi-line `claude plugin list` output (unlike Box's default one-line stub) —
        # matches the real Claude Code CLI's actual format, confirmed by direct reproduction against
        # a live install (design.md §A.6). Version exactly matches ECC_REF's pin (v2.2.1, see
        # setup.sh): the expected, pinned-match case — no "differs" note.
        (a.root / "bin" / "claude").write_text(
            '#!/usr/bin/env bash\n'
            'case "$1" in\n'
            '  --version) echo "2.1.258 (Claude Code)";;\n'
            '  plugin) printf "Installed plugins:\\n\\n  > ecc@ecc\\n    Version: 2.2.1\\n    Scope: user\\n    Status: enabled\\n";;\n'
            '  *) exit 0;;\n'
            'esac\n'
        )
        os.chmod(a.root / "bin" / "claude", 0o755)
        r = a.run("--verify")
        check("verify: exit 0 with a realistic multi-line claude plugin list stub", r.returncode == 0, r.stdout + r.stderr)
        check("verify: parses the real installed ECC version from 'claude plugin list'",
              "ECC" in r.stdout and "2.2.1" in r.stdout and "version not parsed" not in r.stdout, r.stdout)
        check("verify: version matching the ECC_REF pin reports pinned, no drift note",
              "(pinned to v2.2.1)" in r.stdout and "differs" not in r.stdout, r.stdout)

        # Same shape, but a version other than the ECC_REF pin (e.g. from a manual 'claude plugin
        # update' run outside install.sh's pin) — must still PASS (not a broken install) and name
        # the mismatch distinctly, not fail the row.
        (a.root / "bin" / "claude").write_text(
            '#!/usr/bin/env bash\n'
            'case "$1" in\n'
            '  --version) echo "2.1.258 (Claude Code)";;\n'
            '  plugin) printf "Installed plugins:\\n\\n  > ecc@ecc\\n    Version: 2.1.9\\n    Scope: user\\n    Status: enabled\\n";;\n'
            '  *) exit 0;;\n'
            'esac\n'
        )
        os.chmod(a.root / "bin" / "claude", 0o755)
        r = a.run("--verify")
        check("verify: version differing from the ECC_REF pin is a PASS with a note, not a FAIL",
              r.returncode == 0 and "ECC                 PASS" in r.stdout and "2.1.9" in r.stdout, r.stdout)
        check("verify: pin-mismatch note names the pin and the likely cause",
              "(pinned to v2.2.1 — this differs, likely from a manual 'claude plugin update' outside the pin)" in r.stdout, r.stdout)
    finish()


def test_capabilities_and_routines() -> None:
    print("setup.sh --capability-profile / --doctor / --configure / --routines (Groundwork 2.1)")
    if shutil.which("bash") is None:
        print("  skip: bash not available")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # ---- fresh install with a capability profile: config.json lands under CLAUDE_CONFIG_DIR,
        # not the real home dir, and routines from that profile actually show as enabled — the
        # exact regression a fixed CLAUDE_CONFIG_DIR-blind DEFAULT_PATH bug in groundwork_config.py
        # would reintroduce (setup.sh's own "routines enabled: ..." summary silently read back
        # 'none' before the fix, because init() wrote to ~/.claude while the summary read from
        # CLAUDE_CONFIG_DIR).
        b = Box(tmp / "b")
        r = b.run("--non-interactive", "--profile", "work", "--capability-profile", "sre-cloudops", "--schedule", "daily")
        check("setup with --capability-profile sre-cloudops exits 0", r.returncode == 0, r.stdout[-800:] + r.stderr[-400:])
        cfgfile = b.cfg / "groundwork" / "config.json"
        check("config.json written under CLAUDE_CONFIG_DIR", cfgfile.is_file())
        cfg = json.loads(cfgfile.read_text())
        check("config.json profile is sre-cloudops", cfg["profile"] == "sre-cloudops", cfg)
        check("sre-cloudops routines actually enabled in the written config", cfg["routines"]["jira_eod"]["enabled"] is True, cfg["routines"])
        check("setup output names the enabled routines, not 'none'", "routines enabled: none" not in r.stdout and "jira_eod" in r.stdout, r.stdout)

        # ---- --doctor shows Capabilities/Routines status
        r = b.run("--doctor")
        check("--doctor exits 0 on a healthy install", r.returncode == 0, r.stdout + r.stderr)
        check("--doctor shows the configured capability profile", "Capability profile  CONFIGURED   sre-cloudops" in r.stdout.replace("\t", " ") or "sre-cloudops" in r.stdout, r.stdout)
        check("--doctor shows the -- Routines -- section with real enabled/schedule status", "-- Routines --" in r.stdout and "jira_eod: enabled=True" in r.stdout, r.stdout)

        # ---- regression: --doctor must still show Capabilities/Routines even when core checks
        # fail (previously: verify_install()'s non-zero return under `set -e` short-circuited
        # run_doctor() before verify_capabilities() ever ran, silently dropping the whole section).
        shutil.rmtree(b.cfg / "groundwork" / "playbooks")
        r = b.run("--doctor")
        check("--doctor with a broken core install still exits non-zero (core health reflected)", r.returncode == 1, r.stdout + r.stderr)
        check("--doctor with a broken core install still shows the Capabilities section (regression)",
              "Capability profile" in r.stdout and "sre-cloudops" in r.stdout, r.stdout)
        check("--doctor with a broken core install still shows the Routines section (regression)",
              "-- Routines --" in r.stdout and "jira_eod" in r.stdout, r.stdout)
        (b.cfg / "groundwork" / "playbooks").mkdir(parents=True, exist_ok=True)
        for src in (REPO_ROOT / "playbooks").glob("*.md"):
            shutil.copy(src, b.cfg / "groundwork" / "playbooks" / src.name)

        # ---- regression (independent-review MUST FIX): a hand-corrupted config.json must not
        # crash --doctor outright (worse than the bug above — the whole script aborted silently,
        # not just the Capabilities section, because verify_capabilities()'s own inline-Python
        # pipeline had no fail-open guard under set -euo pipefail). config.json is explicitly
        # documented as hand-editable, so a malformed edit or an interrupted write is realistic.
        good_config = cfgfile.read_text()
        cfgfile.write_text("{ not valid json ][")
        r = b.run("--doctor")
        check("--doctor against a corrupt config.json exits 0 (core checks all still pass)", r.returncode == 0, r.stdout + r.stderr)
        check("--doctor against a corrupt config.json reports Capabilities INVALID, not a crash",
              "Capabilities" in r.stdout and "INVALID" in r.stdout, r.stdout)
        check("--doctor against a corrupt config.json still reaches the Routines section (fail-open, like groundwork_config.load_config())",
              "-- Routines --" in r.stdout, r.stdout)
        cfgfile.write_text(good_config)

        # ---- --configure re-profiles explicitly, no backup/reinstall
        r = b.run("--configure", "--capability-profile", "minimal")
        check("--configure --capability-profile minimal exits 0", r.returncode == 0, r.stdout + r.stderr)
        cfg2 = json.loads(cfgfile.read_text())
        check("--configure actually rewrote config.json to the new profile", cfg2["profile"] == "minimal", cfg2)
        check("--configure did not add a new backup (no reinstall)", len(b.backup_dirs()) == 1, b.backup_dirs())

        # ---- --configure declining the prompt makes no change
        r = b.run("--configure", stdin="1\n")
        check("--configure declining (choice 1) makes no change, exit 0", r.returncode == 0 and "No change made" in r.stdout, r.stdout)
        cfg3 = json.loads(cfgfile.read_text())
        check("declined --configure left the profile as minimal", cfg3["profile"] == "minimal", cfg3)

        # ---- --routines lists configured routines and their status
        r = b.run("--routines")
        check("--routines exits 0 and lists all six routines, all disabled under minimal", r.returncode == 0 and r.stdout.count("enabled=False") == 6, r.stdout)

        # ---- a fresh install with no --capability-profile and non-interactive: config.json never
        # written at all, doctor reports NOT CONFIGURED rather than fabricating a profile
        c = Box(tmp / "c")
        r = c.run("--non-interactive", "--profile", "work")
        check("setup with no capability profile exits 0", r.returncode == 0, r.stdout[-400:] + r.stderr[-300:])
        check("no config.json written when no profile was chosen", not (c.cfg / "groundwork" / "config.json").exists())
        r = c.run("--doctor")
        check("--doctor with no config.json reports Capabilities NOT CONFIGURED, not a guess",
              "Capabilities" in r.stdout and "NOT CONFIGURED" in r.stdout, r.stdout)

        # ---- uninstall removes config.json and unschedules every routine's plist, cleanly
        d = Box(tmp / "d")
        r = d.run("--non-interactive", "--profile", "work", "--capability-profile", "sre-cloudops", "--schedule", "daily")
        check("Box d: setup with sre-cloudops exits 0", r.returncode == 0, r.stdout[-400:] + r.stderr[-300:])
        check("Box d: sre-cloudops scheduled at least one routine's plist (jira_eod)",
              (d.agents / "com.groundwork.routine.jira_eod.plist").is_file(), list(d.agents.glob("*")) if d.agents.exists() else "no agents dir")
        r = d.run("--uninstall")
        check("uninstall after capability setup exits 0", r.returncode == 0, r.stdout[-400:] + r.stderr[-300:])
        check("uninstall removed config.json", not (d.cfg / "groundwork" / "config.json").exists())
        check("uninstall unscheduled every routine plist", not any(d.agents.glob("com.groundwork.routine.*.plist")) if d.agents.exists() else True,
              list(d.agents.glob("*")) if d.agents.exists() else "no agents dir")
    finish()


if __name__ == "__main__":
    for t in (test_setup, test_verify_reports_ecc_version, test_capabilities_and_routines):
        try:
            t()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
