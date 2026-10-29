#!/bin/bash
# Explicit, reproducible setup for a Claude Code cloud environment that works on this repository. Set it as the
# environment's "Setup script" (cloud environment menu → Edit → Setup script) or run it by hand; nothing runs it
# implicitly. Pinned versions, user-local installs (no global npm, no system pip), idempotent.
#   - pytest, for `python3 -m pytest tests -q`
#   - OpenSpec 1.13.2, for `openspec validate --changes --strict` (setup.sh LAST_VERIFIED_OPENSPEC; 1.15.0, npm
#     latest on 2026-10-28, fails six existing changes on its new requirement-length warning)
set -euo pipefail

PYTEST_VERSION="9.2.0"
OPENSPEC_VERSION="1.13.2"
PREFIX="${GROUNDWORK_TOOLS_PREFIX:-$HOME/.local/groundwork-tools}"

if ! python3 -c "import pytest" >/dev/null 2>&1; then
  python3 -m pip install --user --quiet "pytest==${PYTEST_VERSION}"
fi

if ! command -v openspec >/dev/null 2>&1 || [ "$(openspec --version 2>/dev/null)" != "$OPENSPEC_VERSION" ]; then
  npm install --prefix "$PREFIX" --no-fund --no-audit --silent "@fission-ai/openspec@${OPENSPEC_VERSION}"
  mkdir -p "$HOME/.local/bin"
  ln -sf "$PREFIX/node_modules/.bin/openspec" "$HOME/.local/bin/openspec"
  echo "OpenSpec ${OPENSPEC_VERSION} installed at $HOME/.local/bin/openspec (make sure \$HOME/.local/bin is on PATH)"
fi
python3 -c "import pytest; print('pytest', pytest.__version__)"
"$HOME/.local/bin/openspec" --version 2>/dev/null || openspec --version
