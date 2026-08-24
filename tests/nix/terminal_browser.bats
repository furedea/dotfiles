#!/usr/bin/env bats
# Executable specifications for the terminal-browser package.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "Home Manager installs terminal-browser version 0.6.0" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#homeConfigurations.kaito.config.home.packages" \
    --apply \
    'packages:
      map
        (package: package.version)
        (builtins.filter (package: (package.pname or "") == "terminal-browser") packages)'

  [ "$status" -eq 0 ]
  [ "$output" = '["0.6.0"]' ]
}
