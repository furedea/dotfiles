#!/usr/bin/env bats
# Executable specifications for GitHub CLI extensions.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "GitHub CLI provides the official stacked pull request extension" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#homeConfigurations.kaito.config.programs.gh.extensions" \
    --apply 'extensions: map (extension: extension.pname or extension.name) extensions'

  [ "$status" -eq 0 ]
  [ "$output" = '["gh-stack"]' ]
}
