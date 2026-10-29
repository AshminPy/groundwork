#!/bin/bash
# Cloud sessions only, check-only: installs nothing. Tools come from the explicit, pinned scripts/cloud-setup.sh
# (set it as the environment's setup script). This hook sets PYTHONDONTWRITEBYTECODE and says what is missing.
# Never fatal, so the session always starts.
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Stale bytecode once made a restored source file run as its old version: tests must load source.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  grep -qs '^export PYTHONDONTWRITEBYTECODE=1$' "$CLAUDE_ENV_FILE" || echo 'export PYTHONDONTWRITEBYTECODE=1' >> "$CLAUDE_ENV_FILE"
fi

missing=""
python3 -c "import pytest" >/dev/null 2>&1 || missing="$missing pytest"
command -v openspec >/dev/null 2>&1 || [ -x "$HOME/.local/bin/openspec" ] || missing="$missing openspec"
if [ -n "$missing" ]; then
  echo "session-start: missing:$missing. Run scripts/cloud-setup.sh (or set it as this environment's setup script)." >&2
fi
exit 0
