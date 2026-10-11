"""Mutation check for the snapshot hook's worktree section: each mutant removes one safety or bounding clause and
tests/test_hooks.py (-k worktrees) must then fail. Run from the repository root:

    python3 tests/mutation/mutate_snapshot_worktrees.py

The hook file is rewritten for every mutant and restored afterwards; do not edit it, or run other tests, while this
runs. Not collected by pytest (the name does not start with test_)."""
import subprocess, sys
from pathlib import Path
T = Path("hooks/groundwork_session_snapshot.py"); ORIG = T.read_text()
M = [
 ("no deadline check", 'if left <= 0:\n            return _NO_TIME', 'if False:\n            return _NO_TIME'),
 ("git failure counted as pushed", 'elif state is None:\n            unreadable += 1', 'elif state is None:\n            pushed += 1'),
 ("own gitdir listed (submodule owner)", 'if os.path.realpath(owner) == here:\n                    continue', 'if False:\n                    continue'),
 ("separate-git-dir own dir not skipped", 'if own_git_dir is not None and os.path.realpath(path) == own_git_dir:\n                continue', 'if False:\n                continue'),
 ("owner checkout not examined", 'state_path = owner  # another checkout of the same repository, found through its git directory', 'continue'),
 ("index rewritten", 'env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}', 'env = None'),
 ("newline forges entry", 'records = listing.split("\\0") if nul else listing.splitlines()', 'records = listing.replace("\\0", "\\n").splitlines()'),
 ("no char budget", 'if used + len(row) > MAX_WORKTREE_CHARS:', 'if False:'),
 ("no examined cap", 'if examined >= MAX_WORKTREES_EXAMINED:', 'if False:'),
 ("strict decode of git output", 'text=True, errors=errors, timeout=timeout', 'text=True, timeout=timeout'),
 ("surrogates not preserved", 'env=call_env, errors="surrogateescape")', 'env=call_env, errors="replace")'),
 ("nested orphan trusted (no ceiling)", 'call_env = {**env, "GIT_CEILING_DIRECTORIES": os.path.dirname(os.path.abspath(path))}', 'call_env = env'),
 ("no .git check", 'if not os.path.exists(os.path.join(path, ".git")):', 'if False:'),
 ("no hook-level deadline", 'deadline = min(time.monotonic() + WORKTREE_BUDGET_SECONDS, _T0 + HOOK_DEADLINE_SECONDS)', 'deadline = time.monotonic() + WORKTREE_BUDGET_SECONDS'),
 ("gone upstream not named", '"upstream branch gone" if gone else', '"no upstream tracking branch" if gone else'),
 ("no listed cap", 'for row in local_only[:MAX_WORKTREES_LISTED]:', 'for row in local_only:'),
 ("path cut from the right", 'return text if len(text) <= limit else "…" + text[-(limit - 1):]', 'return text if len(text) <= limit else text[:limit - 1] + "…"'),
 ("section failure kills snapshot", '        except Exception:\n            pass  # this section must never cost the rest of the snapshot', '        except KeyError:\n            pass'),
 ("no -z fallback", 'if listing is None:  # an older git may not accept -z', 'if False:  # an older git may not accept -z'),
 ("guard: missing-only silent", 'if not (local_only or missing or locked_missing or unreadable or unexamined):', 'if not (local_only or locked_missing or unreadable or unexamined):'),
 ("guard: locked-only silent", 'if not (local_only or missing or locked_missing or unreadable or unexamined):', 'if not (local_only or missing or unreadable or unexamined):'),
 ("guard: unreadable-only silent", 'if not (local_only or missing or locked_missing or unreadable or unexamined):', 'if not (local_only or missing or locked_missing or unexamined):'),
 ("guard: unexamined-only silent", 'if not (local_only or missing or locked_missing or unreadable or unexamined):', 'if not (local_only or missing or locked_missing or unreadable):'),
 ("no per-call clamp", 'timeout=min(GIT_TIMEOUT, left)', 'timeout=GIT_TIMEOUT'),
 ("untracked dirs collapsed", '"status", "--porcelain", "-b", "--untracked-files=all", sibling=True', '"status", "--porcelain", "-b", sibling=True'),
 ("bare repos listed", 'if "bare" not in e]', 'if True]'),
 ("locked not separated", 'if "locked" in entry:\n                locked_missing += 1', 'if False:\n                locked_missing += 1'),
 ("branch not clipped", '{_clip_path(branch, 40)}', '{branch}'),
]
surv = []
for name, old, new in M:
    t = T.read_text()
    if old not in t:
        print("SKIP", name); surv.append(name + " [not found]"); continue
    T.write_text(t.replace(old, new, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "tests/test_hooks.py", "-q", "-k", "worktrees", "-x"], capture_output=True, text=True, timeout=300)
        caught = r.returncode != 0
    finally:
        T.write_text(ORIG)
    print(("caught   " if caught else "SURVIVED ") + name, flush=True)
    if not caught: surv.append(name)
print(f"{len(M)-len(surv)}/{len(M)} caught; survivors: {surv}")
