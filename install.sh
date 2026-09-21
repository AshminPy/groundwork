#!/usr/bin/env bash
# Groundwork installer.
#
# Installs, in order:
#   1. ECC (github.com/affaan-m/ECC) as a Claude Code plugin — the official,
#      single supported install path (do NOT also run ECC's own manual installer;
#      see ECC's README "Pick one path only").
#   2. OpenSpec CLI (github.com/Fission-AI/OpenSpec) globally via npm.
#   3. Groundwork's own rules, hooks and task playbooks into ~/.claude/, and merges the required
#      settings.json entries (never overwrites your existing settings — see
#      scripts/merge_settings.py for exactly what it touches). A pre-Groundwork
#      copy of the rules under ~/.claude/rules/harness/ is moved to a backup so
#      nothing is loaded twice (scripts/migrate_legacy_rules.py).
#
# Options:
#   --agent-teams   also set CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 in settings.json
#                   (Claude Code's experimental Agent Teams; opt-in, never default —
#                   it changes how named subagents launch, see docs/en/agent-teams).
#
# Safe to re-run: every step is idempotent.
#
# What this script does NOT do: it does not run `openspec init` in any project —
# that's a per-repo step you run yourself (see README.md "Per-project setup").
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
MERGE_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --agent-teams) MERGE_ARGS+=("--agent-teams") ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg (see --help)"; exit 1 ;;
  esac
done

echo "== Groundwork installer =="
echo "Target: $CLAUDE_DIR"
echo ""

# ---- 0. Preconditions -------------------------------------------------------
command -v claude >/dev/null 2>&1 || { echo "ERROR: 'claude' (Claude Code) not found on PATH. Install it first: https://claude.com/claude-code"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js not found on PATH. Groundwork needs Node >=18 (ECC's hooks and the OpenSpec CLI both require it)."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not found on PATH."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found on PATH (Groundwork's own hooks are Python)."; exit 1; }

CLAUDE_VERSION="$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
if [ -n "$CLAUDE_VERSION" ]; then
  echo "Claude Code version: $CLAUDE_VERSION (Groundwork requires >= 2.1, matching ECC's own requirement)"
fi

# ---- 1. ECC -------------------------------------------------------------
echo ""
echo "-- Installing ECC (github.com/affaan-m/ECC) --"
if claude plugin list 2>/dev/null | grep -q "ecc@ecc"; then
  echo "ECC already installed — skipping (run 'claude plugin update ecc@ecc' to upgrade)."
else
  claude plugin marketplace add affaan-m/ECC
  claude plugin install ecc@ecc --scope user --config hook_profile=standard
fi

# ---- 2. OpenSpec ----------------------------------------------------------
echo ""
echo "-- Installing OpenSpec CLI (github.com/Fission-AI/OpenSpec) --"
if command -v openspec >/dev/null 2>&1; then
  echo "OpenSpec already installed ($(openspec --version 2>/dev/null || echo 'version unknown')) — skipping."
else
  npm install -g @fission-ai/openspec@latest
fi
openspec config set telemetry.enabled false >/dev/null 2>&1 || true

# ---- 3. Groundwork's own rules and hooks -----------------------------------
echo ""
echo "-- Installing Groundwork rules and hooks --"
python3 "$HERE/scripts/migrate_legacy_rules.py" "$CLAUDE_DIR"
mkdir -p "$CLAUDE_DIR/rules/groundwork" "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/groundwork/playbooks"
cp "$HERE"/rules/*.md "$CLAUDE_DIR/rules/groundwork/"
cp "$HERE"/hooks/*.py "$CLAUDE_DIR/hooks/"
# Task playbooks are read on demand by rules/task-routing.md; they live outside rules/ so
# Claude Code never auto-loads them (see docs/ARCHITECTURE.md "Task routing").
cp "$HERE"/playbooks/*.md "$CLAUDE_DIR/groundwork/playbooks/"
chmod +x "$CLAUDE_DIR"/hooks/block_protected_push.py \
         "$CLAUDE_DIR"/hooks/require_material_review.py \
         "$CLAUDE_DIR"/hooks/groundwork_session_snapshot.py

python3 "$HERE/scripts/merge_settings.py" "${MERGE_ARGS[@]+"${MERGE_ARGS[@]}"}" "$CLAUDE_DIR/settings.json"

echo ""
echo "== Groundwork installed. =="
echo ""
echo "Next steps:"
echo "  1. In any project you want spec-driven MATERIAL work in, run: openspec init --tools claude"
echo "  2. Read README.md and docs/ARCHITECTURE.md for how the harness behaves."
echo "  3. Optional sanity check: python3 $HERE/tests/test_hooks.py"
if [ ${#MERGE_ARGS[@]} -eq 0 ]; then
  echo "  4. Agent Teams stay off. To opt in later: ./install.sh --agent-teams (interactive sessions only)."
fi
