#!/usr/bin/env bats
# Tests for .claude/hooks/block_no_verify.sh

setup() {
  load test_helper/setup
}

# --- Blocked cases ---

@test "blocks --no-verify flag" {
  run bash "$HOOK_DIR/block_no_verify.sh" <<< "$(make_input 'git commit --no-verify -m test')"
  [ "$status" -eq 2 ]
  [[ "$output" == *"BLOCKED"* ]]
}

@test "blocks --no-verify at the end" {
  run bash "$HOOK_DIR/block_no_verify.sh" <<< "$(make_input 'git commit -m test --no-verify')"
  [ "$status" -eq 2 ]
}

@test "blocks -n short flag" {
  run bash "$HOOK_DIR/block_no_verify.sh" <<< "$(make_input 'git commit -n -m test')"
  [ "$status" -eq 2 ]
}

@test "blocks with extra whitespace" {
  run bash "$HOOK_DIR/block_no_verify.sh" <<< "$(make_input 'git   commit   --no-verify')"
  [ "$status" -eq 2 ]
}

# --- Allowed cases ---

@test "allows normal git commit" {
  run bash "$HOOK_DIR/block_no_verify.sh" <<< "$(make_input 'git commit -m "hello world"')"
  [ "$status" -eq 0 ]
}

@test "allows git commit with --amend" {
  run bash "$HOOK_DIR/block_no_verify.sh" <<< "$(make_input 'git commit --amend -m fix')"
  [ "$status" -eq 0 ]
}

@test "passes through non-git commands" {
  run bash "$HOOK_DIR/block_no_verify.sh" <<< "$(make_input 'echo hello')"
  [ "$status" -eq 0 ]
}

@test "passes through empty command" {
  run bash "$HOOK_DIR/block_no_verify.sh" <<< '{"tool_input":{"command":""}}'
  [ "$status" -eq 0 ]
}
