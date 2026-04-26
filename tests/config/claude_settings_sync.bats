#!/usr/bin/env bats
# Validate that every hook command in claude/settings.json references an existing script.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SETTINGS="$REPO_ROOT/claude/settings.json"
}

@test "settings.json exists and is valid JSON" {
  [ -f "$SETTINGS" ]
  jq empty "$SETTINGS"
}

@test "all hook commands reference existing scripts" {
  local missing=()

  while IFS= read -r cmd; do
    local resolved
    resolved=$(echo "$cmd" |
      sed "s|\\\$HOME/.claude/|$REPO_ROOT/claude/|")

    local script
    script=$(echo "$resolved" | awk '{print $1}')

    if [ ! -f "$script" ]; then
      missing+=("$cmd -> $script")
    fi
  done < <(jq -r '.. | objects | select(.command?) | .command' "$SETTINGS")

  if [ ${#missing[@]} -gt 0 ]; then
    printf 'Missing script:\n' >&2
    printf '  %s\n' "${missing[@]}" >&2
    return 1
  fi
}
