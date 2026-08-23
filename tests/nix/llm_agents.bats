#!/usr/bin/env bats
# Executable specifications for Nix-managed AI coding agent packages.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "AI coding agents use the shared llm-agents input" {
  run --separate-stderr nix flake metadata --no-write-lock-file --json "$REPO_ROOT"

  [ "$status" -eq 0 ]
  run jq -ce '
    .locks.nodes.root.inputs
    | has("llm-agents")
      and (has("nix-claude-code") | not)
      and (has("codex-cli-nix") | not)
      and (has("herdr") | not)
  ' <<<"$output"

  [ "$status" -eq 0 ]
  [ "$output" = "true" ]
}

@test "Home Manager selects only Claude Code, Codex, and Herdr from llm-agents" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#homeConfigurations.kaito.config.home.packages" \
    --apply \
    'packages:
      builtins.filter
        (name: builtins.elem name [ "claude-code" "codex" "herdr" ])
        (map (package: package.pname or package.name) packages)'

  [ "$status" -eq 0 ]
  [ "$output" = '["herdr","claude-code","codex"]' ]
}
