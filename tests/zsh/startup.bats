#!/usr/bin/env bats
# Executable specifications for Zsh startup behavior.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TEST_FLAKE="${DOTFILES_TEST_FLAKE:-$REPO_ROOT}"
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
  grep -Fx -- \
    "--quiet -S hr=herdr --remote mbp --session main --remote-keybindings server" \
    "$ABBR_LOG"
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

@test "startup preserves Nix command precedence without duplicate PATH entries" {
  local _user_profile="$TEST_HOME/.nix-profile/bin"
  local _per_user_profile="$BATS_TEST_TMPDIR/profiles/per-user/bin"
  local _system_profile="$BATS_TEST_TMPDIR/current-system/sw/bin"
  mkdir -p "$_user_profile" "$_per_user_profile" "$_system_profile" "$TEST_HOME/.local/bin"
  touch "$_user_profile/git" "$TEST_HOME/.local/bin/git"
  chmod +x "$_user_profile/git" "$TEST_HOME/.local/bin/git"

  local _mode
  for _mode in -dfc -dfic -dflic; do
    # Source repository files explicitly to isolate host startup configuration.
    run --separate-stderr env -i \
      HOME="$TEST_HOME" \
      XDG_CACHE_HOME="$TEST_HOME/.cache" \
      FPATH="$BATS_TEST_TMPDIR/functions" \
      COMPINIT_LOG="$COMPINIT_LOG" \
      ABBR_LOG="$ABBR_LOG" \
      REPO_ROOT="$REPO_ROOT" \
      PATH="$_user_profile:$_per_user_profile:$_system_profile:$TEST_BIN:/usr/bin:/bin:/opt/homebrew/bin:/usr/bin:$_user_profile" \
      "$(command -v zsh)" "$_mode" '
        source "$REPO_ROOT/zsh/.zshenv"
        if [[ -o login ]]; then
          source "$REPO_ROOT/zsh/.zprofile"
        fi
        if [[ -o interactive ]]; then
          source "$REPO_ROOT/zsh/.zshrc"
        fi
        print -r -- "$(command -v git)"
        print -rl -- "${path[@]}"
      '

    [ "$status" -eq 0 ]
    [ "${lines[0]}" = "$_user_profile/git" ]
    [ "${lines[1]}" = "$_user_profile" ]
    [ "${lines[2]}" = "$_per_user_profile" ]
    [ "${lines[3]}" = "$_system_profile" ]
    [ "$(printf '%s\n' "${lines[@]:1}" | sort | uniq -d)" = "" ] || {
      printf 'duplicate PATH entries in %s: %s\n' "$_mode" "$output" >&2
      return 1
    }
    [[ "$output" == *"/usr/bin"* ]]
    [[ "$output" == *"/opt/homebrew/bin"* ]]
    if [[ "$_mode" == *i* ]]; then
      [[ "$output" == *"/Library/TeX/texbin"* ]]
    fi
  done
}

@test "Home Manager activation invokes the packaged Zsh cache builder" {
  run --separate-stderr nix build --no-link --print-out-paths \
    "$TEST_FLAKE#homeConfigurations.\"kaito@mbp\".activationPackage"

  if [ "$status" -ne 0 ]; then
    printf '%s\n' "$stderr" >&2
  fi
  [ "$status" -eq 0 ]

  local _activation_package="$output"
  [ -f "$_activation_package/activate" ]
  local _builder
  _builder="$(grep -Eo '/nix/store/[^"[:space:]]+-build_cache[.]zsh' "$_activation_package/activate" | head -n 1)"
  [ -f "$_builder" ]
  cmp --silent "$REPO_ROOT/zsh/build_cache.zsh" "$_builder"
}
