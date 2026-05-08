#!/usr/bin/env bats
# Tests for .claude/hooks/log_tool_call.sh

setup() {
  load test_helper/setup
  HOOK="$HOOK_DIR/log_tool_call.sh"
  LOG_TMPDIR="$(mktemp -d "${BATS_TEST_TMPDIR:-/tmp}/log.XXXXXX")"
}

teardown() {
  [ -d "${LOG_TMPDIR:-}" ] && rm -rf "$LOG_TMPDIR"
}

run_hook() {
  CLAUDE_PROJECT_DIR="$LOG_TMPDIR" run bash "$HOOK" <<< "$1"
}

get_last_log() {
  cat "$LOG_TMPDIR/docs/logs/audit/"*.jsonl 2>/dev/null | tail -1
}

# ============================================================
# Bash tool logging
# ============================================================

@test "logs Bash command" {
  run_hook "$(make_log_input Bash '{"command":"git status"}')"
  [ "$status" -eq 0 ]
  local entry
  entry=$(get_last_log)
  [[ $(echo "$entry" | jq -r '.tool') == "Bash" ]]
  [[ $(echo "$entry" | jq -r '.input') == "git status" ]]
  [[ $(echo "$entry" | jq -r '.status') == "allowed" ]]
}

# ============================================================
# Edit/Write tool logging
# ============================================================

@test "logs Edit file path" {
  run_hook "$(make_log_input Edit '{"file_path":"/src/main.py"}')"
  [ "$status" -eq 0 ]
  local entry
  entry=$(get_last_log)
  [[ $(echo "$entry" | jq -r '.tool') == "Edit" ]]
  [[ $(echo "$entry" | jq -r '.input') == "/src/main.py" ]]
}

@test "logs Write file path" {
  run_hook "$(make_log_input Write '{"file_path":"/src/new.py"}')"
  [ "$status" -eq 0 ]
  local entry
  entry=$(get_last_log)
  [[ $(echo "$entry" | jq -r '.tool') == "Write" ]]
  [[ $(echo "$entry" | jq -r '.input') == "/src/new.py" ]]
}

# ============================================================
# WebFetch tool logging
# ============================================================

@test "logs WebFetch URL" {
  run_hook "$(make_log_input WebFetch '{"url":"https://example.com/api"}')"
  [ "$status" -eq 0 ]
  local entry
  entry=$(get_last_log)
  [[ $(echo "$entry" | jq -r '.tool') == "WebFetch" ]]
  [[ $(echo "$entry" | jq -r '.input') == "https://example.com/api" ]]
}

# ============================================================
# Agent tool logging
# ============================================================

@test "logs Agent with subagent type and description" {
  run_hook "$(make_log_input Agent '{"subagent_type":"Explore","description":"find API endpoints"}')"
  [ "$status" -eq 0 ]
  local entry
  entry=$(get_last_log)
  [[ $(echo "$entry" | jq -r '.tool') == "Agent" ]]
  [[ $(echo "$entry" | jq -r '.input') == "Explore: find API endpoints" ]]
}

@test "logs Agent without subagent type defaults to general-purpose" {
  run_hook "$(make_log_input Agent '{"description":"research task"}')"
  [ "$status" -eq 0 ]
  local entry
  entry=$(get_last_log)
  [[ $(echo "$entry" | jq -r '.input') == "general-purpose: research task" ]]
}

# ============================================================
# Session tracking
# ============================================================

@test "records session ID" {
  run_hook "$(make_log_input Bash '{"command":"ls"}' "sess-abc-123")"
  [ "$status" -eq 0 ]
  local entry
  entry=$(get_last_log)
  [[ $(echo "$entry" | jq -r '.session') == "sess-abc-123" ]]
}

# ============================================================
# Log file management
# ============================================================

@test "creates log directory if missing" {
  [ ! -d "$LOG_TMPDIR/docs/logs/audit" ]
  run_hook "$(make_log_input Bash '{"command":"ls"}')"
  [ "$status" -eq 0 ]
  [ -d "$LOG_TMPDIR/docs/logs/audit" ]
}

@test "appends to existing log file" {
  run_hook "$(make_log_input Bash '{"command":"first"}')"
  run_hook "$(make_log_input Bash '{"command":"second"}')"
  [ "$status" -eq 0 ]
  local count
  count=$(wc -l < "$LOG_TMPDIR/docs/logs/audit/"*.jsonl | tr -d ' ')
  [ "$count" -eq 2 ]
}

@test "log entry contains timestamp" {
  run_hook "$(make_log_input Bash '{"command":"ls"}')"
  [ "$status" -eq 0 ]
  local entry
  entry=$(get_last_log)
  [[ $(echo "$entry" | jq -r '.ts') =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T ]]
}

# ============================================================
# Edge cases
# ============================================================

@test "exits 0 with empty tool name" {
  CLAUDE_PROJECT_DIR="$LOG_TMPDIR" run bash "$HOOK" <<< '{"tool_name":"","tool_input":{}}'
  [ "$status" -eq 0 ]
}

@test "exits 0 with empty command" {
  CLAUDE_PROJECT_DIR="$LOG_TMPDIR" run bash "$HOOK" <<< '{"tool_name":"Bash","tool_input":{"command":""}}'
  [ "$status" -eq 0 ]
}

@test "exits 0 with missing tool_input" {
  CLAUDE_PROJECT_DIR="$LOG_TMPDIR" run bash "$HOOK" <<< '{"tool_name":"Bash"}'
  [ "$status" -eq 0 ]
}

@test "valid JSONL output" {
  run_hook "$(make_log_input Bash '{"command":"echo hello"}')"
  [ "$status" -eq 0 ]
  local entry
  entry=$(get_last_log)
  echo "$entry" | jq empty
}
