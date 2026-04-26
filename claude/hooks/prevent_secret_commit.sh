#!/bin/bash
# Claude Code PreToolUse hook: block git commit if staged files match sensitive patterns.
# This hook is triggered before Bash tool calls containing "git commit".
# Exit code 0 = allow, exit code 2 = block.

set -euCo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only check git commit commands
if ! echo "$COMMAND" | grep -qE '^\s*git\s+commit'; then
  exit 0
fi

# Sensitive filename patterns (checked against staged file names)
SENSITIVE_PATTERNS=(
  '\.env$'
  '\.env\.'
  '\.env\.local'
  '\.env\.production'
  'credentials?'
  'secrets?'
  '\.pem$'
  '\.key$'
  '\.p12$'
  '\.pkcs12$'
  '\.jks$'
  '\.pfx$'
  'id_rsa'
  'id_ed25519'
  '\.aws/'
  '\.gcp/'
)

ALLOWLISTED_SENSITIVE_PATHS=(
  'claude/hooks/block_secret_content.sh'
  'claude/hooks/prevent_secret_commit.sh'
  'codex/hooks/adapt_block_secret_content.sh'
  'tests/claude-hooks/prevent_secret_commit.bats'
)

is_allowlisted_sensitive_path() {
  local _file="$1"

  local _allowed
  for _allowed in "${ALLOWLISTED_SENSITIVE_PATHS[@]}"; do
    [ "$_file" = "$_allowed" ] && return 0
  done

  return 1
}

# Get staged files
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null)

if [ -z "$STAGED_FILES" ]; then
  exit 0
fi

BLOCKED_FILES=()

for pattern in "${SENSITIVE_PATTERNS[@]}"; do
  MATCHES=$(echo "$STAGED_FILES" | grep -iE "$pattern" || true)
  if [ -n "$MATCHES" ]; then
    while IFS= read -r file; do
      is_allowlisted_sensitive_path "$file" && continue
      BLOCKED_FILES+=("$file")
    done <<<"$MATCHES"
  fi
done

if [ ${#BLOCKED_FILES[@]} -gt 0 ]; then
  echo "BLOCKED: Commit rejected — staged files may contain secrets." >&2
  echo "" >&2
  echo "The following files match sensitive filename patterns and must not be committed:" >&2
  for file in "${BLOCKED_FILES[@]}"; do
    echo "  - $file" >&2
  done
  echo "" >&2
  echo "Action required:" >&2
  echo "  1. Unstage these files: git reset HEAD <file>" >&2
  echo "  2. Ensure secrets are never staged. Use .gitignore or store them in Google Secret Manager." >&2
  echo "  3. If unsure, ask the user for guidance before proceeding." >&2
  exit 2
fi

exit 0
