#!/usr/bin/env bats
# End-to-end denial audit checks; record construction is covered by pytest.

setup() {
  load test-helper/setup
  LOG_TMPDIR="$(mktemp -d "${BATS_TEST_TMPDIR:-/tmp}/log.XXXXXX")"
}

teardown() {
  [ -d "${LOG_TMPDIR:-}" ] && rm -rf "$LOG_TMPDIR"
}

get_last_log() {
  cat "$LOG_TMPDIR/docs/logs/audit/"*.jsonl 2>/dev/null | tail -1
}

# ============================================================
# End-to-end: real block hook must emit a Blocked audit row
# ============================================================

@test "guard_forbidden_commands.sh emits a Blocked row for no-verify" {
  AGENT_COMMAND_PERMISSIONS="$REPO_ROOT/agents/command_permissions.json" \
    AGENT_FORBIDDEN_COMMAND_RULES="$REPO_ROOT/agents/hooks/rules/forbidden_commands.json" \
    CLAUDE_PROJECT_DIR="$LOG_TMPDIR" run python3 -I -B "$HOOK_DIR/guard_commands.py" forbidden \
    <<<"$(jq -n '{tool_input:{command:"git commit --no-verify -m x"},session_id:"sess-e2e"}')"
  [ "$status" -eq 2 ]
  local entry
  entry=$(get_last_log)
  [[ $(echo "$entry" | jq -r '.event') == "Blocked" ]]
  [[ $(echo "$entry" | jq -r '.hook') == "guard_forbidden_commands.sh" ]]
  [[ $(echo "$entry" | jq -r '.session') == "sess-e2e" ]]
  [[ $(echo "$entry" | jq -r '.tool') == "Bash" ]]
}

@test "guard_dangerous_git.sh emits a Blocked row when it blocks" {
  CLAUDE_PROJECT_DIR="$LOG_TMPDIR" run python3 -I -B "$HOOK_DIR/guard_dangerous_git.py" \
    <<<"$(jq -n '{tool_input:{command:"git push --force origin main"},session_id:"sess-e2e"}')"
  [ "$status" -eq 2 ]
  local entry
  entry=$(get_last_log)
  [[ $(echo "$entry" | jq -r '.event') == "Blocked" ]]
  [[ $(echo "$entry" | jq -r '.hook') == "guard_dangerous_git.sh" ]]
  # First line of the BLOCKED stderr message is preserved as the reason.
  [[ $(echo "$entry" | jq -r '.reason') == BLOCKED:* ]]
}
