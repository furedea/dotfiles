# Shared startup fixture for Zsh tests.

function setup_zsh_test_environment() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TEST_ROOT="$(cd "$BATS_TEST_TMPDIR" && pwd -P)"
  TEST_HOME="$TEST_ROOT/home"
  TEST_BIN="$TEST_ROOT/bin"
  TEST_FUNCTIONS="$TEST_ROOT/functions"
  COMPINIT_LOG="$TEST_ROOT/compinit.log"
  ABBR_LOG="$TEST_ROOT/abbr.log"

  create_zsh_startup_stubs

  export ABBR_LOG
  export COMPINIT_LOG
  export REPO_ROOT
  export TEST_BIN
  export TEST_FUNCTIONS
  export TEST_HOME
}

function create_zsh_startup_stubs() {
  mkdir -p \
    "$TEST_HOME/.config/zsh" \
    "$TEST_HOME/ghq/github.com/furedea/dotfiles/zsh" \
    "$TEST_BIN" \
    "$TEST_FUNCTIONS"

  cat >"$TEST_FUNCTIONS/compinit" <<'EOF'
print -r -- "$*" >>"$COMPINIT_LOG"
EOF
  cat >"$TEST_HOME/.config/zsh/nix-plugins.zsh" <<'EOF'
function abbr() { print -r -- "$*" >>"$ABBR_LOG"; }
EOF
  : >"$TEST_HOME/ghq/github.com/furedea/dotfiles/zsh/esa.zsh"

  local _command
  for _command in atuin carapace direnv starship zoxide; do
    cat >"$TEST_BIN/$_command" <<'EOF'
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"
set +x
EOF
    chmod +x "$TEST_BIN/$_command"
  done
}
