#!/bin/bash
# Installs RTK (https://github.com/rtk-ai/rtk) and registers its Claude Code hook.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

export PATH="$HOME/.local/bin:$PATH"
FALLBACK_VERSION="v0.51.0"

if ! command -v rtk >/dev/null 2>&1; then
  # The GitHub API is blocked by the proxy, so resolve the latest tag via git.
  VERSION=$(git ls-remote --tags --refs https://github.com/rtk-ai/rtk 2>/dev/null \
    | awk '{print $2}' | sed 's|refs/tags/||' \
    | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1 || true)
  VERSION="${VERSION:-$FALLBACK_VERSION}"
  curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh \
    | RTK_VERSION="$VERSION" sh
fi

# Idempotent: registers RTK.md, the CLAUDE.md reference and the PreToolUse hook.
rtk init -g --auto-patch

# Make rtk available in later Bash calls of this session.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
fi
