#!/usr/bin/env bats
# Executable specifications for tools intentionally absent from Home Manager.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOME_CONFIG="homeConfigurations.kaito.config"
}

@test "Home Manager omits retired presentation packages" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$HOME_CONFIG.home.packages" \
    --apply \
    'packages:
      builtins.filter
        (name: builtins.elem name [ "marp" "marp-cli" ])
        (map (package: package.pname or package.name) packages)'

  [ "$status" -eq 0 ]
  [ "$output" = '[]' ]
}

@test "The retired Marp skill files are absent" {
  [ ! -f "$REPO_ROOT/agents/skills/marp-style/SKILL.md" ]
  [ ! -f "$REPO_ROOT/agents/skills/marp-style/assets/base.css" ]
}
