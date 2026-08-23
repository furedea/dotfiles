#!/usr/bin/env bats
# Executable specifications for Nix-managed AI coding agent packages.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  readonly NUMTIDE_CACHE_URL="https://cache.numtide.com"
  readonly NUMTIDE_CACHE_PUBLIC_KEY="niks3.numtide.com-1:DTx8wZduET09hRmMtKdQDxNNthLQETkc/yaX7M4qK0g="
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

@test "Darwin configurations pin the Numtide binary cache trust" {
  local _host
  local _settings

  for _host in mba mbp; do
    run --separate-stderr nix eval --no-write-lock-file --json \
      "$REPO_ROOT#darwinConfigurations.$_host.config.nix.settings" \
      --apply \
      'settings: {
        substituters = settings.extra-substituters or [];
        publicKeys = settings.extra-trusted-public-keys or [];
      }'

    [ "$status" -eq 0 ]
    _settings="$output"

    run jq -ce \
      --arg cache_url "$NUMTIDE_CACHE_URL" \
      --arg public_key "$NUMTIDE_CACHE_PUBLIC_KEY" \
      '.substituters == [$cache_url] and .publicKeys == [$public_key]' \
      <<<"$_settings"

    [ "$status" -eq 0 ]
    [ "$output" = "true" ]
  done
}
