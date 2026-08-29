#!/usr/bin/env bats
# Executable specifications for Home Manager's Herdr plugin activation.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "Home Manager propagates Herdr plugin synchronization failures" {
  run --separate-stderr nix eval --raw \
    "$REPO_ROOT#homeConfigurations.kaito.config.home.activation.herdrPlugins.data"

  [ "$status" -eq 0 ]
  [[ "$output" == *"sync_herdr_plugins.sh"* ]]
  [[ "$output" != *"|| true"* ]]
}

@test "Home Manager gives Herdr plugin builds a deterministic executable path" {
  run --separate-stderr nix eval --raw \
    "$REPO_ROOT#homeConfigurations.kaito.config.home.activation.herdrPlugins.data"

  [ "$status" -eq 0 ]
  [[ "$output" == *'PATH="'* ]]
  [[ "$output" == *'/bin:/usr/bin:/bin"'* ]]
}
