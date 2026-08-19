#!/usr/bin/env bats
# Executable specifications for Zsh startup behavior.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TEST_HOME="$BATS_TEST_TMPDIR/home"
  TEST_BIN="$BATS_TEST_TMPDIR/bin"
  COMPINIT_LOG="$BATS_TEST_TMPDIR/compinit.log"
  ABBR_LOG="$BATS_TEST_TMPDIR/abbr.log"

  mkdir -p \
    "$TEST_HOME/.config/zsh" \
    "$TEST_HOME/ghq/github.com/furedea/dotfiles/zsh" \
    "$TEST_BIN" \
    "$BATS_TEST_TMPDIR/functions"

  cat >"$BATS_TEST_TMPDIR/functions/compinit" <<'EOF'
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

  export COMPINIT_LOG
  export ABBR_LOG
  export REPO_ROOT
  export TEST_BIN
  export TEST_HOME
}

@test "hl expands to the local main Herdr session" {
  run env \
    HOME="$TEST_HOME" \
    XDG_CACHE_HOME="$TEST_HOME/.cache" \
    FPATH="$BATS_TEST_TMPDIR/functions" \
    PATH="$TEST_BIN:$PATH" \
    zsh -dfi -c "source '$REPO_ROOT/zsh/.zshrc'"

  [ "$status" -eq 0 ]
  grep -Fx -- "--quiet -S hl=herdr --session main" "$ABBR_LOG"
}

@test "hr expands to the home Mac Herdr session" {
  run env \
    HOME="$TEST_HOME" \
    XDG_CACHE_HOME="$TEST_HOME/.cache" \
    FPATH="$BATS_TEST_TMPDIR/functions" \
    PATH="$TEST_BIN:$PATH" \
    zsh -dfi -c "source '$REPO_ROOT/zsh/.zshrc'"

  [ "$status" -eq 0 ]
  grep -Fx -- "--quiet -S hr=herdr --remote mbp --session main" "$ABBR_LOG"
}

@test "interactive startup loads only the prebuilt completion dump" {
  run env \
    HOME="$TEST_HOME" \
    XDG_CACHE_HOME="$TEST_HOME/.cache" \
    FPATH="$BATS_TEST_TMPDIR/functions" \
    PATH="$TEST_BIN:$PATH" \
    zsh -dfi -c "source '$REPO_ROOT/zsh/.zshrc'"

  [ "$status" -eq 0 ]
  [ "$(cat "$COMPINIT_LOG")" = "-C -d $TEST_HOME/.cache/zsh/.zcompdump" ]
}

@test "login startup skips Homebrew environment discovery" {
  run --separate-stderr env \
    HOME="$TEST_HOME" \
    PATH="$TEST_BIN:$PATH" \
    zsh -dfxc "source '$REPO_ROOT/zsh/.zprofile'"

  [ "$status" -eq 0 ]
  ! [[ "$stderr" == *"brew shellenv"* ]]
}

@test "system Zsh leaves completion initialization to the user configuration" {
  run --separate-stderr nix eval --json \
    "$REPO_ROOT#darwinConfigurations.mba.config.programs.zsh.enableGlobalCompInit"

  [ "$status" -eq 0 ]
  [ "$output" = "false" ]
}

@test "system Zsh skips unused Bash completion compatibility" {
  run --separate-stderr nix eval --json \
    "$REPO_ROOT#darwinConfigurations.mba.config.programs.zsh.enableBashCompletion"

  [ "$status" -eq 0 ]
  [ "$output" = "false" ]
}

@test "system Zsh leaves prompt initialization to Starship" {
  run --separate-stderr nix eval --json \
    "$REPO_ROOT#darwinConfigurations.mba.config.programs.zsh.promptInit"

  [ "$status" -eq 0 ]
  [ "$output" = '""' ]
}

@test "nix-homebrew leaves Zsh environment initialization disabled" {
  run --separate-stderr nix eval --json \
    "$REPO_ROOT#darwinConfigurations.mba.config.nix-homebrew.enableZshIntegration"

  [ "$status" -eq 0 ]
  [ "$output" = "false" ]
}

@test "Home Manager activation invokes the packaged Zsh cache builder" {
  run --separate-stderr nix build --no-link --print-out-paths \
    "$REPO_ROOT#homeConfigurations.kaito.activationPackage"

  if [ "$status" -ne 0 ]; then
    printf '%s\n' "$stderr" >&2
  fi
  [ "$status" -eq 0 ]

  local _activation_package="$output"
  [ -f "$_activation_package/activate" ]
  local _builder
  _builder="$(grep -Eo '/nix/store/[^"[:space:]]+-build_cache[.]sh' "$_activation_package/activate" | head -n 1)"
  [ -f "$_builder" ]
  cmp --silent "$REPO_ROOT/zsh/build_cache.sh" "$_builder"
}

@test "Home Manager builds Zsh caches after linking the new startup file" {
  run --separate-stderr nix eval --json \
    "$REPO_ROOT#homeConfigurations.kaito.config.home.activation.zshCache.after"

  [ "$status" -eq 0 ]
  [ "$output" = '["linkGeneration"]' ]
}
