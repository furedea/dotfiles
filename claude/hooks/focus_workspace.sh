#!/usr/bin/env bash
# Claude Code Stop hook: focus the cmux workspace where Claude Code is running

set -euo pipefail

# No-op if not running inside cmux
if [[ -z "${CMUX_WORKSPACE_ID:-}" ]]; then
	exit 0
fi

# Step 1: Bring the cmux macOS window to the front
osascript -e 'tell application "cmux" to activate' 2>/dev/null || true

# Step 2: Switch to the workspace that triggered this hook
cmux select-workspace --workspace "$CMUX_WORKSPACE_ID" 2>/dev/null || true
