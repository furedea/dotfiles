#!/usr/bin/env bats
# Executable specifications for the generated Homebrew bundle.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "Homebrew installs moshi-hook" {
  run --separate-stderr nix eval --raw \
    "$REPO_ROOT#darwinConfigurations.mba.config.homebrew.brewfile"

  [ "$status" -eq 0 ]
  [[ "$output" == *'brew "rjyo/moshi/moshi-hook"'* ]]
}

@test "Homebrew trusts only the moshi-hook formula from the Moshi tap" {
  run --separate-stderr nix eval --raw \
    "$REPO_ROOT#darwinConfigurations.mba.config.homebrew.brewfile"

  [ "$status" -eq 0 ]
  [[ "$output" == *'tap "rjyo/moshi", trusted: { formula: "moshi-hook" }'* ]]
  [[ "$output" != *'tap "rjyo/moshi", trusted: true'* ]]
}

@test "Homebrew cleanup runs without an interactive confirmation" {
  run --separate-stderr nix eval --json \
    "$REPO_ROOT#darwinConfigurations.mbp.config.homebrew.onActivation.extraFlags"

  [ "$status" -eq 0 ]
  [ "$output" = '["--force"]' ]
}

@test "Homebrew does not own the MacBook Pro moshi-hook service" {
  run --separate-stderr nix eval --raw \
    "$REPO_ROOT#darwinConfigurations.mbp.config.homebrew.brewfile"

  [ "$status" -eq 0 ]
  [[ "$output" != *'brew "rjyo/moshi/moshi-hook", restart_service:'* ]]
}

@test "MacBook Air does not start the moshi-hook service" {
  run --separate-stderr nix eval --raw \
    "$REPO_ROOT#darwinConfigurations.mba.config.homebrew.brewfile"

  [ "$status" -eq 0 ]
  [[ "$output" != *'brew "rjyo/moshi/moshi-hook", restart_service:'* ]]
}
