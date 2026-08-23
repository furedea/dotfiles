#!/usr/bin/env bats
# Executable specifications for reproducible Neovim plugin loading.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LOCK_FILE="$REPO_ROOT/nvim/lazy-lock.json"
}

@test "Neovim loads lazy.nvim from the Nix-managed runtime" {
  run rg --fixed-strings 'https://github.com/folke/lazy.nvim.git' \
    "$REPO_ROOT/nvim/init.lua"

  [ "$status" -eq 1 ]

  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#homeConfigurations.kaito.config.programs.neovim.plugins" \
    --apply 'plugins: map (plugin: plugin.pname or plugin.name) plugins'

  [ "$status" -eq 0 ]
  [ "$output" = '["lazy.nvim"]' ]
}

@test "Neovim plugin revisions are recorded in version control" {
  [ -f "$LOCK_FILE" ]

  run git -C "$REPO_ROOT" check-ignore nvim/lazy-lock.json

  [ "$status" -eq 1 ]

  run jq -e '
    length > 0
    and all(.[]; .commit | test("^[0-9a-f]{40}$"))
    and (has("lazy.nvim") | not)
  ' "$LOCK_FILE"

  [ "$status" -eq 0 ]
}
