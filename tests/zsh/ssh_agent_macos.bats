#!/usr/bin/env bats
# Interactive Zsh attaches the user's 1Password agent.
# macOS only: zsh/.zshrc attaches the 1Password agent only when OSTYPE is darwin.
# bats file_tags=macos

setup() {
  load test-helper/ssh_agent
  setup_agent_environment
}

@test "startup attaches the 1Password agent when none is inherited" {
  run_startup
  [ "$status" -eq 0 ]
  [ "$output" = "$AGENT_SOCKET" ]
}

@test "startup replaces the login session's local agent with 1Password" {
  export SSH_AUTH_SOCK="$BATS_TEST_TMPDIR/apple-agent"
  run_startup
  [ "$status" -eq 0 ]
  [ "$output" = "$AGENT_SOCKET" ]
}
