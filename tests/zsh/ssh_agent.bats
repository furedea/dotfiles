#!/usr/bin/env bats
# Interactive Zsh points SSH_AUTH_SOCK at the user's 1Password agent, never at another local agent.

setup() {
  load test-helper/ssh_agent
  setup_agent_environment
}

@test "noninteractive startup does not attach an agent" {
  run env HOME="$TEST_HOME" zsh -dfc 'source "$REPO_ROOT/zsh/.zshenv"; print -r -- "${SSH_AUTH_SOCK:-unset}"'
  [ "$status" -eq 0 ]
  [ "$output" = unset ]
}

@test "startup preserves an agent forwarded into a remote session" {
  export SSH_CONNECTION="192.0.2.1 50000 192.0.2.2 22"
  export SSH_AUTH_SOCK="$BATS_TEST_TMPDIR/forwarded-agent"
  run_startup
  [ "$status" -eq 0 ]
  [ "$output" = "$SSH_AUTH_SOCK" ]
}

@test "startup keeps the inherited agent when 1Password is unavailable" {
  rm "$AGENT_SOCKET"
  export SSH_AUTH_SOCK="$BATS_TEST_TMPDIR/inherited-agent"
  run_startup
  [ "$status" -eq 0 ]
  [ "$output" = "$SSH_AUTH_SOCK" ]
}

@test "startup leaves no agent set when 1Password is unavailable" {
  rm "$AGENT_SOCKET"
  run_startup
  [ "$status" -eq 0 ]
  [ "$output" = unset ]
}

@test "startup refuses a regular file in place of the agent socket" {
  rm "$AGENT_SOCKET"
  touch "$AGENT_SOCKET"
  run_startup
  [ "$status" -eq 0 ]
  [ "$output" = unset ]
}

@test "startup refuses a symlink in place of the agent socket" {
  mv "$AGENT_SOCKET" "$BATS_TEST_TMPDIR/real-socket"
  ln -s "$BATS_TEST_TMPDIR/real-socket" "$AGENT_SOCKET"
  run_startup
  [ "$status" -eq 0 ]
  [ "$output" = unset ]
}
