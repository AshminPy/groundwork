"""Mutation check for the snapshot hook's worktree section: each mutant removes one safety or bounding clause and
tests/test_hooks.py (-k worktrees) must then fail. A mutant that makes the tests hang counts as caught. Run from the
repository root:

    python3 tests/mutation/mutate_snapshot_worktrees.py

It works on a COPY of the tracked files in a temporary directory, so the working tree is never modified and an
interrupted run cannot leave a mutated hook behind. Not collected by pytest (the name does not start with test_)."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path.cwd()
WORK = Path(tempfile.mkdtemp(prefix="gw-mutate-snapshot-"))
files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.split(b"\0")
for rel in filter(None, files):
    src = ROOT / rel.decode()
    if src.is_file():
        dst = WORK / rel.decode()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
T = WORK / "hooks" / "groundwork_session_snapshot.py"
ORIG = T.read_text()
M = [
 ("no deadline check", 'if left <= 0:\n            return _NO_TIME', 'if False:\n            return _NO_TIME'),
 ("git failure counted as pushed", 'elif state is None:\n            unreadable += 1', 'elif state is None:\n            pushed += 1'),
 ("own gitdir listed (submodule owner)", 'if os.path.realpath(owner) == here:\n                    continue', 'if False:\n                    continue'),
 ("separate-git-dir own dir not skipped", 'if own_git_dir is not None and os.path.realpath(path) == own_git_dir:\n                continue', 'if False:\n                continue'),
 ("owner checkout not examined", 'state_path = owner  # another checkout of the same repository, found through its git directory', 'continue'),
 ("index rewritten", 'env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}', 'env = None'),
 ("newline forges entry", 'records = listing.split("\\0") if nul else listing.splitlines()', 'records = listing.replace("\\0", "\\n").splitlines()'),
 ("no char budget", 'if used + 1 + len(row) + reserve > budget:', 'if False:'),
 ("no examined cap", 'if examined >= MAX_WORKTREES_EXAMINED:', 'if False:'),
 ("strict decode of git output", 'text=True, errors=errors, timeout=timeout', 'text=True, timeout=timeout'),
 ("surrogates not preserved", 'env=env, errors="surrogateescape")', 'env=env, errors="replace")'),
 ("no .git check", 'if not os.path.exists(dot_git):', 'if False:'),
 ("no hook-level deadline", 'deadline = min(time.monotonic() + WORKTREE_BUDGET_SECONDS, _T0 + HOOK_DEADLINE_SECONDS)', 'deadline = time.monotonic() + WORKTREE_BUDGET_SECONDS'),
 ("gone upstream not named", '"upstream branch gone" if gone else', '"no upstream tracking branch" if gone else'),
 ("no listed cap", 'for k, row in enumerate(rows[:MAX_WORKTREES_LISTED]):', 'for k, row in enumerate(rows):'),
 ("path cut from the right", 'return text if len(text) <= limit else "…" + text[-(limit - 1):]', 'return text if len(text) <= limit else text[:limit - 1] + "…"'),
 ("section failure kills snapshot", '        except Exception:\n            pass  # this section must never cost the rest of the snapshot', '        except KeyError:\n            pass'),
 ("no -z fallback", 'if listing is None:  # an older git may not accept -z', 'if False:  # an older git may not accept -z'),
 ("guard: missing-only silent", 'if not (local_only or missing or locked_missing or unreadable or unexamined):', 'if not (local_only or locked_missing or unreadable or unexamined):'),
 ("guard: locked-only silent", 'if not (local_only or missing or locked_missing or unreadable or unexamined):', 'if not (local_only or missing or unreadable or unexamined):'),
 ("guard: unreadable-only silent", 'if not (local_only or missing or locked_missing or unreadable or unexamined):', 'if not (local_only or missing or locked_missing or unexamined):'),
 ("guard: unexamined-only silent", 'if not (local_only or missing or locked_missing or unreadable or unexamined):', 'if not (local_only or missing or locked_missing or unreadable):'),
 ("no per-call clamp", 'timeout=min(GIT_TIMEOUT, left)', 'timeout=GIT_TIMEOUT'),
 ("untracked dirs collapsed", '"status", "--porcelain", "-b", "--untracked-files=all")', '"status", "--porcelain", "-b")'),
 ("bare repos listed", 'if "bare" not in e]', 'if True]'),
 ("locked not separated", 'if "locked" in entry:\n                locked_missing += 1', 'if False:\n                locked_missing += 1'),
 ("branch not clipped", '{_clip_path(branch, 40)}', '{branch}'),
 ("section ignores the room left under the cap", 'worktree_facts(cwd, budget=min(MAX_WORKTREE_CHARS, max(0, room)))', 'worktree_facts(cwd)'),
 ("overflow line not reserved", 'reserve = OVERFLOW_LINE_CHARS if len(rows) > k + 1 else 0', 'reserve = 0'),
 ("deadline kill reported as unreadable", 'if out is None and time.monotonic() >= deadline:', 'if False:'),
 ("empty .git directory trusted", 'if os.path.exists(dot_git) and not (os.path.isfile(dot_git) or os.path.isfile(os.path.join(dot_git, "HEAD"))):', 'if False:'),
 ("ambiguous listing guessed", 'if key in current:\n            raise ValueError("ambiguous listing")', 'if False:\n            raise ValueError("ambiguous listing")'),
 ("budget default bound at definition", 'budget = MAX_WORKTREE_CHARS if budget is None else budget', 'budget = 700 if budget is None else budget'),
 ("section lines not fitted to the budget", 'return _fit(lines, budget)', 'return lines'),
 ("ambiguous line not fitted to the budget", 'return _fit(["other worktrees of this repository: the listing is ambiguous (a path contains a newline), so none was examined (git worktree list)"], budget)', 'return ["other worktrees of this repository: the listing is ambiguous (a path contains a newline), so none was examined (git worktree list)"]'),
 ("fit drops the summary first", 'lines.pop()', 'lines.pop(0)'),
 ("fit trims nothing", 'lines.pop()', 'break'),
 ("rows in git listing order, not by risk", 'rows = [row for _, row in sorted(local_only, key=lambda ranked: ranked[0])]', 'rows = [row for _, row in local_only]'),
 ("overflow line reserved for the last row too", 'reserve = OVERFLOW_LINE_CHARS if len(rows) > k + 1 else 0', 'reserve = OVERFLOW_LINE_CHARS'),
 ("fit drops a section that exactly fits", 'while lines and len("\\n".join(lines)) > budget:', 'while lines and len("\\n".join(lines)) >= budget:'),
]

surv = []
for name, old, new in M:
    t = ORIG
    if old not in t:
        print(f"STALE (pattern not found): {name}")
        surv.append(name + " [pattern not found]")
        continue
    T.write_text(t.replace(old, new, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "tests/test_hooks.py", "-q", "-k", "worktrees", "-x"], cwd=WORK,
                           capture_output=True, text=True, timeout=300,
                           env={k: v for k, v in os.environ.items() if k != "GIT_OPTIONAL_LOCKS"})
        caught, how = r.returncode != 0, "caught   "
    except subprocess.TimeoutExpired:
        caught, how = True, "caught (timeout) "
    finally:
        T.write_text(ORIG)
    print((how if caught else "SURVIVED ") + name, flush=True)
    if not caught:
        surv.append(name)
shutil.rmtree(WORK, ignore_errors=True)
print(f"{len(M) - len(surv)}/{len(M)} caught; survivors: {surv}")
sys.exit(1 if surv else 0)
