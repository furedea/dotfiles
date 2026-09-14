#!/usr/bin/env bats
# The installed layout must carry every standard-library automation module.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
}

@test "rendered Claude and Codex entry points load adjacent Python modules" {
  local _prefix="$BATS_TEST_TMPDIR/rendered"
  agent-harness --profile minimal install --source "$REPO_ROOT/agents" \
    --prefix "$_prefix" --runtime-root "$_prefix"

  [ -f "$_prefix/.claude/hooks/guard_commands.py" ]
  [ -f "$_prefix/.claude/hooks/lib/shell_syntax.py" ]
  [ -f "$_prefix/.codex/hooks/adapters.py" ]
  [ -f "$_prefix/.claude/statusline/statusline.py" ]

  run env AGENT_HARNESS_ROOT="$_prefix" CLAUDE_PROJECT_DIR="$BATS_TEST_TMPDIR" \
    "$_prefix/.codex/hooks/adapters.py" shell allowed \
    <<<'{"tool_input":{"cmd":"git status"}}'
  [ "$status" -eq 0 ]

  run env AGENT_HARNESS_ROOT="$_prefix" CLAUDE_PROJECT_DIR="$BATS_TEST_TMPDIR" \
    "$_prefix/.codex/hooks/adapters.py" paths patch \
    <<<'{"tool_input":{"file_path":".env.local"}}'
  [ "$status" -eq 2 ]
  [[ "$output" == *"secret path policy matched"* ]]
}

@test "direct Python entry point ignores project and user module injection" {
  local _project="$BATS_TEST_TMPDIR/project"
  mkdir -p "$_project"
  printf 'raise RuntimeError("untrusted json module")\n' >"$_project/json.py"
  printf 'raise RuntimeError("untrusted user site")\n' >"$_project/sitecustomize.py"
  cd "$_project"

  run env PYTHONPATH="$_project" "$REPO_ROOT/github/repo.py" create --help
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
  [[ "$output" != *"untrusted"* ]]
}
