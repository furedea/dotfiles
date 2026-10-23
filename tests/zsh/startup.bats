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

@test "agent startup keeps cd as the shell builtin when either agent variable is set" {
  local _agent _value
  for _agent in CLAUDECODE AI_AGENT; do
    for _value in 1 ''; do
      run --separate-stderr env -u CLAUDECODE -u AI_AGENT \
        "$_agent=$_value" \
        HOME="$TEST_HOME" \
        XDG_CACHE_HOME="$TEST_HOME/.cache" \
        FPATH="$BATS_TEST_TMPDIR/functions" \
        PATH="$TEST_BIN:$PATH" \
        zsh -dfi -c "source '$REPO_ROOT/zsh/.zshenv'; source '$REPO_ROOT/zsh/.zshrc'; whence -w cd"

      [ "$status" -eq 0 ]
      [ "$output" = "cd: builtin" ] || {
        printf 'unexpected cd resolution with %s=%s: %s\n' "$_agent" "$_value" "$output" >&2
        return 1
      }
    done
  done
}

@test "human startup aliases cd to j when neither agent variable is set" {
  run --separate-stderr env -u CLAUDECODE -u AI_AGENT \
    HOME="$TEST_HOME" \
    XDG_CACHE_HOME="$TEST_HOME/.cache" \
    FPATH="$BATS_TEST_TMPDIR/functions" \
    PATH="$TEST_BIN:$PATH" \
    zsh -dfi -c "source '$REPO_ROOT/zsh/.zshenv'; source '$REPO_ROOT/zsh/.zshrc'; alias cd"

  [ "$status" -eq 0 ]
  [ "$output" = "cd=j" ]
}

@test "hl expands to the local main Herdr session" {
  run env \
    HOME="$TEST_HOME" \
    XDG_CACHE_HOME="$TEST_HOME/.cache" \
    FPATH="$BATS_TEST_TMPDIR/functions" \
    PATH="$TEST_BIN:$PATH" \
    zsh -dfi -c "source '$REPO_ROOT/zsh/.zshenv'; source '$REPO_ROOT/zsh/.zshrc'"

  [ "$status" -eq 0 ]
  grep -Fx -- "--quiet -S hl=herdr --session main" "$ABBR_LOG"
}

@test "hr expands to the home Mac Herdr session" {
  run env \
    HOME="$TEST_HOME" \
    XDG_CACHE_HOME="$TEST_HOME/.cache" \
    FPATH="$BATS_TEST_TMPDIR/functions" \
    PATH="$TEST_BIN:$PATH" \
    zsh -dfi -c "source '$REPO_ROOT/zsh/.zshenv'; source '$REPO_ROOT/zsh/.zshrc'"

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
    zsh -dfi -c "source '$REPO_ROOT/zsh/.zshenv'; source '$REPO_ROOT/zsh/.zshrc'"

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

@test "clean login startup orders Nix profiles and fallback tools before system entries" {
  local _user_profile="$TEST_HOME/.nix-profile/bin"
  local _per_user_profile="/etc/profiles/per-user/startup-test/bin"
  local _system_profile="/run/current-system/sw/bin"
  local _default_profile="/nix/var/nix/profiles/default/bin"

  run_startup_path "$_user_profile:$_per_user_profile:$_system_profile:$_default_profile:/usr/bin:$TEST_BIN:/bin" -lic

  [ "$status" -eq 0 ]
  local _expected=(
    "$_user_profile"
    "$_per_user_profile"
    "$_system_profile"
    "$_default_profile"
    "$TEST_HOME/.local/bin"
    "$TEST_HOME/.cargo/bin"
    "$TEST_HOME/.gem/bin"
    /opt/homebrew/bin
    /Library/TeX/texbin
    /usr/bin
    "$TEST_BIN"
    /bin
    /Applications/Obsidian.app/Contents/MacOS
  )
  [ "${#lines[@]}" -eq "${#_expected[@]}" ]
  local _index
  for _index in "${!_expected[@]}"; do
    [ "${lines[_index]}" = "${_expected[_index]}" ] || {
      printf 'unexpected PATH entry at %s: %s\n' "$_index" "$output" >&2
      return 1
    }
  done
}

@test "startup preserves inherited devShell PATH order in all shell modes" {
  local _inherited="/nix/store/devshell-tools/bin:/workspace/project/bin:$TEST_HOME/.cargo/bin:/opt/homebrew/bin:$TEST_HOME/.nix-profile/bin:/usr/bin:$TEST_HOME/.local/bin:/Library/TeX/texbin:$TEST_BIN:/bin"
  local _mode
  for _mode in -c -ic -lic; do
    run_startup_path "$_inherited:$_inherited" "$_mode"

    [ "$status" -eq 0 ]
    local _expected=(
      /nix/store/devshell-tools/bin
      /workspace/project/bin
      "$TEST_HOME/.cargo/bin"
      /opt/homebrew/bin
      "$TEST_HOME/.nix-profile/bin"
      "$TEST_HOME/.gem/bin"
      /usr/bin
      "$TEST_HOME/.local/bin"
      /Library/TeX/texbin
      "$TEST_BIN"
      /bin
    )
    if [ "$_mode" = -lic ]; then
      _expected+=(/Applications/Obsidian.app/Contents/MacOS)
    fi
    [ "${#lines[@]}" -eq "${#_expected[@]}" ]
    local _index
    for _index in "${!_expected[@]}"; do
      [ "${lines[_index]}" = "${_expected[_index]}" ] || {
        printf 'unexpected PATH entry in %s at %s: %s\n' "$_mode" "$_index" "$output" >&2
        return 1
      }
    done
  done
}

@test "startup inserts missing fallback tools after inherited devShell entries in all shell modes" {
  local _inherited="/nix/store/devshell-tools/bin:/workspace/project/bin:$TEST_BIN"
  local _mode
  for _mode in -c -ic -lic; do
    run_startup_path "$_inherited:/usr/bin:/bin" "$_mode"

    [ "$status" -eq 0 ]
    local _expected=(
      /nix/store/devshell-tools/bin
      /workspace/project/bin
      "$TEST_BIN"
      "$TEST_HOME/.local/bin"
      "$TEST_HOME/.cargo/bin"
      "$TEST_HOME/.gem/bin"
    )
    if [ "$_mode" != -c ]; then
      _expected+=(/opt/homebrew/bin /Library/TeX/texbin)
    fi
    _expected+=(/usr/bin /bin)
    if [ "$_mode" = -lic ]; then
      _expected+=(/Applications/Obsidian.app/Contents/MacOS)
    fi
    [ "$output" = "$(printf '%s\n' "${_expected[@]}")" ] || {
      printf 'unexpected PATH in %s: %s\n' "$_mode" "$output" >&2
      return 1
    }
  done
}

@test "startup inserts before the first system entry or appends when none exists" {
  local _system
  for _system in /usr/local/bin /usr/bin /bin /usr/sbin /sbin ''; do
    local _inherited="$TEST_BIN"
    local _expected=(
      "$TEST_BIN"
      "$TEST_HOME/.local/bin"
      "$TEST_HOME/.cargo/bin"
      "$TEST_HOME/.gem/bin"
    )
    if [ -n "$_system" ]; then
      _inherited+=":$_system:/custom/bin:/usr/bin"
      _expected+=("$_system" /custom/bin)
      if [ "$_system" != /usr/bin ]; then
        _expected+=(/usr/bin)
      fi
    fi
    run_startup_path "$_inherited" -c

    [ "$status" -eq 0 ]
    [ "$output" = "$(printf '%s\n' "${_expected[@]}")" ] || {
      printf 'unexpected PATH for system entry %s: %s\n' "$_system" "$output" >&2
      return 1
    }
  done
}

run_startup_path() {
  # Source repository files explicitly to isolate host startup configuration.
  run --separate-stderr env -i \
    HOME="$TEST_HOME" \
    USER=startup-test \
    XDG_CACHE_HOME="$TEST_HOME/.cache" \
    FPATH="$BATS_TEST_TMPDIR/functions" \
    COMPINIT_LOG="$COMPINIT_LOG" \
    ABBR_LOG="$ABBR_LOG" \
    REPO_ROOT="$REPO_ROOT" \
    PATH="$1" \
    "$(command -v zsh)" -df "$2" '
      source "$REPO_ROOT/zsh/.zshenv"
      source "$REPO_ROOT/zsh/.zshenv"
      if [[ -o login ]]; then
        source "$REPO_ROOT/zsh/.zprofile"
      fi
      if [[ -o interactive ]]; then
        source "$REPO_ROOT/zsh/.zshrc"
      fi
      print -rl -- "${path[@]}"
    '
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
