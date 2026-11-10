# Shared fixtures for the Zsh SSH agent specs.

setup_agent_environment() {
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
