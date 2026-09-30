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
NODE_MIN_MAJOR=20; NODE_MIN_MINOR=19   # OpenSpec's actual engines.node requirement (>=20.19.0); ECC itself only needs >=18
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js not found on PATH. Groundwork needs Node >=$NODE_MIN_MAJOR.$NODE_MIN_MINOR.0 (the OpenSpec CLI requires it; ECC's own floor is lower, >=18)."; exit 1; }
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
NODE_MINOR="$(node -p 'process.versions.node.split(".")[1]' 2>/dev/null || echo 0)"
if [ "$NODE_MAJOR" -lt "$NODE_MIN_MAJOR" ] || { [ "$NODE_MAJOR" -eq "$NODE_MIN_MAJOR" ] && [ "$NODE_MINOR" -lt "$NODE_MIN_MINOR" ]; }; then
  echo "ERROR: Node.js $(node --version) is older than $NODE_MIN_MAJOR.$NODE_MIN_MINOR.0. The OpenSpec CLI requires it. Upgrade with your Node version manager (nvm/asdf/volta) or from https://nodejs.org/en/download."
  exit 1
fi
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not found on PATH."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found on PATH (Groundwork's own hooks are Python)."; exit 1; }

CLAUDE_VERSION="$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
if [ -n "$CLAUDE_VERSION" ]; then
  echo "Claude Code version: $CLAUDE_VERSION (Groundwork requires >= 2.1, matching ECC's own requirement)"
fi

# ---- 1. ECC -------------------------------------------------------------
# Pinned to a real, tested release tag (Groundwork 2.1) rather than floating `main` — `claude plugin
# marketplace add owner/repo#ref` pins the clone to that ref (confirmed current on Claude Code's
# plugin-marketplace path, 2026-09-28). Bump ECC_REF only after re-testing clean install/upgrade/
# rollback/uninstall against the new tag; set GROUNDWORK_ECC_REF to override for a specific machine
# (e.g. to track `main` again: GROUNDWORK_ECC_REF=main ./install.sh).
ECC_REF="${GROUNDWORK_ECC_REF:-v2.2.1}"
echo ""
echo "-- Installing ECC (github.com/affaan-m/ECC, pinned to $ECC_REF) --"
if claude plugin list 2>/dev/null | grep -q "ecc@ecc"; then
  echo "ECC already installed — skipping (run 'claude plugin update ecc@ecc' to upgrade within the pinned ref)."
else
  claude plugin marketplace add "affaan-m/ECC#$ECC_REF"
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
         "$CLAUDE_DIR"/hooks/groundwork_session_snapshot.py \
         "$CLAUDE_DIR"/hooks/groundwork_telemetry.py
# Health dashboard generator (no server, no LLM): installed beside the playbooks; the configured
# launchd schedule (default weekly) is applied idempotently — one job, replaced on every install.
mkdir -p "$CLAUDE_DIR/groundwork/bin" "$CLAUDE_DIR/groundwork/reports"
cp "$HERE/scripts/groundwork_report.py" "$CLAUDE_DIR/groundwork/bin/groundwork_report.py"
chmod +x "$CLAUDE_DIR/groundwork/bin/groundwork_report.py"
SCHED=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('schedule','weekly'))" "$CLAUDE_DIR/groundwork/report.json" 2>/dev/null || echo weekly)
if [ "$(uname -s)" = "Darwin" ]; then
  python3 "$CLAUDE_DIR/groundwork/bin/groundwork_report.py" schedule "$SCHED" >/dev/null && echo "  report schedule: $SCHED via launchd (change: python3 ~/.claude/groundwork/bin/groundwork_report.py schedule <disabled|daily|weekly|monthly|yearly>)"
else
  python3 "$CLAUDE_DIR/groundwork/bin/groundwork_report.py" schedule "$SCHED" >/dev/null && echo "  report schedule: $SCHED recorded, but automatic runs need macOS launchd — on this OS run 'python3 ~/.claude/groundwork/bin/groundwork_report.py generate --snapshot' manually or from cron"
fi
# Capability configuration and Routines (Groundwork 2.1) — installed unconditionally, dormant
# until a config.json exists (setup.sh's optional capability-selection flow writes one; without
# it, groundwork_config.py falls back to the minimal profile and every routine stays disabled).
cp "$HERE/scripts/groundwork_config.py" "$HERE/scripts/groundwork_routines.py" "$CLAUDE_DIR/groundwork/bin/"
chmod +x "$CLAUDE_DIR/groundwork/bin/groundwork_config.py" "$CLAUDE_DIR/groundwork/bin/groundwork_routines.py"

# Integration Catalog (Groundwork 2.1) — a structured, read-only catalog of known external-system
# integrations and their truthfully-observed readiness (see docs/INTEGRATIONS.md). Installs
# nothing itself and stores no credentials; dormant/NOT CONFIGURED for everything until a
# config.json exists.
cp "$HERE/scripts/groundwork_integrations.py" "$CLAUDE_DIR/groundwork/bin/"
chmod +x "$CLAUDE_DIR/groundwork/bin/groundwork_integrations.py"
# One best-effort cache refresh so the statusLine (below) has real data from the first render —
# never repeated on a timer; the only other refreshes are setup.sh's --configure/--doctor
# (openspec/changes/add-statusline/design.md Decision 1: lifecycle-driven, not scheduled).
python3 "$CLAUDE_DIR/groundwork/bin/groundwork_integrations.py" refresh >/dev/null 2>&1 || true

# statusLine (Groundwork 2.1) — a Claude Code `statusLine` command rendering Groundwork-specific
# state (capability profile, last-completed-turn playbook/validation, cached Integration Catalog
# readiness, live git branch/dirty). Reads only cached/local data; never probes integrations
# itself (see docs/ARCHITECTURE.md and openspec/changes/add-statusline/).
cp "$HERE/scripts/groundwork_statusline.py" "$CLAUDE_DIR/groundwork/bin/"
chmod +x "$CLAUDE_DIR/groundwork/bin/groundwork_statusline.py"

# Installed version (top CHANGELOG entry) — shown in the session snapshot and stamped on telemetry.
grep -m1 -oE '^## [0-9]+\.[0-9]+\.[0-9]+' "$HERE/CHANGELOG.md" | sed 's/^## //' > "$CLAUDE_DIR/groundwork/VERSION"

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
