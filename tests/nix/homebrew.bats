#!/usr/bin/env bats
# Executable specifications for the generated Homebrew bundle.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "Homebrew does not install or trust moshi-hook" {
  run --separate-stderr nix eval --raw \
    "$REPO_ROOT#darwinConfigurations.mba.config.homebrew.brewfile"

  [ "$status" -eq 0 ]
  [[ "$output" != *'moshi-hook'* ]]
  [[ "$output" != *'rjyo/moshi'* ]]
}

@test "Homebrew cleanup runs without an interactive confirmation" {
  run --separate-stderr nix eval --json \
    "$REPO_ROOT#darwinConfigurations.mbp.config.homebrew.onActivation.extraFlags"

  [ "$status" -eq 0 ]
  [ "$output" = '["--force"]' ]
}
