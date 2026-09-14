#!/usr/bin/env bats
# All configured language modes share one Python command.

setup() {
  load test-helper/setup
}

@test "every configured language accepts an event without a file" {
  local _kind
  for _kind in gha js json_toml lua md nix py rs sh tex txt; do
    run python3 -I -B "$HOOK_DIR/lint_format.py" "$_kind" <<<'{"tool_input":{}}'
    [ "$status" -eq 0 ]
    [ -z "$output" ]
  done
}

@test "quality entry point rejects a missing mode" {
  run python3 -I -B "$HOOK_DIR/lint_format.py"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "quality entry point rejects malformed JSON" {
  run python3 -I -B "$HOOK_DIR/lint_format.py" py <<<'{'
  [ "$status" -eq 1 ]
}
