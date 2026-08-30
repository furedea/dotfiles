#!/usr/bin/env bats
# Executable specifications for Home Manager package selection.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOME_CONFIG="homeConfigurations.kaito.config"
}

@test "Home Manager does not install Marp" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$HOME_CONFIG.home.packages" \
    --apply \
    'packages:
      builtins.any
        (package:
          builtins.elem
            (package.pname or package.name)
            [ "marp" "marp-cli" ])
        packages'

  [ "$status" -eq 0 ]
  [ "$output" = 'false' ]
}
