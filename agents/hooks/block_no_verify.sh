#!/bin/bash
# Claude Code PreToolUse hook: block git commit --no-verify.
# Claude Code must never bypass pre-commit hooks.
# Exit code 0 = allow, exit code 2 = block.

set -euCo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE 'git\s+commit.*--no-verify|git\s+commit.*-n\b'; then
  cat >&2 <<ERRMSG
BLOCKED: --no-verify flag detected in git commit.

Why: Pre-commit hooks must never be bypassed. They enforce project safety checks.

What to do:
  Claude Code: Investigate and fix the failing hook instead of skipping it.
               If stuck, ask the user for help.
  User: Check which pre-commit hook is failing and fix the underlying issue.
ERRMSG
  exit 2
fi

exit 0
