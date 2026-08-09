#!/usr/bin/env bats
# Tests for the evaluated Home Manager configuration.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "disables tmux in the Home Manager configuration" {
  run nix eval --json "$REPO_ROOT#homeConfigurations.kaito.config.programs.tmux.enable"

  [ "$status" -eq 0 ]
  [ "${lines[${#lines[@]} - 1]}" = "false" ]
}
