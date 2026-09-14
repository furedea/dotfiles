#!/usr/bin/env bats
# Tests for .claude/statusline/statusline.py

setup() {
  load test-helper/setup
  STATUSLINE="$REPO_ROOT/agents/claude/statusline/statusline.py"
}

# Build a minimal statusline JSON input.
# Usage: make_statusline_input '{"model":{"display_name":"Opus"},...}'
make_statusline_input() {
  printf '%s' "$1"
}

MINIMAL_INPUT='{"model":{"display_name":"Opus 4.6"},"cwd":"/tmp/test","context_window":{"used_percentage":25}}'

# ============================================================
# File structure
# ============================================================

@test "statusline.py exists and is executable" {
  [ -f "$STATUSLINE" ]
  [ -x "$STATUSLINE" ]
}

# Basic output
# ============================================================

@test "produces two lines of output" {
  run "$STATUSLINE" <<< "$MINIMAL_INPUT"
  [ "$status" -eq 0 ]
  [ "${#lines[@]}" -eq 2 ]
}

@test "line 1 contains model name" {
  run "$STATUSLINE" <<< "$MINIMAL_INPUT"
  [ "$status" -eq 0 ]
  [[ "${lines[0]}" == *"Opus 4.6"* ]]
}

@test "line 2 contains context percentage" {
  run "$STATUSLINE" <<< "$MINIMAL_INPUT"
  [ "$status" -eq 0 ]
  [[ "${lines[1]}" == *"25%"* ]]
}

@test "line 2 contains Ctx label" {
  run "$STATUSLINE" <<< "$MINIMAL_INPUT"
  [ "$status" -eq 0 ]
  [[ "${lines[1]}" == *"Ctx:"* ]]
}

# ============================================================
# CWD shortening
# ============================================================

@test "shortens long CWD to current directory name" {
  local input='{"model":{"display_name":"Opus"},"cwd":"/a/b/c/d/e","context_window":{"used_percentage":0}}'
  run "$STATUSLINE" <<< "$input"
  [ "$status" -eq 0 ]
  [[ "${lines[0]}" == *"e"* ]]
  [[ "${lines[0]}" != *"c/d/e"* ]]
}

# ============================================================
# Rate limits
# ============================================================

@test "shows 5h rate limit when provided" {
  local input='{"model":{"display_name":"Opus"},"cwd":"/tmp","context_window":{"used_percentage":10},"rate_limits":{"five_hour":{"used_percentage":42,"resets_at":null}}}'
  run "$STATUSLINE" <<< "$input"
  [ "$status" -eq 0 ]
  [[ "${lines[1]}" == *"42%"* ]]
  [[ "${lines[1]}" == *"5h:"* ]]
}

@test "shows 7d rate limit when provided" {
  local input='{"model":{"display_name":"Opus"},"cwd":"/tmp","context_window":{"used_percentage":10},"rate_limits":{"seven_day":{"used_percentage":15,"resets_at":null}}}'
  run "$STATUSLINE" <<< "$input"
  [ "$status" -eq 0 ]
  [[ "${lines[1]}" == *"15%"* ]]
  [[ "${lines[1]}" == *"7d:"* ]]
}

@test "omits 5h section when not present" {
  run "$STATUSLINE" <<< "$MINIMAL_INPUT"
  [ "$status" -eq 0 ]
  [[ "${lines[1]}" != *"5h:"* ]]
}

# ============================================================
# Edge cases
# ============================================================

@test "handles empty model name" {
  local input='{"model":{},"cwd":"/tmp","context_window":{"used_percentage":50}}'
  run "$STATUSLINE" <<< "$input"
  [ "$status" -eq 0 ]
  [ "${#lines[@]}" -eq 2 ]
}

@test "handles 0% context" {
  local input='{"model":{"display_name":"Opus"},"cwd":"/tmp","context_window":{"used_percentage":0}}'
  run "$STATUSLINE" <<< "$input"
  [ "$status" -eq 0 ]
  [[ "${lines[1]}" == *"0%"* ]]
}

@test "handles 100% context" {
  local input='{"model":{"display_name":"Opus"},"cwd":"/tmp","context_window":{"used_percentage":100}}'
  run "$STATUSLINE" <<< "$input"
  [ "$status" -eq 0 ]
  [[ "${lines[1]}" == *"100%"* ]]
}

# ============================================================
# Helper functions
# ============================================================
