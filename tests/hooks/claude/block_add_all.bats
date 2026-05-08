#!/usr/bin/env bats
# Tests for .claude/hooks/block_add_all.sh

setup() {
  load test_helper/setup
}

# --- Blocked cases ---

@test "blocks git add ." {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'git add .')"
  [ "$status" -eq 2 ]
  [[ "$output" == *"BLOCKED"* ]]
}

@test "blocks git add -A" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'git add -A')"
  [ "$status" -eq 2 ]
}

@test "blocks git add --all" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'git add --all')"
  [ "$status" -eq 2 ]
}

@test "blocks git add . at end of pipeline" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'ls && git add .')"
  [ "$status" -eq 2 ]
}

@test "blocks git add -A after pipe" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'echo ok | xargs -I {} git add -A')"
  [ "$status" -eq 2 ]
}

@test "blocks with extra whitespace" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'git   add   .')"
  [ "$status" -eq 2 ]
}

@test "blocks git add --all with trailing flag" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'git add --all --verbose')"
  [ "$status" -eq 2 ]
}

# --- Allowed cases ---

@test "allows git add <file>" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'git add bot/main.py')"
  [ "$status" -eq 0 ]
}

@test "allows git add multiple files" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'git add bot/main.py tests/bot/test_main.py')"
  [ "$status" -eq 0 ]
}

@test "allows git add ./path (relative)" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'git add ./bot/main.py')"
  [ "$status" -eq 0 ]
}

@test "allows filename starting with letter 'a' (not --all)" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'git add allocator.py')"
  [ "$status" -eq 0 ]
}

@test "allows filename containing 'all'" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'git add ball.txt')"
  [ "$status" -eq 0 ]
}

@test "allows git add -- <file>" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'git add -- path/to/file')"
  [ "$status" -eq 0 ]
}

@test "passes through non-git commands" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input 'echo hello')"
  [ "$status" -eq 0 ]
}

@test "passes through git commit commands" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< "$(make_input "git commit -m 'msg'")"
  [ "$status" -eq 0 ]
}

@test "passes through empty command" {
  run bash "$HOOK_DIR/block_add_all.sh" <<< '{"tool_input":{"command":""}}'
  [ "$status" -eq 0 ]
}
