#!/usr/bin/env bats
# Tests for Herdr Home Manager activation.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "propagates Herdr plugin synchronization failures" {
  run nix eval --raw \
    "$REPO_ROOT#homeConfigurations.kaito.config.home.activation.herdrPlugins.data"

  [ "$status" -eq 0 ]
  ! [[ "$output" == *"|| true"* ]]
}

@test "provides plugin installer commands during activation" {
  run nix eval --raw \
    "$REPO_ROOT#homeConfigurations.kaito.config.home.activation.herdrPlugins.data"

  [ "$status" -eq 0 ]
  [[ "$output" == *'-git-'*'/bin:/usr/bin:/bin'* ]]
}
