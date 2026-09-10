#!/usr/bin/env bats
# Zsh restores the local agent only when no agent was inherited.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export REPO_ROOT
  export AGENT_SOCKET="$BATS_TEST_TMPDIR/Listeners"
  export DISCOVERY_LOG="$BATS_TEST_TMPDIR/discovery"
  mkdir -p "$BATS_TEST_TMPDIR/bin"
  export PATH="$BATS_TEST_TMPDIR/bin:$PATH"
  unset SSH_AUTH_SOCK
  /usr/bin/perl -MIO::Socket::UNIX -e 'IO::Socket::UNIX->new(Local => $ARGV[0], Listen => 1) or die $!' "$AGENT_SOCKET"
  cat >"$BATS_TEST_TMPDIR/bin/launchctl" <<'EOF'
#!/bin/sh
printf '%s\n' "$*" > "$DISCOVERY_LOG"
[ "${DISCOVERY_FAILED:-0}" = 0 ] || exit 1
printf 'path = %s\n' "$AGENT_SOCKET"
EOF
  chmod +x "$BATS_TEST_TMPDIR/bin/launchctl"
  export TEST_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$TEST_HOME/.config/zsh" "$TEST_HOME/ghq/github.com/furedea/dotfiles/zsh"
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

@test "noninteractive startup does not discover a local agent" {
  run zsh -dfc 'source "$REPO_ROOT/zsh/.zshenv"; print -r -- "${SSH_AUTH_SOCK:-unset}"'
  [ "$status" -eq 0 ]
  [ "$output" = unset ]
  [ ! -e "$DISCOVERY_LOG" ]
}

@test "startup restores the current user's local agent when none is inherited" {
  run_startup
  [ "$status" -eq 0 ]
  [ "$output" = "$AGENT_SOCKET" ]
  [ "$(cat "$DISCOVERY_LOG")" = "print gui/$(id -u)/com.openssh.ssh-agent" ]
}

@test "startup preserves an inherited or forwarded agent without discovery" {
  export SSH_AUTH_SOCK="$BATS_TEST_TMPDIR/forwarded-agent"
  run_startup
  [ "$status" -eq 0 ]
  [ "$output" = "$SSH_AUTH_SOCK" ]
  [ ! -e "$DISCOVERY_LOG" ]
}

@test "unavailable local agent does not disrupt startup" {
  export DISCOVERY_FAILED=1
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
