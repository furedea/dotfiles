#!/usr/bin/env bats
# The hook's Bats entry point delegates declarative contracts to native flake checks.

bats_require_minimum_version 1.5.0

@test "Home Manager and host configuration satisfy native Nix contracts" {
  local _repo_root
  _repo_root="${DOTFILES_TEST_FLAKE:-$(cd "$BATS_TEST_DIRNAME/../.." && pwd)}"

  run --separate-stderr nix build --no-link --print-out-paths \
    "$_repo_root#checks.aarch64-darwin.home-configuration" \
    "$_repo_root#checks.aarch64-darwin.host-configuration"

  if [ "$status" -ne 0 ]; then
    printf '%s\n' "$stderr" >&2
  fi
  [ "$status" -eq 0 ]
  [ "${#lines[@]}" -eq 2 ]
}
