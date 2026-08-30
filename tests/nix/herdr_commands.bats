#!/usr/bin/env bats
# Executable specifications for Nix-managed Herdr command helpers.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  PRIMARY_DOTFILES="$(dirname "$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir)")"
  HOME_CONFIG="homeConfigurations.kaito.config"
}

@test "Home Manager links the editable Herdr pull-request merge helper" {
  run --separate-stderr nix build --no-link --print-out-paths \
    "$REPO_ROOT#$HOME_CONFIG.home.file.\".local/libexec/herdr_merge_pull_request.sh\".source"

  [ "$status" -eq 0 ]
  run readlink "$output"
  [ "$status" -eq 0 ]
  [ "$output" = "$PRIMARY_DOTFILES/herdr/merge_pull_request.sh" ]
}

@test "Home Manager builds with the out-of-store Herdr pull-request merge helper" {
  run --separate-stderr nix build --no-link --print-out-paths \
    "$REPO_ROOT#homeConfigurations.kaito.activationPackage"

  if [ "$status" -ne 0 ]; then
    printf '%s\n' "$stderr" >&2
  fi
  [ "$status" -eq 0 ]
}
