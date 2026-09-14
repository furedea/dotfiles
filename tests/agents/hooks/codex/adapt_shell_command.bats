#!/usr/bin/env bats
# Codex shell payloads reach shared enforcement without an intermediate command.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../.." && pwd)"
  HOOK="$REPO_ROOT/agents/codex/hooks/adapters.py"
}

@test "shell adapter requires a known policy mode" {
  run python3 -I -B "$HOOK" shell /tmp/arbitrary-hook
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "both Codex command fields preserve dangerous Git enforcement" {
  local _field _input
  for _field in command cmd; do
    _input="$(jq -n --arg field "$_field" '{tool_input:{($field):"git reset --hard"}}')"
    run python3 -I -B "$HOOK" shell git <<<"$_input"
    [ "$status" -eq 2 ]
    [[ "$output" == *"BLOCKED"* ]]
    [[ "$output" == *"git reset --hard"* ]]
  done
}

@test "safe Git command emits no shell trace" {
  run python3 -I -B "$HOOK" shell git <<<'{"tool_input":{"cmd":"git status"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
