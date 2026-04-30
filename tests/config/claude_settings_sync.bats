#!/usr/bin/env bats
# Validate that generated Claude settings reference existing hook scripts.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  GENERATED_NIX="$REPO_ROOT/nix/agents/claude_settings.nix"
}

generated_settings() {
  nix eval --impure --json --expr "
    let
      pkgs = import <nixpkgs> {};
      settings = import $GENERATED_NIX { lib = pkgs.lib; };
    in
      settings.generatedSettings
  "
}

@test "generated settings are valid JSON" {
  generated_settings | jq empty
}

@test "all hook commands reference existing scripts" {
  generated="$(generated_settings)"
  local missing=()

  while IFS= read -r cmd; do
    local script
    local resolved
    resolved="${cmd/\$HOME\/.claude\//$REPO_ROOT/claude/}"
    script=$(echo "$resolved" | awk '{print $1}')

    if [ ! -f "$script" ]; then
      missing+=("$cmd -> $script")
    fi
  done < <(jq -r '.. | objects | select(.command?) | .command' <<<"$generated")

  if [ ${#missing[@]} -gt 0 ]; then
    printf 'Missing script:\n' >&2
    printf '  %s\n' "${missing[@]}" >&2
    return 1
  fi
}
