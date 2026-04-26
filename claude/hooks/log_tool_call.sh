#!/bin/bash
# Claude Code PostToolUse hook: append allowed tool calls to the audit log.
#
# Writes one JSONL line per call to docs/logs/audit/YYYY-MM-DD.jsonl.
# Records: timestamp, tool, input summary (command / file path / URL), session.
# Does NOT record: file contents, command stdout/stderr, Read/Grep/Glob calls.
#
# Logging failures are silent (exit 0) — audit is observability, not enforcement.

set -u

INPUT=$(cat)

# jq is required; if missing, silently skip.
command -v jq >/dev/null 2>&1 || exit 0

TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null || true)
SESSION=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || true)
[ -z "$TOOL" ] && exit 0

case "$TOOL" in
Bash)
  SUMMARY=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
  ;;
Edit | Write | MultiEdit | NotebookEdit)
  SUMMARY=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
  ;;
WebFetch)
  SUMMARY=$(echo "$INPUT" | jq -r '.tool_input.url // empty' 2>/dev/null || true)
  ;;
Agent)
  SUMMARY=$(echo "$INPUT" | jq -r '(.tool_input.subagent_type // "general-purpose") + ": " + (.tool_input.description // "")' 2>/dev/null || true)
  ;;
*)
  SUMMARY=$(echo "$INPUT" | jq -rc '.tool_input // {}' 2>/dev/null | head -c 200 || true)
  ;;
esac

[ -z "$SUMMARY" ] && exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
LOG_DIR="$PROJECT_DIR/docs/logs/audit"
mkdir -p "$LOG_DIR" 2>/dev/null || true
LOG_FILE="$LOG_DIR/$(date -u +%Y-%m-%d).jsonl"

TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

jq -cn --arg ts "$TS" --arg tool "$TOOL" --arg input "$SUMMARY" --arg session "$SESSION" \
  '{ts: $ts, tool: $tool, status: "allowed", input: $input, session: $session}' \
  >>"$LOG_FILE" 2>/dev/null || true

exit 0
