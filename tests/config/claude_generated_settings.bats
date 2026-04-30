#!/usr/bin/env bats
# Validate generated Claude settings used for command_policy migration.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SETTINGS="$REPO_ROOT/claude/settings.base.json"
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

@test "generated settings preserve non-permission top-level settings" {
  generated="$(generated_settings)"

  [ "$(jq -r '.model' <<<"$generated")" = "$(jq -r '.model' "$SETTINGS")" ]
  [ "$(jq -r '.language' <<<"$generated")" = "$(jq -r '.language' "$SETTINGS")" ]
  [ "$(jq -r '.hooks.PreToolUse | length' <<<"$generated")" = "$(jq -r '.hooks.PreToolUse | length' "$SETTINGS")" ]
}

@test "generated settings preserve non-Bash permissions" {
  generated="$(generated_settings)"

  expected="$(
    jq -r '.permissions.allow[], .permissions.deny[] | select(startswith("Bash(") | not)' "$SETTINGS" |
      sort
  )"
  actual="$(
    jq -r '.permissions.allow[], .permissions.deny[] | select(startswith("Bash(") | not)' <<<"$generated" |
      sort
  )"

  [ "$actual" = "$expected" ]
}

@test "generated settings derive Bash allow and deny from command policy" {
  generated="$(generated_settings)"

  jq -e '.permissions.allow[] | select(. == "Bash(uv run:*)")' <<<"$generated" >/dev/null
  jq -e '.permissions.deny[] | select(. == "Bash(rm:*)")' <<<"$generated" >/dev/null
  jq -e '.permissions.deny[] | select(. == "Bash(brew install:*)")' <<<"$generated" >/dev/null
}

@test "generated settings keep hook commands resolvable" {
  generated="$(generated_settings)"
  missing=()

  while IFS= read -r cmd; do
    resolved="${cmd/\$HOME\/.claude\//$REPO_ROOT/claude/}"
    script="$(echo "$resolved" | awk '{print $1}')"

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
