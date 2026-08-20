#!/usr/bin/env bats
# Executable specifications for the generated Homebrew bundle.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "Homebrew installs moshi-hook from a trusted tap" {
  run --separate-stderr nix eval --raw \
    "$REPO_ROOT#darwinConfigurations.mba.config.homebrew.brewfile"

  [ "$status" -eq 0 ]
  [[ "$output" == *'tap "rjyo/moshi", trusted: true'* ]]
  [[ "$output" == *'brew "rjyo/moshi/moshi-hook"'* ]]
}

@test "MacBook Pro starts moshi-hook through the Homebrew service" {
  run --separate-stderr nix eval --raw \
    "$REPO_ROOT#darwinConfigurations.mbp.config.homebrew.brewfile"

  [ "$status" -eq 0 ]
  [[ "$output" == *'brew "rjyo/moshi/moshi-hook", restart_service: :changed'* ]]
}

@test "MacBook Air does not start the moshi-hook service" {
  run --separate-stderr nix eval --raw \
    "$REPO_ROOT#darwinConfigurations.mba.config.homebrew.brewfile"

  [ "$status" -eq 0 ]
  [[ "$output" != *'brew "rjyo/moshi/moshi-hook", restart_service:'* ]]
}
