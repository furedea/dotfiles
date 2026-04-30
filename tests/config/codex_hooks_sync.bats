#!/usr/bin/env bats
# Validate that every hook command in codex/hooks.json references an existing script.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOKS_JSON="$REPO_ROOT/codex/hooks.json"
}

@test "hooks.json exists and is valid JSON" {
  [ -f "$HOOKS_JSON" ]
  jq empty "$HOOKS_JSON"
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
  done < <(jq -r '.. | objects | select(.command?) | .command' "$HOOKS_JSON")

  if [ ${#missing[@]} -gt 0 ]; then
    printf 'Missing script:\n' >&2
    printf '  %s\n' "${missing[@]}" >&2
    return 1
  fi
}

@test "no duplicate hooks within the same event group" {
  local dupes
  dupes=$(jq -r '
    .hooks | to_entries[] |
    .value[] |
    [.hooks[]?.command] |
    group_by(.) |
    map(select(length > 1)) |
    .[][0]
  ' "$HOOKS_JSON" 2>/dev/null || true)

  [ -z "$dupes" ]
}
