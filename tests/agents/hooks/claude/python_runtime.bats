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
    bash "$_prefix/.codex/hooks/adapt_shell_command.sh" \
    "$_prefix/.claude/hooks/guard_allowed_commands.sh" \
    <<<'{"tool_input":{"cmd":"git status"}}'
  [ "$status" -eq 0 ]

  run env AGENT_HARNESS_ROOT="$_prefix" CLAUDE_PROJECT_DIR="$BATS_TEST_TMPDIR" \
    bash "$_prefix/.codex/hooks/adapt_guard_secret_paths.sh" patch \
    <<<'{"tool_input":{"file_path":".env.local"}}'
  [ "$status" -eq 2 ]
  [[ "$output" == *"secret path policy matched"* ]]
}

@test "entry points prefer the Nix-managed interpreter over project PATH" {
  local _config="$BATS_TEST_TMPDIR/config"
  local _bin="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$_config/dotfiles/bin" "$_bin"
  cat >"$_config/dotfiles/bin/python3" <<'STUB'
#!/usr/bin/env bash
printf 'managed-python:%s\n' "$1"
STUB
  cat >"$_bin/python3" <<'STUB'
#!/usr/bin/env bash
exit 99
STUB
  chmod +x "$_config/dotfiles/bin/python3" "$_bin/python3"

  run env XDG_CONFIG_HOME="$_config" PATH="$_bin:$PATH" \
    bash "$REPO_ROOT/github/create_repo.sh" --help
  [ "$status" -eq 0 ]
  [ "$output" = 'managed-python:-I' ]
}
