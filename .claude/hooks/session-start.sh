#!/bin/bash
# Cloud sessions only: make the repo's own checks runnable in a fresh container
# (python3 -m pytest tests -q, openspec validate --strict). Idempotent; installs only what is missing.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

OPENSPEC_VERSION="1.15.0"   # the version this repo's changes were last validated with

if ! python3 -c "import pytest" >/dev/null 2>&1; then
  python3 -m pip install --quiet pytest
fi

if ! command -v openspec >/dev/null 2>&1; then
  npm install --global --silent "@fission-ai/openspec@${OPENSPEC_VERSION}"
fi

# Stale bytecode once made a restored source file run as its old version: tests must load source.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  grep -qs '^export PYTHONDONTWRITEBYTECODE=1$' "$CLAUDE_ENV_FILE" || echo 'export PYTHONDONTWRITEBYTECODE=1' >> "$CLAUDE_ENV_FILE"
fi
