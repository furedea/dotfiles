#!/usr/bin/env bats
# Interactive Zsh points SSH_AUTH_SOCK at the user's 1Password agent, never at another local agent.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export REPO_ROOT
  export TEST_HOME="$BATS_TEST_TMPDIR/home"
  export AGENT_DIR="$TEST_HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t"
  export AGENT_SOCKET="$AGENT_DIR/agent.sock"
  unset SSH_AUTH_SOCK SSH_CONNECTION
  mkdir -p "$AGENT_DIR" "$TEST_HOME/.config/zsh" "$TEST_HOME/ghq/github.com/furedea/dotfiles/zsh"
  # The full path exceeds the sockaddr_un limit, so bind by a relative name.
  /usr/bin/perl -MIO::Socket::UNIX -e 'chdir $ARGV[0] or die $!; IO::Socket::UNIX->new(Local => "agent.sock", Listen => 1) or die $!' "$AGENT_DIR"
  touch "$TEST_HOME/.config/zsh/nix-plugins.zsh"
  touch "$TEST_HOME/ghq/github.com/furedea/dotfiles/zsh/esa.zsh"
}

run_startup() {
  # Expand variables in the child Zsh, not in the Bats process.
  # shellcheck disable=SC2016
  run env HOME="$TEST_HOME" zsh -dfi -c '
    source "$REPO_ROOT/zsh/.zshenv"
    function autoload compinit carapace abbr atuin direnv starship zoxide() { :; }
    source "$REPO_ROOT/zsh/.zshrc"
    print -r -- "${SSH_AUTH_SOCK:-unset}"
  '
}

@test "noninteractive startup does not attach an agent" {
  run env HOME="$TEST_HOME" zsh -dfc 'source "$REPO_ROOT/zsh/.zshenv"; print -r -- "${SSH_AUTH_SOCK:-unset}"'
  [ "$status" -eq 0 ]
  [ "$output" = unset ]
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
