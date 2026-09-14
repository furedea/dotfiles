#!/usr/bin/env bats
# Exercise the actual shared scanner with an isolated, non-secret test pattern.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../.." && pwd)"
  HOOK="$REPO_ROOT/agents/codex/hooks/adapters.py"
  local _rules="$BATS_TEST_TMPDIR/harness/.claude/hooks/rules"
  mkdir -p "$_rules"
  printf '%s\n' '{"fixture":{"pattern":"fixture-sensitive-marker","message":"Fixture detected"}}' \
    >"$_rules/secret_content_patterns.json"
  export AGENT_HARNESS_ROOT="$BATS_TEST_TMPDIR/harness"
}

@test "content adapter requires a mode" {
  run python3 -I -B "$HOOK" content
  [ "$status" -eq 1 ]
}

@test "prompt scanner loads policy from the harness root" {
  run env HOME="$BATS_TEST_TMPDIR/other-home" python3 -I -B "$HOOK" content prompt \
    <<<'{"prompt":"fixture-sensitive-marker"}'
  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision": "block"'* ]]
  [[ "$output" == *"Fixture detected"* ]]
}

@test "safe prompt produces no shell trace or decision" {
  run python3 -I -B "$HOOK" content prompt <<<'{"prompt":"hello"}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "patch additions use the write decision format" {
  run python3 -I -B "$HOOK" content apply-patch \
    <<<'{"tool_input":{"command":"*** Update File: file.txt\n@@\n+fixture-sensitive-marker"}}'
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision": "deny"'* ]]
}

@test "removed patch content is not treated as a new secret" {
  run python3 -I -B "$HOOK" content apply-patch \
    <<<'{"tool_input":{"command":"*** Update File: file.txt\n@@\n-fixture-sensitive-marker\n+safe"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
