#!/usr/bin/env bats
# Validate generated Codex hook commands.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  HOOKS_JSON="$REPO_ROOT#lib.codexHooks"
}

generated_hooks() {
  nix eval --json "$HOOKS_JSON"
}

@test "generated hooks are valid JSON" {
  generated_hooks | jq empty
}

@test "all hook commands reference existing scripts" {
  local missing=()

  while IFS= read -r cmd; do
    local resolved
    resolved=$(echo "$cmd" |
      sed "s|\\\$HOME/.claude/hooks/|$REPO_ROOT/agents/hooks/|" |
      sed "s|\\\$HOME/.codex/hooks/|$REPO_ROOT/codex/hooks/|")

    local script
    script=$(echo "$resolved" | awk '{print $1}')

    if [ ! -f "$script" ]; then
      missing+=("$cmd -> $script")
    fi
  done < <(generated_hooks | jq -r '.. | objects | select(.command?) | .command')

  if [ ${#missing[@]} -gt 0 ]; then
    printf 'Missing script:\n' >&2
    printf '  %s\n' "${missing[@]}" >&2
    return 1
  fi
}

@test "no duplicate hooks within the same event group" {
  local dupes
  dupes=$(generated_hooks | jq -r '
    .hooks | to_entries[] |
    .value[] |
    [.hooks[]?.command] |
    group_by(.) |
    map(select(length > 1)) |
    .[][0]
  ' "$HOOKS_JSON" 2>/dev/null || true)

  [ -z "$dupes" ]
}

@test "home-manager writes generated Codex hooks JSON" {
  grep -q '".codex/hooks.json".text = builtins.toJSON agentHooks.codexHooks;' "$REPO_ROOT/nix/home/default.nix"
}
