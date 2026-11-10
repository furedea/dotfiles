#!/usr/bin/env bats
# Executable specifications for Zsh startup behavior that needs the darwin Home Manager build.
# macOS only: builds the aarch64-darwin Home Manager activation package, which needs a macOS host or builder.
# bats file_tags=macos

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TEST_FLAKE="${DOTFILES_TEST_FLAKE:-$REPO_ROOT}"
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
