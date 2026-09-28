"""Small helpers shared by Groundwork's own hooks. Not a hook itself — never registered in
settings.json, never invoked directly by Claude Code. Installed alongside the hook files
(install.sh copies all of hooks/*.py) so the hooks that import it can find it as a sibling
module on their default sys.path.

Kept deliberately tiny: only what at least two hooks genuinely need identically. If a
helper is used by only one hook, it stays in that hook.
"""
import re
import subprocess

# Bash commands that look like a real test/validation run, not just any command. Originally
# defined only in groundwork_telemetry.py; moved here in Groundwork 2.0 Phase 4 because
# require_material_review.py's strengthened review-evidence check needs the exact same
# classification (has a validation command run since the last review?) and duplicating the
# pattern would risk the two hooks silently drifting apart on what counts as "tested".
TEST_CMD = re.compile(
    r"\b(pytest|npm test|npm run test|yarn test|go test|cargo test|make test|tox|nox|"
    r"unittest|terraform validate|terraform plan|kubectl .* --dry-run)\b|"
    r"python3?\s+\S*(?:tests?/|test_)\S*\.py\b"
)


def dirty_change_names(cwd: str) -> set[str]:
    """Names of openspec/changes/<name> directories that git shows as modified or untracked.

    Parses each porcelain line's path into segments instead of substring-matching the raw
    output: with `thing` (committed) and `add-thing` (dirty) in the same repo, a substring
    test wrongly flagged `thing` too (found by independent review of 1.1.0).
    """
    try:
        status = subprocess.run(
            # --untracked-files=all: a brand-new change directory otherwise collapses to one
            # "?? openspec/changes/" line instead of listing its files (caught by the 1.0.0 tests).
            ["git", "-C", cwd, "status", "--porcelain", "--untracked-files=all", "--", "openspec/changes"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return set()
    if status.returncode != 0:
        return set()
    names = set()
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:  # rename: "old -> new"
            path = path.split(" -> ", 1)[1]
        path = path.strip().strip('"')
        parts = path.split("/")
        if len(parts) > 2 and parts[0] == "openspec" and parts[1] == "changes":
            names.add(parts[2])
    return names
