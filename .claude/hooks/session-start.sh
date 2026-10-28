#!/bin/bash
# Cloud sessions only: make the repo's own checks runnable in a fresh container
# (python3 -m pytest tests -q, openspec validate --strict). Idempotent; installs only what is missing; a failed
# install is reported, never fatal, so the session always starts.
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Same version as setup.sh LAST_VERIFIED_OPENSPEC: 1.13.2 passes `openspec validate --changes --strict` on every
# change here, while 1.15.0 (npm latest on 2026-10-28) fails six on its new requirement-length warning.
OPENSPEC_VERSION="1.13.2"

# Stale bytecode once made a restored source file run as its old version: tests must load source.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  grep -qs '^export PYTHONDONTWRITEBYTECODE=1$' "$CLAUDE_ENV_FILE" || echo 'export PYTHONDONTWRITEBYTECODE=1' >> "$CLAUDE_ENV_FILE"
fi

if ! python3 -c "import pytest" >/dev/null 2>&1; then
  python3 -m pip install --quiet pytest || echo "session-start: pytest install failed; run tests with python3 tests/<file>.py" >&2
fi

if ! command -v openspec >/dev/null 2>&1; then
  npm install --global --silent "@fission-ai/openspec@${OPENSPEC_VERSION}" || echo "session-start: OpenSpec install failed" >&2
fi
exit 0
