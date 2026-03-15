#!/bin/bash

# Sensitive information scanner for Claude Code hooks
# Usage: scan_sensitive_info.sh <mode>
# Modes: prompt, read, write

set -euo pipefail

MODE="${1:-}"
PATTERNS_FILE="$HOME/.claude/hooks/rules/sensitive_patterns.json"
INPUT=$(cat)

# Validate mode
if [[ -z "$MODE" ]]; then
  echo "Error: mode argument required (prompt|read|write)" >&2
  exit 1
fi

# Check patterns file exists
if [[ ! -f "$PATTERNS_FILE" ]]; then
  exit 0
fi

# Extract text to scan based on mode
scan_text=""
case "$MODE" in
  prompt)
    scan_text=$(echo "$INPUT" | jq -r '.prompt // empty')
    ;;
  read)
    file_path=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
    if [[ -n "$file_path" && -f "$file_path" ]]; then
      scan_text=$(head -c 100000 "$file_path" 2>/dev/null || echo "")
    fi
    ;;
  write)
    # Check content (Write tool) and new_string (Edit/MultiEdit tool)
    content=$(echo "$INPUT" | jq -r '.tool_input.content // empty')
    new_string=$(echo "$INPUT" | jq -r '.tool_input.new_string // empty')
    scan_text="${content}${new_string}"
    ;;
  *)
    exit 0
    ;;
esac

# Nothing to scan
if [[ -z "$scan_text" ]]; then
  exit 0
fi

# Scan text against each pattern
rule_names=$(jq -r 'keys[]' "$PATTERNS_FILE")
for rule_name in $rule_names; do
  pattern=$(jq -r ".[\"$rule_name\"].pattern" "$PATTERNS_FILE")
  message=$(jq -r ".[\"$rule_name\"].message" "$PATTERNS_FILE")

  if echo "$scan_text" | grep -qP "$pattern" 2>/dev/null; then
    # Sensitive info detected - output block response based on mode
    case "$MODE" in
      prompt)
        jq -n \
          --arg reason "⚠ BLOCKED: $message ($rule_name). Prompt contains sensitive information." \
          '{
            decision: "block",
            reason: $reason
          }'
        ;;
      read|write)
        jq -n \
          --arg reason "⚠ BLOCKED: $message ($rule_name)" \
          '{
            hookSpecificOutput: {
              hookEventName: "PreToolUse",
              permissionDecision: "deny",
              permissionDecisionReason: $reason
            }
          }'
        ;;
    esac
    exit 0
  fi
done

# No sensitive info found
exit 0
